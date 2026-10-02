"""What the assistant can do, as plain functions over the use cases.

They know nothing about any LLM framework: an adapter exposes them to the model. Results are
JSON-ready dicts the model reads, with amounts already formatted as BRL.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from open_assessor.application.usecases.add_expense import (
    AddExpense,
    AddExpenseInput,
    Duplicate,
    Saved,
)
from open_assessor.application.usecases.list_expenses import (
    Listed,
    ListExpenses,
    ListExpensesInput,
)
from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.categories import Category
from open_assessor.domain.dates import Clock, today_in, weekday_in
from open_assessor.domain.expenses.money import format_brl
from open_assessor.ports.tool import ToolContext

MAX_LISTED_EXPENSES = 50
"""Items returned to the model; the summary always covers the whole period."""

type ToolOutput = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ExpenseItem:
    """One expense as the model reports it."""

    amount: float = field(metadata={"description": "Amount in BRL as a decimal number, e.g. 50.9."})
    description: str = field(metadata={"description": "What was bought, as written by the user."})
    category: Category
    date: str | None = field(
        default=None,
        metadata={
            "description": "Day of the expense as YYYY-MM-DD. Omit it when the expense is from today."
        },
    )


async def add_expenses(
    add_expense: AddExpense, context: ToolContext, expenses: Sequence[ExpenseItem]
) -> ToolOutput:
    """Saves each expense on its own, so one invalid item does not block the others."""
    if not expenses:
        return {"results": [{"status": "invalid", "reason": "expenses must be a non-empty array"}]}

    results: list[ToolOutput] = []
    for index, item in enumerate(expenses):
        result = await add_expense.execute(
            AddExpenseInput(
                user_id=context.user_id,
                # One message may hold several expenses; the index keeps their keys apart
                # while a replay of the same message still deduplicates each one.
                message_key=f"{context.message_key}#{index}",
                amount=item.amount,
                description=item.description,
                category=item.category,
                date=item.date,
            )
        )

        match result:
            case Saved(expense):
                results.append(
                    {
                        "status": "saved",
                        "date": expense.date,
                        "amount": format_brl(expense.amount_cents),
                        "description": expense.description,
                        "category": expense.category,
                    }
                )
            case Duplicate():
                results.append({"status": "duplicate"})
            case Invalid(reason):
                results.append({"status": "invalid", "reason": reason})

    return {"results": results}


async def list_expenses(
    list_expenses: ListExpenses,
    context: ToolContext,
    from_: str,
    to: str,
    category: Category | None = None,
) -> ToolOutput:
    result = await list_expenses.execute(
        ListExpensesInput(user_id=context.user_id, from_=from_, to=to, category=category)
    )

    match result:
        case Invalid(reason):
            return {"status": "invalid", "reason": reason}
        case Listed(expenses, summary):
            return {
                "status": "ok",
                "from": from_,
                "to": to,
                "count": summary.count,
                "total": format_brl(summary.total_cents),
                "byCategory": {
                    category: format_brl(cents) for category, cents in summary.by_category.items()
                },
                "expenses": [
                    {
                        "date": e.date,
                        "amount": format_brl(e.amount_cents),
                        "description": e.description,
                        "category": e.category,
                    }
                    for e in expenses[:MAX_LISTED_EXPENSES]
                ],
                "truncated": len(expenses) > MAX_LISTED_EXPENSES,
            }


def current_date(clock: Clock, timezone: str) -> ToolOutput:
    """Read on every call, so a long-running process never goes stale."""
    now = clock()
    return {
        "date": today_in(timezone, now),
        "weekday": weekday_in(timezone, now),
        "timezone": timezone,
    }
