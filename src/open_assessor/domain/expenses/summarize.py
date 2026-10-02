from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from open_assessor.domain.categories import Category
from open_assessor.domain.expenses.expense import Expense


@dataclass(frozen=True, slots=True)
class ExpenseSummary:
    count: int
    total_cents: int
    by_category: Mapping[Category, int]


def summarize(expenses: Iterable[Expense]) -> ExpenseSummary:
    by_category: dict[Category, int] = {}
    count = 0
    total_cents = 0

    for expense in expenses:
        count += 1
        total_cents += expense.amount_cents
        by_category[expense.category] = by_category.get(expense.category, 0) + expense.amount_cents

    return ExpenseSummary(count=count, total_cents=total_cents, by_category=by_category)
