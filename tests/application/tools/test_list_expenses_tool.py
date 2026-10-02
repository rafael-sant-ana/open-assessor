import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import pytest

from open_assessor.application.tools.list_expenses_tool import (
    MAX_LISTED_EXPENSES,
    ListExpensesTool,
)
from open_assessor.application.usecases.list_expenses import ListExpenses
from open_assessor.domain.expenses.expense import Expense
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.ports.tool import ToolContext
from tests.factories import make_expense

CONTEXT = ToolContext(user_id="telegram:1", message_key="telegram:10:100")

type Run = Callable[[Mapping[str, object]], Awaitable[dict[str, Any]]]


def expense(i: int, **overrides: Any) -> Expense:
    return make_expense(
        **{
            "amount_cents": 1000,
            "description": f"item {i}",
            "category": "outros",
            "message_key": f"key-{i}",
            **overrides,
        }
    )


@pytest.fixture
def repository() -> InMemoryExpenseRepository:
    return InMemoryExpenseRepository()


@pytest.fixture
def run(repository: InMemoryExpenseRepository) -> Run:
    tool = ListExpensesTool(ListExpenses(repository))

    async def run(args: Mapping[str, object]) -> dict[str, Any]:
        return json.loads(await tool.execute(args, CONTEXT))

    return run


async def test_returns_formatted_totals_per_category_totals_and_the_expenses(
    run: Run, repository: InMemoryExpenseRepository
):
    await repository.add(expense(1, amount_cents=5000, category="alimentacao"))
    await repository.add(expense(2, amount_cents=2090, category="transporte"))
    await repository.add(expense(3, user_id="telegram:2", amount_cents=9999))

    result = await run({"from": "2026-10-01", "to": "2026-10-31"})

    assert result["status"] == "ok"
    assert result["count"] == 2
    assert result["total"] == "R$ 70,90"
    assert result["byCategory"] == {"alimentacao": "R$ 50,00", "transporte": "R$ 20,90"}
    assert result["expenses"][0] == {
        "date": "2026-10-01",
        "amount": "R$ 50,00",
        "description": "item 1",
        "category": "alimentacao",
    }
    assert result["truncated"] is False


async def test_caps_the_listed_expenses_but_summarizes_all_of_them(
    run: Run, repository: InMemoryExpenseRepository
):
    for i in range(MAX_LISTED_EXPENSES + 5):
        await repository.add(expense(i))

    result = await run({"from": "2026-10-01", "to": "2026-10-31"})

    assert len(result["expenses"]) == MAX_LISTED_EXPENSES
    assert result["count"] == MAX_LISTED_EXPENSES + 5
    assert result["truncated"] is True


async def test_passes_the_category_filter_through(run: Run, repository: InMemoryExpenseRepository):
    await repository.add(expense(1, category="lazer"))
    await repository.add(expense(2, category="outros"))

    result = await run({"from": "2026-10-01", "to": "2026-10-31", "category": "lazer"})

    assert result["count"] == 1


async def test_reports_invalid_arguments_to_the_model(run: Run):
    result = await run({"from": "ontem", "to": "2026-10-31"})

    assert result["status"] == "invalid"
    assert "YYYY-MM-DD" in result["reason"]
