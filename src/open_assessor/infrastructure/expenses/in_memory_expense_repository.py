from open_assessor.domain.dates import DateRange
from open_assessor.domain.expenses.expense import Expense


class InMemoryExpenseRepository:
    def __init__(self) -> None:
        self._expenses: list[Expense] = []

    async def add(self, expense: Expense) -> None:
        if await self.exists_by_message_key(expense.message_key):
            return
        self._expenses.append(expense)

    async def remove_last_by(self, user_id: str) -> Expense | None:
        for index in range(len(self._expenses) - 1, -1, -1):
            if self._expenses[index].belongs_to(user_id):
                return self._expenses.pop(index)
        return None

    async def exists_by_message_key(self, message_key: str) -> bool:
        return any(e.message_key == message_key for e in self._expenses)

    async def list_by(self, user_id: str, date_range: DateRange) -> list[Expense]:
        return [e for e in self._expenses if e.belongs_to(user_id) and e.occurs_within(date_range)]
