import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from open_assessor.infrastructure.expenses.google_auth import create_sheets_api
from open_assessor.infrastructure.expenses.google_sheets_expense_repository import (
    GoogleSheetsExpenseRepository,
)
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.infrastructure.expenses.sheets_api import SheetsApi
from open_assessor.ports.expense_repository import ExpenseRepository


@dataclass(frozen=True, slots=True)
class CreatedRepository:
    name: str
    persistent: bool
    repository: ExpenseRepository


async def create_expense_repository(
    env: Mapping[str, str] = os.environ,
    create_api: Callable[[Mapping[str, str]], SheetsApi] = create_sheets_api,
) -> CreatedRepository:
    """Google Sheets when `SPREADSHEET_ID` is set, otherwise memory (lost on restart).

    Also validates the sheet, so a misconfiguration fails at startup, not on the first expense.
    """
    spreadsheet_id = env.get("SPREADSHEET_ID", "").strip()

    if not spreadsheet_id:
        return CreatedRepository("in-memory", False, InMemoryExpenseRepository())

    return CreatedRepository(
        "Google Sheets",
        True,
        await GoogleSheetsExpenseRepository.create(create_api(env), spreadsheet_id),
    )
