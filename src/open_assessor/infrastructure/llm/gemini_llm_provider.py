import os
from collections.abc import Mapping, Sequence

from google.genai import Client, types
from google.genai.chats import AsyncChat

from open_assessor.infrastructure.llm.run_tool import (
    MAX_TOOL_ROUNDS,
    EmptyResponseError,
    ToolResult,
    TooManyToolRoundsError,
    require_api_key,
    run_tool,
)
from open_assessor.infrastructure.llm.system_prompt import SYSTEM_PROMPT
from open_assessor.ports.tool import Tool, ToolContext

DEFAULT_MODEL = "gemini-3.6-flash"


class GeminiLLMProvider:
    def __init__(
        self,
        tools: Sequence[Tool] = (),
        *,
        client: Client | None = None,
        env: Mapping[str, str] = os.environ,
    ) -> None:
        self.tools = tuple(tools)
        self._env = env
        self._client = client or Client(api_key=require_api_key(env, "GEMINI_API_KEY"))
        # TODO: forget chats unused for a long time (they grow without bound).
        self._conversations: dict[str, AsyncChat] = {}

    async def generate_response(self, chat_id: str, message: str, context: ToolContext) -> str:
        chat = self._conversations.get(chat_id)
        if chat is None:
            chat = self._client.aio.chats.create(
                model=self._env.get("GEMINI_MODEL", DEFAULT_MODEL),
                config=self._build_config(),
            )
            self._conversations[chat_id] = chat

        # google-genai's own annotations leave part of send_message's signature unknown.
        response = await chat.send_message(message)  # pyright: ignore[reportUnknownMemberType]

        for round in range(MAX_TOOL_ROUNDS + 1):
            calls = response.function_calls or []
            if not calls:
                break
            if round >= MAX_TOOL_ROUNDS:
                raise TooManyToolRoundsError()

            parts: list[types.Part] = []
            for call in calls:
                name = call.name or ""
                result = await run_tool(self.tools, name, call.args or {}, context)
                parts.append(_function_response(call.id, name, result))

            response = await chat.send_message(parts)  # pyright: ignore[reportUnknownMemberType]

        if not response.text:
            raise EmptyResponseError()

        return response.text

    def _build_config(self) -> types.GenerateContentConfig:
        if not self.tools:
            return types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)

        return types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters_json_schema=t.parameters,
                        )
                        for t in self.tools
                    ]
                )
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )


def _function_response(call_id: str | None, name: str, result: ToolResult) -> types.Part:
    return types.Part(
        function_response=types.FunctionResponse(
            id=call_id,
            name=name,
            response={"error": result.output} if result.is_error else {"output": result.output},
        )
    )
