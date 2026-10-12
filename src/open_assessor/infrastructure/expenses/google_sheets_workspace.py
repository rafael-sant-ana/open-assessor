import asyncio

from googleapiclient.errors import HttpError

from open_assessor.infrastructure.expenses.google_sheets_expense_repository import (
    GoogleSheetsExpenseRepository,
    UnexpectedHeaderError,
)
from open_assessor.infrastructure.expenses.sheets_api import SheetsApi
from open_assessor.ports.spreadsheet_access import SpreadsheetProblem

_NO_ACCESS_STATUSES = frozenset({400, 403, 404})
"""Bad id, not shared with the service account, or deleted."""


class GoogleSheetsWorkspace:
    """Opens any spreadsheet shared with the service account, one cached repository per
    spreadsheet so each keeps its own lock and idempotency keys."""

    def __init__(self, sheets: SheetsApi, service_account_email: str | None) -> None:
        self._sheets = sheets
        self._service_account_email = service_account_email
        self._repositories: dict[str, GoogleSheetsExpenseRepository] = {}
        self._lock = asyncio.Lock()

    @property
    def service_account_email(self) -> str | None:
        return self._service_account_email

    async def open(self, spreadsheet_id: str) -> GoogleSheetsExpenseRepository:
        async with self._lock:
            repository = self._repositories.get(spreadsheet_id)
            if repository is None:
                repository = await GoogleSheetsExpenseRepository.create(
                    self._sheets, spreadsheet_id
                )
                self._repositories[spreadsheet_id] = repository
            return repository

    async def check(self, spreadsheet_id: str) -> SpreadsheetProblem | None:
        try:
            await self.open(spreadsheet_id)
        except HttpError as error:
            status: int = getattr(error, "status_code", 0)
            if status in _NO_ACCESS_STATUSES:
                return "not_shared"
            raise
        except UnexpectedHeaderError:
            return "invalid_layout"
        return None
