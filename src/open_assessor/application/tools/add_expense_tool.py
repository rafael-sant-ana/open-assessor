from collections.abc import Mapping
from typing import cast

from open_assessor.application.tools._json import to_json
from open_assessor.application.usecases.add_expense import (
    AddExpense,
    AddExpenseInput,
    Duplicate,
    Saved,
)
from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.categories import CATEGORIES
from open_assessor.domain.expenses.money import format_brl
from open_assessor.ports.tool import ToolContext


class AddExpenseTool:
    name = "add_expense"
    description = (
        'Records one or more expenses the user just told you about (e.g. "gastei 50 no burger king"). '
        "Call it once with every expense mentioned in the message. "
        "Never guess a missing amount or description: ask the user instead of calling this tool. "
        "The result says what was saved, duplicated or rejected; confirm to the user what was saved."
    )
    parameters: Mapping[str, object] = {
        "type": "object",
        "properties": {
            "expenses": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": "number",
                            "description": "Amount in BRL as a decimal number, e.g. 50.9.",
                        },
                        "description": {
                            "type": "string",
                            "description": "What was bought, as written by the user.",
                        },
                        "category": {"type": "string", "enum": list(CATEGORIES)},
                        "date": {
                            "type": "string",
                            "description": (
                                "Day of the expense as YYYY-MM-DD. "
                                "Omit it when the expense is from today."
                            ),
                        },
                    },
                    "required": ["amount", "description", "category"],
                },
            },
        },
        "required": ["expenses"],
    }

    def __init__(self, add_expense: AddExpense) -> None:
        self._add_expense = add_expense

    async def execute(self, args: Mapping[str, object], context: ToolContext) -> str:
        expenses = args.get("expenses")
        if not isinstance(expenses, list) or not expenses:
            return to_json(
                {"results": [{"status": "invalid", "reason": "expenses must be a non-empty array"}]}
            )

        results: list[dict[str, object]] = []
        for index, item in enumerate(cast("list[object]", expenses)):
            fields = cast("dict[str, object]", item) if isinstance(item, dict) else {}
            result = await self._add_expense.execute(
                AddExpenseInput(
                    user_id=context.user_id,
                    # One message may hold several expenses; the index keeps their keys apart
                    # while a replay of the same message still deduplicates each one.
                    message_key=f"{context.message_key}#{index}",
                    amount=fields.get("amount"),
                    description=fields.get("description"),
                    category=fields.get("category"),
                    date=fields.get("date"),
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

        return to_json({"results": results})
