import json
from datetime import UTC, datetime
from typing import Any

import pytest

from open_assessor.application.usecases.add_expense import AddExpense
from open_assessor.application.usecases.list_expenses import ListExpenses
from open_assessor.domain.dates import DateRange
from open_assessor.domain.expenses.expense import Expense
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.infrastructure.llm.pydantic_ai_provider import PydanticAIProvider
from open_assessor.infrastructure.llm.toolset import build_toolset
from open_assessor.ports.tool import ToolContext
from tests.infrastructure.llm.scripted_model import ScriptedModel, Step, call, text

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
CTX = ToolContext(user_id="telegram:1", message_key="telegram:10:100")


class BrokenRepository(InMemoryExpenseRepository):
    async def exists_by_message_key(self, message_key: str) -> bool:
        raise ConnectionError("Sheets is down")

    async def list_by(self, user_id: str, date_range: DateRange) -> list[Expense]:
        raise ConnectionError("Sheets is down")


async def run(repository: InMemoryExpenseRepository, *steps: Step) -> ScriptedModel:
    scripted = ScriptedModel(*steps)
    toolset = build_toolset(
        AddExpense(repository, lambda: NOW), ListExpenses(repository), lambda: NOW, "UTC"
    )
    await PydanticAIProvider(scripted.model, [toolset]).generate_response("chat", "x", CTX)
    return scripted


def tool_output(model: ScriptedModel) -> Any:
    [result] = model.tool_returns()
    content = result.content
    return json.loads(content) if isinstance(content, str) else content


@pytest.fixture
def repository() -> InMemoryExpenseRepository:
    return InMemoryExpenseRepository()


class TestSchemas:
    async def test_exposes_the_three_tools_with_their_descriptions(
        self, repository: InMemoryExpenseRepository
    ):
        model = await run(repository, text("ok"))

        tools = {t.name: t for t in model.infos[0].function_tools}
        assert set(tools) == {"add_expense", "list_expenses", "get_current_date"}
        assert "gastei 50 no burger king" in (tools["add_expense"].description or "")

    async def test_add_expense_takes_a_non_empty_list_with_categories_as_an_enum(
        self, repository: InMemoryExpenseRepository
    ):
        model = await run(repository, text("ok"))

        [tool] = [t for t in model.infos[0].function_tools if t.name == "add_expense"]
        schema = tool.parameters_json_schema
        expenses = schema["properties"]["expenses"]
        assert expenses["minItems"] == 1
        assert "alimentacao" in json.dumps(schema)
        assert schema["required"] == ["expenses"]

    async def test_list_expenses_requires_both_days(self, repository: InMemoryExpenseRepository):
        model = await run(repository, text("ok"))

        [tool] = [t for t in model.infos[0].function_tools if t.name == "list_expenses"]
        assert tool.parameters_json_schema["required"] == ["from_date", "to_date"]


class TestCalls:
    async def test_add_expense_saves_for_the_context_user(
        self, repository: InMemoryExpenseRepository
    ):
        model = await run(
            repository,
            call(
                "add_expense",
                {
                    "expenses": [
                        {"amount": 50, "description": "burger king", "category": "alimentacao"}
                    ]
                },
            ),
            text("salvo"),
        )

        assert tool_output(model)["results"][0]["status"] == "saved"
        saved = await repository.list_by("telegram:1", DateRange("2026-10-01", "2026-10-01"))
        assert saved[0].message_key == "telegram:10:100#0"

    async def test_list_expenses_reads_the_period(self, repository: InMemoryExpenseRepository):
        model = await run(
            repository,
            call("list_expenses", {"from_date": "2026-10-01", "to_date": "2026-10-31"}),
            text("nada"),
        )

        assert tool_output(model)["count"] == 0

    async def test_get_current_date_uses_the_clock(self, repository: InMemoryExpenseRepository):
        model = await run(repository, call("get_current_date"), text("hoje"))

        assert tool_output(model)["date"] == "2026-10-01"

    async def test_an_unknown_category_is_sent_back_to_the_model_to_fix(
        self, repository: InMemoryExpenseRepository
    ):
        model = await run(
            repository,
            call(
                "add_expense",
                {"expenses": [{"amount": 50, "description": "x", "category": "viagem"}]},
            ),
            text("ok"),
        )

        assert model.retry_prompts() != []
        assert not await repository.exists_by_message_key("telegram:10:100#0")

    @pytest.mark.parametrize(
        "step",
        [
            pytest.param(
                call(
                    "add_expense",
                    {"expenses": [{"amount": 5, "description": "x", "category": "outros"}]},
                ),
                id="add_expense",
            ),
            pytest.param(
                call("list_expenses", {"from_date": "2026-10-01", "to_date": "2026-10-31"}),
                id="list_expenses",
            ),
        ],
    )
    async def test_a_storage_failure_is_reported_to_the_model_instead_of_raising(self, step: Step):
        model = await run(BrokenRepository(), step, text("não salvei"))

        assert tool_output(model) == {"status": "error", "reason": "Sheets is down"}
