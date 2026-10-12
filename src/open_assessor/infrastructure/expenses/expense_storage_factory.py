import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from open_assessor.infrastructure.expenses.google_auth import (
    create_sheets_api,
    read_service_account_email,
)
from open_assessor.infrastructure.expenses.google_sheets_workspace import GoogleSheetsWorkspace
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.infrastructure.expenses.per_user_expense_repository import (
    PerUserExpenseRepository,
)
from open_assessor.infrastructure.expenses.sheets_api import SheetsApi
from open_assessor.ports.expense_repository import ExpenseRepository
from open_assessor.ports.spreadsheet_access import SpreadsheetAccess
from open_assessor.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class CreatedExpenseStorage:
    name: str
    persistent: bool
    repository: ExpenseRepository
    spreadsheets: SpreadsheetAccess | None
    """`None` when expenses live in memory and users need no spreadsheet."""


async def create_expense_storage(
    users: UserRepository,
    env: Mapping[str, str] = os.environ,
    create_api: Callable[[Mapping[str, str]], SheetsApi] = create_sheets_api,
    read_email: Callable[[Mapping[str, str]], str | None] = read_service_account_email,
) -> CreatedExpenseStorage:
    """One Google spreadsheet per user when `SPREADSHEET_ID` or `MONGODB_URL` is set,
    otherwise memory (lost on restart).

    `SPREADSHEET_ID`, if set, is validated now so a misconfiguration fails at startup.
    """
    spreadsheet_id = env.get("SPREADSHEET_ID", "").strip()
    if not spreadsheet_id and not env.get("MONGODB_URL", "").strip():
        return CreatedExpenseStorage("in-memory", False, InMemoryExpenseRepository(), None)

    workspace = GoogleSheetsWorkspace(create_api(env), read_email(env))
    if spreadsheet_id:
        await workspace.open(spreadsheet_id)

    return CreatedExpenseStorage(
        "Google Sheets (one per user)",
        True,
        PerUserExpenseRepository(users, workspace.open),
        workspace,
    )
