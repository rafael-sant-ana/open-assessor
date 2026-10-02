import itertools
from typing import Any

import pytest

from open_assessor.application.usecases.list_expenses import (
    Listed,
    ListExpenses,
    ListExpensesInput,
)
from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.expenses.summarize import ExpenseSummary
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from tests.factories import make_expense

_keys = itertools.count()


def expense(**overrides: Any):
    return make_expense(
        **{"amount_cents": 1000, "category": "outros", "message_key": f"key-{next(_keys)}"}
        | overrides
    )


@pytest.fixture
async def list_expenses() -> ListExpenses:
    repository = InMemoryExpenseRepository()
    await repository.add(expense(date="2026-10-01", amount_cents=5000, category="alimentacao"))
    await repository.add(expense(date="2026-10-15", amount_cents=2000, category="transporte"))
    await repository.add(expense(date="2026-11-01", amount_cents=9900))
    await repository.add(expense(user_id="telegram:2", amount_cents=7700))
    return ListExpenses(repository)


def make_input(**overrides: Any) -> ListExpensesInput:
    return ListExpensesInput(
        **{"user_id": "telegram:1", "from_": "2026-10-01", "to": "2026-10-31", **overrides}
    )


async def test_lists_the_user_expenses_in_the_inclusive_range_with_a_summary(
    list_expenses: ListExpenses,
):
    result = await list_expenses.execute(make_input(to="2026-10-15"))

    assert isinstance(result, Listed)
    assert len(result.expenses) == 2
    assert result.summary == ExpenseSummary(
        count=2,
        total_cents=7000,
        by_category={"alimentacao": 5000, "transporte": 2000},
    )


async def test_filters_by_category(list_expenses: ListExpenses):
    result = await list_expenses.execute(make_input(category="transporte"))

    assert isinstance(result, Listed)
    assert result.summary.total_cents == 2000


async def test_returns_an_empty_summary_when_nothing_matches(list_expenses: ListExpenses):
    result = await list_expenses.execute(make_input(from_="2025-01-01", to="2025-01-31"))

    assert isinstance(result, Listed)
    assert result.summary.count == 0


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        pytest.param({"from_": "01/10/2026"}, "YYYY-MM-DD", id="a malformed from"),
        pytest.param({"to": "2026-02-30"}, "YYYY-MM-DD", id="an impossible to"),
        pytest.param({"from_": None}, "YYYY-MM-DD", id="a missing from"),
        pytest.param({"from_": "2026-10-31", "to": "2026-10-01"}, "after", id="from after to"),
        pytest.param({"category": "viagem"}, "category", id="an unknown category"),
    ],
)
async def test_rejects_invalid_input(
    list_expenses: ListExpenses, overrides: dict[str, Any], reason: str
):
    result = await list_expenses.execute(make_input(**overrides))

    assert isinstance(result, Invalid)
    assert reason in result.reason
