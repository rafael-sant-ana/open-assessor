from typing import Any

from open_assessor.domain.expenses.expense import Expense


def make_expense(**overrides: Any) -> Expense:
    """A valid expense; override only what the test is about."""
    return Expense(
        **{
            "date": "2026-10-01",
            "amount_cents": 5090,
            "description": "burger king",
            "category": "alimentacao",
            "user_id": "telegram:1",
            "message_key": "telegram:10:100#0",
            "created_at": "2026-10-01T12:00:00.000Z",
            **overrides,
        }
    )
