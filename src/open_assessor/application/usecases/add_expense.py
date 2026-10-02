from dataclasses import dataclass

from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.dates import DEFAULT_TIMEZONE, Clock, to_iso_instant, today_in
from open_assessor.domain.expenses.expense import Expense, InvalidExpenseError
from open_assessor.domain.expenses.money import to_cents
from open_assessor.ports.expense_repository import ExpenseRepository


@dataclass(frozen=True, slots=True)
class AddExpenseInput:
    user_id: str
    message_key: str
    """Idempotency key: replaying the same key never creates a second expense."""
    amount: object
    """BRL decimal, e.g. 50.9."""
    description: object
    category: object
    date: object = None
    """`YYYY-MM-DD`; defaults to today in the configured timezone."""


@dataclass(frozen=True, slots=True)
class Saved:
    expense: Expense


@dataclass(frozen=True, slots=True)
class Duplicate:
    pass


type AddExpenseResult = Saved | Duplicate | Invalid


class AddExpense:
    def __init__(
        self,
        repository: ExpenseRepository,
        clock: Clock,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._timezone = timezone

    async def execute(self, input: AddExpenseInput) -> AddExpenseResult:
        amount_cents = to_cents(input.amount)
        if amount_cents is None:
            return Invalid("amount must be a positive number in BRL")

        now = self._clock()
        try:
            expense = Expense(
                date=input.date if input.date is not None else today_in(self._timezone, now),
                amount_cents=amount_cents,
                description=input.description,
                category=input.category,
                user_id=input.user_id,
                message_key=input.message_key,
                created_at=to_iso_instant(now),
            )
        except InvalidExpenseError as error:
            return Invalid(str(error))

        if await self._repository.exists_by_message_key(expense.message_key):
            return Duplicate()

        await self._repository.add(expense)

        return Saved(expense)
