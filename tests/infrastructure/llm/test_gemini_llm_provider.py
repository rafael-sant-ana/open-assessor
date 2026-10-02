from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import types

from open_assessor.infrastructure.llm.gemini_llm_provider import GeminiLLMProvider
from open_assessor.ports.tool import Tool
from tests.infrastructure.llm.fixtures import CTX, BrokenTool, GreeterTool, SpyTool

type Reply = str | list[SimpleNamespace] | None


def call(name: str, args: dict[str, Any] | None = None, id: str = "fc_1") -> list[SimpleNamespace]:
    return [SimpleNamespace(id=id, name=name, args=args or {})]


class FakeChat:
    def __init__(self, replies: list[Reply]) -> None:
        self._replies = replies
        self.sent: list[Any] = []

    async def send_message(self, message: Any) -> SimpleNamespace:
        self.sent.append(message)
        reply = self._replies.pop(0) if self._replies else "ok"
        if isinstance(reply, list):
            return SimpleNamespace(text=None, function_calls=reply)
        return SimpleNamespace(text=reply, function_calls=None)


class FakeGenAI:
    def __init__(self, replies: Sequence[Reply]) -> None:
        self._replies = list(replies)
        self.created: list[dict[str, Any]] = []
        self.chats: list[FakeChat] = []
        self.aio = SimpleNamespace(chats=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> FakeChat:
        self.created.append(kwargs)
        chat = FakeChat(self._replies)
        self.chats.append(chat)
        return chat


def setup(
    *replies: Reply, tools: Sequence[Tool] = (), env: dict[str, str] | None = None
) -> tuple[GeminiLLMProvider, FakeGenAI]:
    client = FakeGenAI(replies)
    provider = GeminiLLMProvider(tools, client=client, env=env if env is not None else {})  # pyright: ignore[reportArgumentType]
    return provider, client


def test_raises_when_gemini_api_key_is_missing_and_no_client_is_given():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiLLMProvider(env={})


async def test_sends_the_message_and_returns_the_reply_text():
    provider, client = setup("olá")

    assert await provider.generate_response("chat", "oi", CTX) == "olá"
    assert client.chats[0].sent == ["oi"]


async def test_reuses_the_same_chat_for_the_same_chat_id():
    provider, client = setup()

    await provider.generate_response("chat", "q1", CTX)
    await provider.generate_response("chat", "q2", CTX)

    assert len(client.created) == 1


async def test_creates_a_separate_chat_per_chat_id():
    provider, client = setup()

    await provider.generate_response("chat-a", "a", CTX)
    await provider.generate_response("chat-b", "b", CTX)

    assert len(client.created) == 2


async def test_uses_gemini_model_when_set():
    provider, client = setup(env={"GEMINI_MODEL": "custom-model"})

    await provider.generate_response("chat", "x", CTX)

    assert client.created[0]["model"] == "custom-model"


async def test_raises_when_the_reply_is_empty():
    provider, _ = setup(None)

    with pytest.raises(RuntimeError, match="empty body"):
        await provider.generate_response("chat", "x", CTX)


class TestTools:
    async def test_does_not_declare_tools_when_none_are_configured(self):
        provider, client = setup()

        await provider.generate_response("chat", "oi", CTX)

        assert client.created[0]["config"].tools is None

    async def test_declares_tools_and_sends_the_function_response_back(self):
        provider, client = setup(
            call("greet", {"name": "Rafa"}), "Olá, Rafa!", tools=[GreeterTool()]
        )

        reply = await provider.generate_response("chat", "hello world", CTX)

        assert reply == "Olá, Rafa!"
        config: types.GenerateContentConfig = client.created[0]["config"]
        [tool] = config.tools or []  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        assert isinstance(tool, types.Tool)
        assert tool.function_declarations
        assert tool.function_declarations[0].name == "greet"
        assert config.automatic_function_calling
        assert config.automatic_function_calling.disable is True
        assert client.chats[0].sent[1] == [
            types.Part(
                function_response=types.FunctionResponse(
                    id="fc_1", name="greet", response={"output": "Hello, Rafa!"}
                )
            )
        ]

    async def test_reports_a_failing_tool_to_the_model_instead_of_raising(self):
        provider, client = setup(call("broken"), "desculpe", tools=[BrokenTool()])

        assert await provider.generate_response("chat", "x", CTX) == "desculpe"
        part: types.Part = client.chats[0].sent[1][0]
        assert part.function_response
        assert part.function_response.response == {"error": "boom"}

    async def test_passes_the_message_context_to_the_tool(self):
        spy = SpyTool()
        provider, _ = setup(call("spy"), "ok", tools=[spy])

        await provider.generate_response("chat", "x", CTX)

        assert spy.seen == [CTX]

    async def test_gives_up_after_too_many_tool_rounds(self):
        provider, _ = setup(*(call("greet") for _ in range(10)), tools=[GreeterTool()])

        with pytest.raises(RuntimeError, match="tool rounds"):
            await provider.generate_response("chat", "x", CTX)
