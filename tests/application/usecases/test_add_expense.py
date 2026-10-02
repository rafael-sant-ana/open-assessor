import dataclasses
import re
from datetime import UTC, datetime
from typing import Any

import pytest

from open_assessor.application.usecases.add_expense import (
    AddExpense,
    AddExpenseInput,
    Duplicate,
    Saved,
)
from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.dates import DateRange
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)

# 02:30 UTC on Oct 2nd is still Oct 1st in São Paulo.
NOW = datetime(2026, 10, 2, 2, 30, tzinfo=UTC)


def make_input(**overrides: Any) -> AddExpenseInput:
    fields: dict[str, Any] = {
        "user_id": "telegram:1",
        "message_key": "telegram:10:100#0",
        "amount": 50.9,
        "description": " burger king ",
        "category": "alimentacao",
        **overrides,
    }
    return AddExpenseInput(**fields)


@pytest.fixture
def repository() -> InMemoryExpenseRepository:
    return InMemoryExpenseRepository()


@pytest.fixture
def add_expense(repository: InMemoryExpenseRepository) -> AddExpense:
    return AddExpense(repository, lambda: NOW)


async def test_saves_a_normalized_expense_dated_today_in_the_configured_timezone(
    add_expense: AddExpense, repository: InMemoryExpenseRepository
):
    result = await add_expense.execute(make_input())

    assert isinstance(result, Saved)
    assert dataclasses.asdict(result.expense) == {
        "date": "2026-10-01",
        "amount_cents": 5090,
        "description": "burger king",
        "category": "alimentacao",
        "user_id": "telegram:1",
        "message_key": "telegram:10:100#0",
        "created_at": "2026-10-02T02:30:00.000Z",
    }
    assert result.expense.currency == "BRL"
    assert await repository.exists_by_message_key("telegram:10:100#0")


async def test_uses_the_given_date(add_expense: AddExpense):
    result = await add_expense.execute(make_input(date="2026-09-30"))

    assert isinstance(result, Saved)
    assert result.expense.date == "2026-09-30"


async def test_does_not_write_twice_for_a_replayed_message_key(
    add_expense: AddExpense, repository: InMemoryExpenseRepository
):
    await add_expense.execute(make_input())
    result = await add_expense.execute(make_input(amount=99))

    assert result == Duplicate()
    saved = await repository.list_by("telegram:1", DateRange("2026-01-01", "2026-12-31"))
    assert len(saved) == 1
    assert saved[0].amount_cents == 5090


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        pytest.param({"amount": None}, "amount", id="a missing amount"),
        pytest.param({"amount": 0}, "amount", id="a zero amount"),
        pytest.param({"amount": -3}, "amount", id="a negative amount"),
        pytest.param({"amount": "50"}, "amount", id="a string amount"),
        pytest.param({"description": "   "}, "description", id="a blank description"),
        pytest.param({"description": None}, "description", id="a missing description"),
        pytest.param({"category": "viagem"}, "category", id="an unknown category"),
        pytest.param({"date": "2026-02-30"}, "date", id="an impossible date"),
        pytest.param({"date": "30/09/2026"}, "date", id="a badly formatted date"),
    ],
)
async def test_rejects_invalid_input_without_writing(
    add_expense: AddExpense,
    repository: InMemoryExpenseRepository,
    overrides: dict[str, Any],
    reason: str,
):
    result = await add_expense.execute(make_input(**overrides))

    assert isinstance(result, Invalid)
    assert re.search(reason, result.reason)
    assert not await repository.exists_by_message_key("telegram:10:100#0")
