from datetime import UTC, datetime
from typing import Any

import pytest

from open_assessor.application.assistant_tools import (
    MAX_LISTED_EXPENSES,
    ExpenseItem,
    add_expenses,
    current_date,
    list_expenses,
)
from open_assessor.application.usecases.add_expense import AddExpense
from open_assessor.application.usecases.list_expenses import ListExpenses
from open_assessor.domain.dates import DateRange
from open_assessor.domain.expenses.expense import Expense
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.ports.tool import ToolContext
from tests.factories import make_expense

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
CONTEXT = ToolContext(user_id="telegram:1", message_key="telegram:10:100")


@pytest.fixture
def repository() -> InMemoryExpenseRepository:
    return InMemoryExpenseRepository()


class TestAddExpenses:
    @pytest.fixture
    def add_expense(self, repository: InMemoryExpenseRepository) -> AddExpense:
        return AddExpense(repository, lambda: NOW)

    async def test_saves_an_expense_for_the_context_user_and_reports_it(
        self, add_expense: AddExpense, repository: InMemoryExpenseRepository
    ):
        output = await add_expenses(
            add_expense, CONTEXT, [ExpenseItem(50, "burger king", "alimentacao")]
        )

        assert output == {
            "results": [
                {
                    "status": "saved",
                    "date": "2026-10-01",
                    "amount": "R$ 50,00",
                    "description": "burger king",
                    "category": "alimentacao",
                }
            ]
        }
        saved = await repository.list_by("telegram:1", DateRange("2026-10-01", "2026-10-01"))
        assert saved[0].message_key == "telegram:10:100#0"

    async def test_uses_the_given_date(self, add_expense: AddExpense):
        output = await add_expenses(
            add_expense, CONTEXT, [ExpenseItem(20, "uber", "transporte", date="2026-09-30")]
        )

        assert output["results"][0]["date"] == "2026-09-30"

    async def test_saves_several_expenses_from_one_message_under_distinct_keys(
        self, add_expense: AddExpense, repository: InMemoryExpenseRepository
    ):
        output = await add_expenses(
            add_expense,
            CONTEXT,
            [ExpenseItem(20, "uber", "transporte"), ExpenseItem(30, "almoço", "alimentacao")],
        )

        assert [r["status"] for r in output["results"]] == ["saved", "saved"]
        assert await repository.exists_by_message_key("telegram:10:100#0")
        assert await repository.exists_by_message_key("telegram:10:100#1")

    async def test_reports_a_replayed_message_as_duplicate_instead_of_saving_again(
        self, add_expense: AddExpense
    ):
        items = [ExpenseItem(20, "uber", "transporte")]

        await add_expenses(add_expense, CONTEXT, items)
        output = await add_expenses(add_expense, CONTEXT, items)

        assert output == {"results": [{"status": "duplicate"}]}

    async def test_reports_invalid_items_without_blocking_the_valid_ones(
        self, add_expense: AddExpense
    ):
        output = await add_expenses(
            add_expense,
            CONTEXT,
            [ExpenseItem(-5, "uber", "transporte"), ExpenseItem(30, "almoço", "alimentacao")],
        )

        assert output["results"][0]["status"] == "invalid"
        assert "amount" in output["results"][0]["reason"]
        assert output["results"][1]["status"] == "saved"

    @pytest.mark.parametrize(
        "item",
        [
            pytest.param(ExpenseItem(10, "   ", "outros"), id="a blank description"),
            pytest.param(
                ExpenseItem(10, "x", "outros", date="2026-02-30"), id="an impossible date"
            ),
            pytest.param(ExpenseItem(10_000_000, "x", "outros"), id="an amount above the cap"),
        ],
    )
    async def test_relays_business_rule_violations(
        self, add_expense: AddExpense, item: ExpenseItem
    ):
        output = await add_expenses(add_expense, CONTEXT, [item])

        assert output["results"][0]["status"] == "invalid"

    async def test_rejects_an_empty_list(self, add_expense: AddExpense):
        output = await add_expenses(add_expense, CONTEXT, [])

        assert output["results"][0]["status"] == "invalid"


class TestListExpenses:
    @pytest.fixture
    def use_case(self, repository: InMemoryExpenseRepository) -> ListExpenses:
        return ListExpenses(repository)

    @staticmethod
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

    async def test_returns_formatted_totals_per_category_totals_and_the_expenses(
        self, use_case: ListExpenses, repository: InMemoryExpenseRepository
    ):
        await repository.add(self.expense(1, amount_cents=5000, category="alimentacao"))
        await repository.add(self.expense(2, amount_cents=2090, category="transporte"))
        await repository.add(self.expense(3, user_id="telegram:2", amount_cents=9999))

        output = await list_expenses(use_case, CONTEXT, "2026-10-01", "2026-10-31")

        assert output["status"] == "ok"
        assert output["count"] == 2
        assert output["total"] == "R$ 70,90"
        assert output["byCategory"] == {"alimentacao": "R$ 50,00", "transporte": "R$ 20,90"}
        assert output["expenses"][0] == {
            "date": "2026-10-01",
            "amount": "R$ 50,00",
            "description": "item 1",
            "category": "alimentacao",
        }
        assert output["truncated"] is False

    async def test_caps_the_listed_expenses_but_summarizes_all_of_them(
        self, use_case: ListExpenses, repository: InMemoryExpenseRepository
    ):
        for i in range(MAX_LISTED_EXPENSES + 5):
            await repository.add(self.expense(i))

        output = await list_expenses(use_case, CONTEXT, "2026-10-01", "2026-10-31")

        assert len(output["expenses"]) == MAX_LISTED_EXPENSES
        assert output["count"] == MAX_LISTED_EXPENSES + 5
        assert output["truncated"] is True

    async def test_passes_the_category_filter_through(
        self, use_case: ListExpenses, repository: InMemoryExpenseRepository
    ):
        await repository.add(self.expense(1, category="lazer"))
        await repository.add(self.expense(2, category="outros"))

        output = await list_expenses(use_case, CONTEXT, "2026-10-01", "2026-10-31", "lazer")

        assert output["count"] == 1

    async def test_reports_invalid_dates_to_the_model(self, use_case: ListExpenses):
        output = await list_expenses(use_case, CONTEXT, "ontem", "2026-10-31")

        assert output["status"] == "invalid"
        assert "YYYY-MM-DD" in output["reason"]


class TestCurrentDate:
    def test_returns_the_day_and_weekday_in_the_configured_timezone(self):
        # 02:30 UTC on Oct 2nd is still Thursday Oct 1st in São Paulo.
        clock = lambda: datetime(2026, 10, 2, 2, 30, tzinfo=UTC)  # noqa: E731

        assert current_date(clock, "America/Sao_Paulo") == {
            "date": "2026-10-01",
            "weekday": "quinta-feira",
            "timezone": "America/Sao_Paulo",
        }

    def test_reads_the_clock_on_every_call(self):
        now = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
        clock = lambda: now  # noqa: E731

        first = current_date(clock, "America/Sao_Paulo")["date"]
        now = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)
        second = current_date(clock, "America/Sao_Paulo")["date"]

        assert (first, second) == ("2026-10-01", "2026-10-02")
