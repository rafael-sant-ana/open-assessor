import asyncio
import math
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, TypeGuard

from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError
from httplib2 import ServerNotFoundError

from open_assessor.domain.dates import DateRange
from open_assessor.domain.expenses.expense import Expense, InvalidExpenseError
from open_assessor.infrastructure.expenses.sheets_api import SheetsApi

SHEET_HEADER = (
    "data",
    "valor",
    "descricao",
    "categoria",
    "criado_em",
    "message_key",
    "user_id",
)

DEFAULT_TAB_NAME = "gastos"
MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 0.2
_TRANSIENT_NETWORK_ERRORS = (
    ConnectionError,
    TimeoutError,
    socket.gaierror,
    ServerNotFoundError,
    TransportError,
)

SHEETS_EPOCH = date(1899, 12, 30)
"""Sheets counts days from 1899-12-30."""

type Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class _StoredExpense:
    expense: Expense
    row_index: int
    """0-based row in the tab; the header is row 0."""


class GoogleSheetsExpenseRepository:
    """Stores expenses in one tab of a Google spreadsheet that the bot owns: rows are only
    appended (or deleted by undo) and never reordered, so charts on other tabs can safely
    reference `gastos!A:G`."""

    def __init__(
        self,
        sheets: SheetsApi,
        spreadsheet_id: str,
        tab_name: str,
        sheet_id: int,
        sleep: Sleep,
    ) -> None:
        """Use `create`, which also prepares the tab."""
        self._sheets = sheets
        self._spreadsheet_id = spreadsheet_id
        self._tab_name = tab_name
        self._sheet_id = sheet_id
        self._sleep = sleep
        # All operations run one at a time so check-then-write sequences never interleave.
        self._lock = asyncio.Lock()
        self._keys: set[str] | None = None

    @classmethod
    async def create(
        cls,
        sheets: SheetsApi,
        spreadsheet_id: str,
        *,
        tab_name: str = DEFAULT_TAB_NAME,
        sleep: Sleep = asyncio.sleep,
    ) -> "GoogleSheetsExpenseRepository":
        """Creates the tab (with header and formats) if missing and validates it otherwise."""
        sheet_id = await _ensure_schema(sheets, spreadsheet_id, tab_name, sleep)
        return cls(sheets, spreadsheet_id, tab_name, sheet_id, sleep)

    async def add(self, expense: Expense) -> None:
        async with self._lock:
            if expense.message_key in await self._load_keys():
                return

            async def append(attempt: int) -> None:
                # A failed attempt may still have reached the sheet; look before writing again.
                if attempt > 1:
                    self._keys = None
                    if expense.message_key in await self._load_keys():
                        return

                await self._sheets.values_append(
                    spreadsheetId=self._spreadsheet_id,
                    range=self._range(),
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [_to_row(expense)]},
                )

            await _retry(append, self._sleep)

            (await self._load_keys()).add(expense.message_key)

    async def exists_by_message_key(self, message_key: str) -> bool:
        async with self._lock:
            return message_key in await self._load_keys()

    async def list_by(self, user_id: str, date_range: DateRange) -> list[Expense]:
        async with self._lock:
            return [
                stored.expense
                for stored in await self._read_expenses()
                if stored.expense.belongs_to(user_id) and stored.expense.occurs_within(date_range)
            ]

    async def remove_last_by(self, user_id: str) -> Expense | None:
        async with self._lock:
            owned = [s for s in await self._read_expenses() if s.expense.belongs_to(user_id)]
            if not owned:
                return None
            last = owned[-1]

            await _retry(
                lambda _: self._sheets.spreadsheets_batch_update(
                    spreadsheetId=self._spreadsheet_id,
                    body={
                        "requests": [
                            {
                                "deleteDimension": {
                                    "range": {
                                        "sheetId": self._sheet_id,
                                        "dimension": "ROWS",
                                        "startIndex": last.row_index,
                                        "endIndex": last.row_index + 1,
                                    }
                                }
                            }
                        ]
                    },
                ),
                self._sleep,
            )

            if self._keys is not None:
                self._keys.discard(last.expense.message_key)
            return last.expense

    async def _load_keys(self) -> set[str]:
        if self._keys is None:
            self._keys = {s.expense.message_key for s in await self._read_expenses()}
        return self._keys

    async def _read_expenses(self) -> list[_StoredExpense]:
        """Valid rows only."""
        response = await _retry(
            lambda _: self._sheets.values_get(
                spreadsheetId=self._spreadsheet_id,
                range=self._range(),
                valueRenderOption="UNFORMATTED_VALUE",
            ),
            self._sleep,
        )

        rows: list[list[object]] = response.get("values", [])
        stored: list[_StoredExpense] = []
        for row_index, row in enumerate(rows):
            expense = None if row_index == 0 else _from_row(row)
            if expense is not None:
                stored.append(_StoredExpense(expense, row_index))
        return stored

    def _range(self) -> str:
        return f"'{self._tab_name}'!A:G"


