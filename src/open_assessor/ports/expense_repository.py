from typing import Protocol

from open_assessor.domain.dates import DateRange
from open_assessor.domain.expenses.expense import Expense


class ExpenseRepository(Protocol):
    async def add(self, expense: Expense) -> None:
        """Idempotent: adding an expense whose `message_key` is already stored does nothing."""
        ...

    async def remove_last_by(self, user_id: str) -> Expense | None:
        """Deletes the last expense created by the user and returns it, or `None` if there is none."""
        ...

    async def exists_by_message_key(self, message_key: str) -> bool: ...

    async def list_by(self, user_id: str, date_range: DateRange) -> list[Expense]: ...
