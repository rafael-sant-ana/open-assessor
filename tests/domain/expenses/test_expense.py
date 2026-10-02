import dataclasses
import re
from typing import Any

import pytest

from open_assessor.domain.dates import DateRange
from open_assessor.domain.expenses.expense import Expense, InvalidExpenseError
from open_assessor.domain.expenses.money import MAX_AMOUNT_CENTS


def props(**overrides: Any) -> dict[str, Any]:
    return {
        "date": "2026-10-01",
        "amount_cents": 5090,
        "description": "burger king",
        "category": "alimentacao",
        "user_id": "telegram:1",
        "message_key": "telegram:10:100#0",
        "created_at": "2026-10-01T12:00:00.000Z",
        **overrides,
    }


class TestConstruction:
    def test_keeps_the_given_values_and_always_uses_brl(self):
        expense = Expense(**props())

        assert expense.date == "2026-10-01"
        assert expense.amount_cents == 5090
        assert expense.currency == "BRL"
        assert expense.description == "burger king"
        assert expense.category == "alimentacao"
        assert expense.user_id == "telegram:1"
        assert expense.message_key == "telegram:10:100#0"
        assert expense.created_at == "2026-10-01T12:00:00.000Z"

    def test_trims_the_description(self):
        assert Expense(**props(description="  uber  ")).description == "uber"

    def test_accepts_the_largest_allowed_amount(self):
        assert Expense(**props(amount_cents=MAX_AMOUNT_CENTS)).amount_cents == MAX_AMOUNT_CENTS

    @pytest.mark.parametrize(
        ("overrides", "reason"),
        [
            pytest.param({"amount_cents": 0}, "amount", id="a zero amount"),
            pytest.param({"amount_cents": -1}, "amount", id="a negative amount"),
            pytest.param({"amount_cents": 10.5}, "amount", id="a fractional amount of cents"),
            pytest.param(
                {"amount_cents": MAX_AMOUNT_CENTS + 1}, "amount", id="an amount above the cap"
            ),
            pytest.param({"amount_cents": "5090"}, "amount", id="a string amount"),
            pytest.param({"amount_cents": None}, "amount", id="a missing amount"),
            pytest.param({"amount_cents": True}, "amount", id="a boolean amount"),
            pytest.param({"description": "   "}, "description", id="a blank description"),
            pytest.param({"description": 50}, "description", id="a non-string description"),
            pytest.param(
                {"category": "viagem"},
                "category must be one of: alimentacao",
                id="an unknown category",
            ),
            pytest.param({"date": "2026-02-30"}, "date", id="an impossible date"),
            pytest.param({"date": "30/09/2026"}, "date", id="a badly formatted date"),
            pytest.param({"user_id": ""}, "userId", id="an empty userId"),
            pytest.param({"message_key": ""}, "messageKey", id="an empty messageKey"),
            pytest.param({"created_at": "ontem"}, "createdAt", id="an unparseable createdAt"),
            pytest.param({"created_at": 123}, "createdAt", id="a non-string createdAt"),
        ],
    )
    def test_rejects_invalid_values(self, overrides: dict[str, Any], reason: str):
        with pytest.raises(InvalidExpenseError, match=re.escape(reason)):
            Expense(**props(**overrides))


class TestBehavior:
    expense = Expense(**props(date="2026-10-15"))

    def test_knows_who_it_belongs_to(self):
        assert self.expense.belongs_to("telegram:1")
        assert not self.expense.belongs_to("telegram:2")

    def test_knows_whether_it_falls_in_a_date_range_ends_included(self):
        assert self.expense.occurs_within(DateRange("2026-10-01", "2026-10-31"))
        assert self.expense.occurs_within(DateRange("2026-10-15", "2026-10-15"))
        assert not self.expense.occurs_within(DateRange("2026-10-16", "2026-10-31"))
        assert not self.expense.occurs_within(DateRange("2026-09-01", "2026-10-14"))

    def test_knows_its_category(self):
        assert self.expense.has_category("alimentacao")
        assert not self.expense.has_category("lazer")


def test_cannot_be_changed_after_construction():
    expense = Expense(**props())

    with pytest.raises(dataclasses.FrozenInstanceError):
        expense.amount_cents = 1  # type: ignore[misc]


def test_equal_when_all_fields_are_equal():
    assert Expense(**props()) == Expense(**props())
    assert Expense(**props()) != Expense(**props(amount_cents=1))
