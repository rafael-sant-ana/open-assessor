import json
import os
from collections.abc import Mapping, Sequence
from typing import cast

from openai import AsyncOpenAI, omit
from openai.types.responses import FunctionToolParam, ResponseInputParam
from openai.types.responses.response_input_param import FunctionCallOutput

from open_assessor.infrastructure.llm.run_tool import (
    MAX_TOOL_ROUNDS,
    TooManyToolRoundsError,
    require_api_key,
    run_tool,
)
from open_assessor.infrastructure.llm.system_prompt import SYSTEM_PROMPT
from open_assessor.ports.tool import Tool, ToolContext

DEFAULT_MODEL = "gpt-5.6-luna"


class OpenAILLMProvider:
    def __init__(
        self,
        tools: Sequence[Tool] = (),
        *,
        client: AsyncOpenAI | None = None,
        env: Mapping[str, str] = os.environ,
    ) -> None:
        self.tools = tuple(tools)
        self._env = env
        self._client = client or AsyncOpenAI(api_key=require_api_key(env, "OPENAI_API_KEY"))
        # The API keeps the history; only the last response of each chat is remembered here.
        self._conversations: dict[str, str] = {}

    async def generate_response(self, chat_id: str, message: str, context: ToolContext) -> str:
        previous_id = self._conversations.get(chat_id)
        input: str | ResponseInputParam = message

        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = await self._client.responses.create(
                model=self._env.get("OPENAI_MODEL", DEFAULT_MODEL),
                instructions=SYSTEM_PROMPT,
                input=input,
                previous_response_id=previous_id or omit,
                tools=self._tool_params() or omit,
            )

            calls = [item for item in response.output or [] if item.type == "function_call"]

            if not calls:
                self._conversations[chat_id] = response.id
                return response.output_text

            outputs: list[FunctionCallOutput] = []
            for call in calls:
                result = await run_tool(
                    self.tools, call.name, _parse_arguments(call.arguments), context
                )
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result.output,
                    }
                )
            input = list(outputs)
            previous_id = response.id

        raise TooManyToolRoundsError()

    def _tool_params(self) -> list[FunctionToolParam]:
        return [
            {
                "type": "function",
                "name": t.name,
                "description": t.description,
                "parameters": dict(t.parameters),
                "strict": False,
            }
            for t in self.tools
        ]


def _parse_arguments(raw: str) -> Mapping[str, object]:
    try:
        parsed: object = json.loads(raw or "{}")
    except ValueError:
        return {}
    return cast("dict[str, object]", parsed) if isinstance(parsed, dict) else {}
