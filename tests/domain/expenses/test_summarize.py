from typing import Any

from open_assessor.domain.expenses.expense import Expense
from open_assessor.domain.expenses.summarize import ExpenseSummary, summarize


def expense(**overrides: Any) -> Expense:
    return Expense(
        **{
            "date": "2026-10-01",
            "amount_cents": 1000,
            "description": "x",
            "category": "outros",
            "user_id": "telegram:1",
            "message_key": "telegram:1:1#0",
            "created_at": "2026-10-01T12:00:00.000Z",
            **overrides,
        }
    )


def test_returns_zeros_for_no_expenses():
    assert summarize([]) == ExpenseSummary(count=0, total_cents=0, by_category={})


def test_totals_everything_and_per_category():
    result = summarize(
        [
            expense(amount_cents=5000, category="alimentacao"),
            expense(amount_cents=2500, category="alimentacao"),
            expense(amount_cents=1000, category="transporte"),
        ]
    )

    assert result == ExpenseSummary(
        count=3,
        total_cents=8500,
        by_category={"alimentacao": 7500, "transporte": 1000},
    )
