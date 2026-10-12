"""Exposes the assistant tools to pydantic-ai, with typed arguments it turns into schemas."""

import logging
from collections.abc import Awaitable
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext, Tool
from pydantic_ai.toolsets import FunctionToolset

from open_assessor.application import assistant_tools
from open_assessor.application.assistant_tools import ExpenseItem, ToolOutput
from open_assessor.application.usecases.add_expense import AddExpense
from open_assessor.application.usecases.list_expenses import ListExpenses
from open_assessor.domain.categories import Category
from open_assessor.domain.dates import Clock
from open_assessor.ports.tool import ToolContext

_logger = logging.getLogger(__name__)

ADD_EXPENSE_DESCRIPTION = (
    'Records one or more expenses the user just told you about (e.g. "gastei 50 no burger king"). '
    "Call it once with every expense mentioned in the message. "
    "Never guess a missing amount or description: ask the user instead of calling this tool. "
    "The result says what was saved, duplicated or rejected; confirm to the user what was saved."
)
LIST_EXPENSES_DESCRIPTION = (
    "Looks up the user's recorded expenses in a period and returns the total, "
    "the total per category and the expenses. "
    'Call it when the user asks how much they spent (e.g. "quanto gastei esse mês?"). '
    "Work out `from_date` and `to_date` from the date returned by get_current_date. "
    "Both days are included."
)
GET_CURRENT_DATE_DESCRIPTION = (
    "Returns today's date and weekday. Call it before resolving any relative date or period "
    '("hoje", "ontem", "sexta passada", "esse mês", "semana passada") '
    "for add_expense or list_expenses."
)


def build_toolset(
    add_expense: AddExpense, list_expenses: ListExpenses, clock: Clock, timezone: str
) -> FunctionToolset[ToolContext]:
    async def add_expense_tool(
        ctx: RunContext[ToolContext],
        expenses: Annotated[list[ExpenseItem], Field(min_length=1)],
    ) -> ToolOutput:
        return await _reporting_errors(
            assistant_tools.add_expenses(add_expense, ctx.deps, expenses)
        )

    async def list_expenses_tool(
        ctx: RunContext[ToolContext],
        from_date: Annotated[str, Field(description="First day, YYYY-MM-DD.")],
        to_date: Annotated[str, Field(description="Last day, YYYY-MM-DD.")],
        category: Annotated[
            Category | None, Field(description="Only expenses of this category. Omit for all.")
        ] = None,
    ) -> ToolOutput:
        return await _reporting_errors(
            assistant_tools.list_expenses(list_expenses, ctx.deps, from_date, to_date, category)
        )

    def get_current_date_tool() -> ToolOutput:
        return assistant_tools.current_date(clock, timezone)

    return FunctionToolset[ToolContext](
        [
            Tool(add_expense_tool, name="add_expense", description=ADD_EXPENSE_DESCRIPTION),
            Tool(list_expenses_tool, name="list_expenses", description=LIST_EXPENSES_DESCRIPTION),
            Tool(
                get_current_date_tool,
                name="get_current_date",
                description=GET_CURRENT_DATE_DESCRIPTION,
            ),
        ]
    )


async def _reporting_errors(operation: Awaitable[ToolOutput]) -> ToolOutput:
    """A failure (e.g. Sheets is down) becomes a result, so the model can tell the user that
    nothing was saved. It is deliberately not retried: the model decides what to do next."""
    try:
        return await operation
    except Exception as error:
        _logger.exception("Tool failed")
        return {"status": "error", "reason": str(error) or type(error).__name__}
