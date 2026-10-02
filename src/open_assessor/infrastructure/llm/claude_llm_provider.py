import os
from collections.abc import Mapping, Sequence

from anthropic import AsyncAnthropic, omit
from anthropic.types import MessageParam, ToolParam, ToolResultBlockParam

from open_assessor.infrastructure.llm.run_tool import (
    MAX_TOOL_ROUNDS,
    EmptyResponseError,
    TooManyToolRoundsError,
    require_api_key,
    run_tool,
)
from open_assessor.infrastructure.llm.system_prompt import SYSTEM_PROMPT
from open_assessor.ports.tool import Tool, ToolContext

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_HISTORY_MESSAGES = 20


class ClaudeLLMProvider:
    def __init__(
        self,
        tools: Sequence[Tool] = (),
        *,
        client: AsyncAnthropic | None = None,
        env: Mapping[str, str] = os.environ,
    ) -> None:
        self.tools = tuple(tools)
        self._env = env
        self._client = client or AsyncAnthropic(api_key=require_api_key(env, "ANTHROPIC_API_KEY"))
        # TODO: forget conversations unused for a long time (they grow without bound).
        self._conversations: dict[str, list[MessageParam]] = {}

    async def generate_response(self, chat_id: str, message: str, context: ToolContext) -> str:
        messages: list[MessageParam] = [
            *self._conversations.get(chat_id, []),
            {"role": "user", "content": message},
        ]

        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = await self._client.messages.create(
                model=self._env.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=self._tool_params() or omit,
            )

            tool_uses = [block for block in response.content if block.type == "tool_use"]

            if not tool_uses:
                text = "".join(block.text for block in response.content if block.type == "text")
                if not text:
                    raise EmptyResponseError()

                self._conversations[chat_id] = _trim(
                    [*messages, {"role": "assistant", "content": text}]
                )
                return text

            results: list[ToolResultBlockParam] = []
            for tool_use in tool_uses:
                result = await run_tool(self.tools, tool_use.name, tool_use.input, context)
                block: ToolResultBlockParam = {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result.output,
                }
                if result.is_error:
                    block["is_error"] = True
                results.append(block)

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": results})

        raise TooManyToolRoundsError()

    def _tool_params(self) -> list[ToolParam]:
        return [
            {"name": t.name, "description": t.description, "input_schema": dict(t.parameters)}
            for t in self.tools
        ]


def _trim(messages: list[MessageParam]) -> list[MessageParam]:
    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    # The API requires the conversation to start with a plain user turn:
    # not an assistant turn, and not a tool_result whose tool_use was cut off.
    while trimmed and not (trimmed[0]["role"] == "user" and isinstance(trimmed[0]["content"], str)):
        trimmed.pop(0)
    return trimmed
