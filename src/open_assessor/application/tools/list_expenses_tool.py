from collections.abc import Mapping

from open_assessor.application.tools._json import to_json
from open_assessor.application.usecases.list_expenses import (
    Listed,
    ListExpenses,
    ListExpensesInput,
)
from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.categories import CATEGORIES
from open_assessor.domain.expenses.money import format_brl
from open_assessor.ports.tool import ToolContext

MAX_LISTED_EXPENSES = 50
"""Items returned to the model; the summary always covers the whole period."""


class ListExpensesTool:
    name = "list_expenses"
    description = (
        "Looks up the user's recorded expenses in a period and returns the total, "
        "the total per category and the expenses. "
        'Call it when the user asks how much they spent (e.g. "quanto gastei esse mês?"). '
        "Work out `from` and `to` from the date returned by get_current_date. "
        "Both days are included."
    )
    parameters: Mapping[str, object] = {
        "type": "object",
        "properties": {
            "from": {"type": "string", "description": "First day, YYYY-MM-DD."},
            "to": {"type": "string", "description": "Last day, YYYY-MM-DD."},
            "category": {
                "type": "string",
                "enum": list(CATEGORIES),
                "description": "Only expenses of this category. Omit for all.",
            },
        },
        "required": ["from", "to"],
    }

    def __init__(self, list_expenses: ListExpenses) -> None:
        self._list_expenses = list_expenses

    async def execute(self, args: Mapping[str, object], context: ToolContext) -> str:
        result = await self._list_expenses.execute(
            ListExpensesInput(
                user_id=context.user_id,
                from_=args.get("from"),
                to=args.get("to"),
                category=args.get("category"),
            )
        )

        match result:
            case Invalid(reason):
                return to_json({"status": "invalid", "reason": reason})
            case Listed(expenses, summary):
                return to_json(
                    {
                        "status": "ok",
                        "from": args.get("from"),
                        "to": args.get("to"),
                        "count": summary.count,
                        "total": format_brl(summary.total_cents),
                        "byCategory": {
                            category: format_brl(cents)
                            for category, cents in summary.by_category.items()
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
                )
