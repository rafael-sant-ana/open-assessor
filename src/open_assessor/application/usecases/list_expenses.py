from dataclasses import dataclass

from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.categories import CATEGORIES, is_category
from open_assessor.domain.dates import DateRange, is_valid_iso_date
from open_assessor.domain.expenses.expense import Expense
from open_assessor.domain.expenses.summarize import ExpenseSummary, summarize
from open_assessor.ports.expense_repository import ExpenseRepository


@dataclass(frozen=True, slots=True)
class ListExpensesInput:
    user_id: str
    from_: object
    """Inclusive `YYYY-MM-DD`."""
    to: object
    """Inclusive `YYYY-MM-DD`."""
    category: object = None
    """Only expenses of this category; `None` for all."""


@dataclass(frozen=True, slots=True)
class Listed:
    expenses: list[Expense]
    summary: ExpenseSummary


type ListExpensesResult = Listed | Invalid


class ListExpenses:
    def __init__(self, repository: ExpenseRepository) -> None:
        self._repository = repository

    async def execute(self, input: ListExpensesInput) -> ListExpensesResult:
        from_, to, category = input.from_, input.to, input.category

        if not is_valid_iso_date(from_) or not is_valid_iso_date(to):
            return Invalid("from and to must be real days formatted as YYYY-MM-DD")
        if from_ > to:
            return Invalid("from must not be after to")
        if category is not None and not is_category(category):
            return Invalid(f"category must be one of: {', '.join(CATEGORIES)}")

        found = await self._repository.list_by(input.user_id, DateRange(from_, to))
        expenses = found if category is None else [e for e in found if e.has_category(category)]

        return Listed(expenses, summarize(expenses))