async def _ensure_schema(
    sheets: SheetsApi, spreadsheet_id: str, tab_name: str, sleep: Sleep
) -> int:
    metadata = await _retry(
        lambda _: sheets.spreadsheets_get(
            spreadsheetId=spreadsheet_id,
            fields="sheets.properties(sheetId,title)",
        ),
        sleep,
    )
    existing = next(
        (
            s["properties"]
            for s in metadata.get("sheets", [])
            if s.get("properties", {}).get("title") == tab_name
        ),
        None,
    )
    sheet_id: int | None = existing.get("sheetId") if existing else None

    if sheet_id is None:
        created = await _retry(
            lambda _: sheets.spreadsheets_batch_update(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
            ),
            sleep,
        )
        replies: list[dict[str, Any]] = created.get("replies", [])
        sheet_id = (
            replies[0].get("addSheet", {}).get("properties", {}).get("sheetId") if replies else None
        )
        if sheet_id is None:
            raise RuntimeError(f'Failed to create the "{tab_name}" tab')

        await _write_header_and_formats(sheets, spreadsheet_id, tab_name, sheet_id, sleep)
        return sheet_id

    response = await _retry(
        lambda _: sheets.values_get(spreadsheetId=spreadsheet_id, range=f"'{tab_name}'!A1:G1"),
        sleep,
    )
    values: list[list[object]] = response.get("values") or [[]]
    header = values[0]

    if not header:
        await _write_header_and_formats(sheets, spreadsheet_id, tab_name, sheet_id, sleep)
        return sheet_id

    if tuple(header) != SHEET_HEADER:
        raise RuntimeError(
            f'The "{tab_name}" tab has unexpected headers ({", ".join(map(str, header))}). '
            f"Expected: {', '.join(SHEET_HEADER)}. Fix or rename the tab; it is never overwritten."
        )

    return sheet_id


async def _write_header_and_formats(
    sheets: SheetsApi, spreadsheet_id: str, tab_name: str, sheet_id: int, sleep: Sleep
) -> None:
    await _retry(
        lambda _: sheets.values_update(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab_name}'!A1:G1",
            valueInputOption="RAW",
            body={"values": [list(SHEET_HEADER)]},
        ),
        sleep,
    )

    def number_format(column: int, type: str, pattern: str) -> dict[str, Any]:
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": column,
                    "endColumnIndex": column + 1,
                },
                "cell": {"userEnteredFormat": {"numberFormat": {"type": type, "pattern": pattern}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        }

    await _retry(
        lambda _: sheets.spreadsheets_batch_update(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    number_format(0, "DATE", "dd/mm/yyyy"),
                    number_format(1, "CURRENCY", '"R$" #,##0.00'),
                ]
            },
        ),
        sleep,
    )


def _to_row(expense: Expense) -> list[str | int | float]:
    return [
        _iso_to_serial(expense.date),
        expense.amount_cents / 100,
        expense.description,
        expense.category,
        expense.created_at,
        expense.message_key,
        expense.user_id,
    ]


def _from_row(row: list[object]) -> Expense | None:
    serial, valor, description, category, created_at, message_key, user_id = (
        row + [None] * len(SHEET_HEADER)
    )[: len(SHEET_HEADER)]

    # The sheet is only a store: a row someone mangled by hand is skipped, not fatal.
    if not _is_number(serial) or not _is_number(valor):
        return None

    try:
        return Expense(
            date=_serial_to_iso(serial),
            amount_cents=math.floor(valor * 100 + 0.5),
            description=description,
            category=category,
            user_id=user_id,
            message_key=message_key,
            created_at=created_at,
        )
    except InvalidExpenseError:
        return None


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _iso_to_serial(day: str) -> int:
    return (date.fromisoformat(day) - SHEETS_EPOCH).days


def _serial_to_iso(serial: float) -> str:
    return (SHEETS_EPOCH + timedelta(days=math.floor(serial))).isoformat()


async def _retry[T](operation: Callable[[int], Awaitable[T]], sleep: Sleep) -> T:
    attempt = 1
    while True:
        try:
            return await operation(attempt)
        except Exception as error:
            if attempt >= MAX_ATTEMPTS or not _is_transient(error):
                raise
            await sleep(BASE_BACKOFF_SECONDS * 2 ** (attempt - 1))
            attempt += 1


def _is_transient(error: Exception) -> bool:
    if isinstance(error, HttpError):
        status: int = getattr(error, "status_code", 0)
        return status == 429 or status >= 500
    return isinstance(error, _TRANSIENT_NETWORK_ERRORS)
