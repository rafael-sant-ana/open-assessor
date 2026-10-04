from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import UsageLimits

from open_assessor.infrastructure.llm.system_prompt import SYSTEM_PROMPT
from open_assessor.ports.tool import ToolContext

MAX_TOOL_ROUNDS = 5
"""Upper bound of model → tool → model round trips for a single user message."""
MAX_HISTORY_MESSAGES = 20
RETRIES = 2
"""How often the model may fix tool arguments that do not match the schema, or an empty reply."""


class PydanticAIProvider:
    """`LLMProvider` for any model pydantic-ai supports. Keeps each chat's history itself."""

    def __init__(
        self, model: Model | str, toolsets: list[AbstractToolset[ToolContext]] | None = None
    ) -> None:
        self._agent = Agent[ToolContext, str](
            model,
            deps_type=ToolContext,
            # Instructions are sent with every request and never stored in the history,
            # so trimming the history can not drop them.
            instructions=SYSTEM_PROMPT,
            toolsets=toolsets,
            retries=RETRIES,
        )
        # TODO: forget conversations unused for a long time (they grow without bound).
        self._conversations: dict[str, list[ModelMessage]] = {}

    async def generate_response(self, chat_id: str, message: str, context: ToolContext) -> str:
        result = await self._agent.run(
            message,
            deps=context,
            message_history=self._conversations.get(chat_id, []),
            # One request per tool round, plus the one that answers.
            usage_limits=UsageLimits(request_limit=MAX_TOOL_ROUNDS + 1),
        )
        # Stored only once the run succeeded, so a failed turn is not replayed later.
        # An empty reply never gets here: pydantic-ai asks the model again, then raises.
        self._conversations[chat_id] = _trim(result.all_messages())
        return result.output


def _trim(messages: list[ModelMessage]) -> list[ModelMessage]:
    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    # The history must start on a plain user turn: not a model response, and not a tool
    # result whose tool call was cut off.
    while trimmed and not _is_user_turn(trimmed[0]):
        trimmed.pop(0)
    return trimmed


def _is_user_turn(message: ModelMessage) -> bool:
    return (
        isinstance(message, ModelRequest)
        and any(isinstance(part, UserPromptPart) for part in message.parts)
        and not any(isinstance(part, ToolReturnPart) for part in message.parts)
    )
