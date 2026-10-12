from collections.abc import Awaitable, Callable

from open_assessor.domain.dates import DateRange
from open_assessor.domain.expenses.expense import Expense
from open_assessor.ports.expense_repository import ExpenseRepository
from open_assessor.ports.user_repository import UserRepository

type OpenSpreadsheet = Callable[[str], Awaitable[ExpenseRepository]]


class SpreadsheetNotConnectedError(Exception):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"{user_id} has no spreadsheet connected")


class PerUserExpenseRepository:
    """Routes every operation to the spreadsheet of the user it is about."""

    def __init__(self, users: UserRepository, open_spreadsheet: OpenSpreadsheet) -> None:
        self._users = users
        self._open_spreadsheet = open_spreadsheet

    async def add(self, expense: Expense) -> None:
        await (await self._repository_of(expense.user_id)).add(expense)

    async def remove_last_by(self, user_id: str) -> Expense | None:
        return await (await self._repository_of(user_id)).remove_last_by(user_id)

    async def exists_by_message_key(self, user_id: str, message_key: str) -> bool:
        repository = await self._repository_of(user_id)
        return await repository.exists_by_message_key(user_id, message_key)

    async def list_by(self, user_id: str, date_range: DateRange) -> list[Expense]:
        return await (await self._repository_of(user_id)).list_by(user_id, date_range)

    async def _repository_of(self, user_id: str) -> ExpenseRepository:
        user = await self._users.get(user_id)
        if user is None or user.spreadsheet_id is None:
            raise SpreadsheetNotConnectedError(user_id)
        return await self._open_spreadsheet(user.spreadsheet_id)
