import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from open_assessor.application.tools.add_expense_tool import AddExpenseTool
from open_assessor.application.usecases.add_expense import AddExpense
from open_assessor.domain.dates import DateRange
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.ports.tool import ToolContext

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
CONTEXT = ToolContext(user_id="telegram:1", message_key="telegram:10:100")

type Run = Callable[[Mapping[str, object]], Awaitable[list[dict[str, Any]]]]


@pytest.fixture
def repository() -> InMemoryExpenseRepository:
    return InMemoryExpenseRepository()


@pytest.fixture
def tool(repository: InMemoryExpenseRepository) -> AddExpenseTool:
    return AddExpenseTool(AddExpense(repository, lambda: NOW))


@pytest.fixture
def run(tool: AddExpenseTool) -> Run:
    async def run(args: Mapping[str, object]) -> list[dict[str, Any]]:
        return json.loads(await tool.execute(args, CONTEXT))["results"]

    return run


def test_exposes_the_categories_as_an_enum_in_its_schema(tool: AddExpenseTool):
    schema: Any = tool.parameters

    assert (
        "alimentacao" in schema["properties"]["expenses"]["items"]["properties"]["category"]["enum"]
    )


async def test_saves_an_expense_for_the_context_user_and_reports_it(
    run: Run, repository: InMemoryExpenseRepository
):
    results = await run(
        {"expenses": [{"amount": 50, "description": "burger king", "category": "alimentacao"}]}
    )

    assert results == [
        {
            "status": "saved",
            "date": "2026-10-01",
            "amount": "R$ 50,00",
            "description": "burger king",
            "category": "alimentacao",
        }
    ]
    saved = await repository.list_by("telegram:1", DateRange("2026-10-01", "2026-10-01"))
    assert saved[0].message_key == "telegram:10:100#0"


async def test_saves_several_expenses_from_one_message_under_distinct_keys(
    run: Run, repository: InMemoryExpenseRepository
):
    results = await run(
        {
            "expenses": [
                {"amount": 20, "description": "uber", "category": "transporte"},
                {"amount": 30, "description": "almoço", "category": "alimentacao"},
            ]
        }
    )

    assert [r["status"] for r in results] == ["saved", "saved"]
    assert await repository.exists_by_message_key("telegram:10:100#0")
    assert await repository.exists_by_message_key("telegram:10:100#1")


async def test_reports_a_replayed_message_as_duplicate_instead_of_saving_again(run: Run):
    args = {"expenses": [{"amount": 20, "description": "uber", "category": "transporte"}]}

    await run(args)
    results = await run(args)

    assert results == [{"status": "duplicate"}]


async def test_reports_invalid_items_without_blocking_the_valid_ones(run: Run):
    results = await run(
        {
            "expenses": [
                {"amount": "muito", "description": "uber", "category": "transporte"},
                {"amount": 30, "description": "almoço", "category": "alimentacao"},
            ]
        }
    )

    assert results[0]["status"] == "invalid"
    assert results[1]["status"] == "saved"


@pytest.mark.parametrize(
    "args",
    [
        pytest.param({}, id="a missing expenses field"),
        pytest.param({"expenses": []}, id="an empty list"),
        pytest.param({"expenses": "gastei 50"}, id="a non-array"),
    ],
)
async def test_rejects_a_bad_expenses_argument(run: Run, args: Mapping[str, object]):
    results = await run(args)

    assert results[0]["status"] == "invalid"


async def test_treats_a_non_object_item_as_invalid(run: Run):
    results = await run({"expenses": ["50"]})

    assert results[0]["status"] == "invalid"
