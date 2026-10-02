import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from open_assessor.ports.tool import Tool, ToolContext

MAX_TOOL_ROUNDS = 5
"""Upper bound of model → tool → model round trips for a single user message."""

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolResult:
    output: str
    is_error: bool


async def run_tool(
    tools: Sequence[Tool],
    name: str,
    args: Mapping[str, object],
    context: ToolContext,
) -> ToolResult:
    """Runs a tool the model asked for. Failures become results so the model can recover."""
    tool = next((t for t in tools if t.name == name), None)
    if tool is None:
        return ToolResult(f"Unknown tool: {name}", is_error=True)

    try:
        return ToolResult(await tool.execute(args, context), is_error=False)
    except Exception as error:
        _logger.exception("Tool %s failed", name)
        return ToolResult(str(error), is_error=True)


class TooManyToolRoundsError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(f"Failed to generate response: more than {MAX_TOOL_ROUNDS} tool rounds")


class EmptyResponseError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Failed to generate response: empty body")


def require_api_key(env: Mapping[str, str], variable: str) -> str:
    key = env.get(variable)
    if not key:
        raise ValueError(
            f"Missing required environment variable: {variable}. Check the .env.example"
        )
    return key
