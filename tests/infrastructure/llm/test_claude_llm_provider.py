from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from anthropic import Omit

from open_assessor.infrastructure.llm.claude_llm_provider import ClaudeLLMProvider
from open_assessor.ports.tool import Tool
from tests.infrastructure.llm.fixtures import CTX, BrokenTool, GreeterTool, SpyTool

type Reply = list[SimpleNamespace] | Exception


def text(t: str) -> list[SimpleNamespace]:
    return [SimpleNamespace(type="text", text=t)]


def tool_use(name: str, input: dict[str, Any], id: str = "tu_1") -> list[SimpleNamespace]:
    return [SimpleNamespace(type="tool_use", id=id, name=name, input=input)]


class FakeAnthropic:
    def __init__(self, replies: Sequence[Reply]) -> None:
        self._replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **request: Any) -> SimpleNamespace:
        sent = {k: v for k, v in request.items() if not isinstance(v, Omit)}
        # Copy the list: the provider keeps appending to the one it sent.
        self.requests.append({**sent, "messages": list(sent["messages"])})
        reply = self._replies.pop(0) if self._replies else text("ok")
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(content=reply)


def setup(
    *replies: Reply, tools: Sequence[Tool] = (), env: dict[str, str] | None = None
) -> tuple[ClaudeLLMProvider, FakeAnthropic]:
    client = FakeAnthropic(replies)
    provider = ClaudeLLMProvider(tools, client=client, env=env if env is not None else {})  # pyright: ignore[reportArgumentType]
    return provider, client


def test_raises_when_anthropic_api_key_is_missing_and_no_client_is_given():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        ClaudeLLMProvider(env={})


async def test_returns_the_reply_text_and_sends_the_user_message():
    provider, client = setup(text("olá"))

    assert await provider.generate_response("chat", "oi", CTX) == "olá"
    assert client.requests[0]["messages"] == [{"role": "user", "content": "oi"}]


async def test_sends_the_previous_turns_on_the_next_call():
    provider, client = setup(text("a1"), text("a2"))

    await provider.generate_response("chat", "q1", CTX)
    await provider.generate_response("chat", "q2", CTX)

    assert client.requests[1]["messages"] == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]


async def test_keeps_conversations_isolated_per_chat():
    provider, client = setup(text("a1"), text("b1"))

    await provider.generate_response("chat-a", "from a", CTX)
    await provider.generate_response("chat-b", "from b", CTX)

    assert client.requests[1]["messages"] == [{"role": "user", "content": "from b"}]


async def test_joins_text_blocks_and_ignores_other_block_types():
    provider, _ = setup(
        [
            SimpleNamespace(type="text", text="foo"),
            SimpleNamespace(type="thinking"),
            SimpleNamespace(type="text", text="bar"),
        ]
    )

    assert await provider.generate_response("chat", "x", CTX) == "foobar"


async def test_raises_on_an_empty_reply_without_storing_the_turn():
    provider, client = setup([], text("fine"))

    with pytest.raises(RuntimeError, match="empty body"):
        await provider.generate_response("chat", "lost", CTX)
    await provider.generate_response("chat", "next", CTX)

    assert client.requests[1]["messages"] == [{"role": "user", "content": "next"}]


async def test_does_not_store_the_turn_when_the_api_call_fails():
    provider, client = setup(RuntimeError("429"), text("fine"))

    with pytest.raises(RuntimeError, match="429"):
        await provider.generate_response("chat", "lost", CTX)
    await provider.generate_response("chat", "next", CTX)

    assert client.requests[1]["messages"] == [{"role": "user", "content": "next"}]


async def test_caps_history_at_20_messages_and_starts_on_a_user_turn():
    provider, client = setup()

    for i in range(12):
        await provider.generate_response("chat", f"q{i}", CTX)
    await provider.generate_response("chat", "last", CTX)

    messages = client.requests[12]["messages"]
    # 20 stored messages + the new user message
    assert len(messages) == 21
    assert messages[0]["role"] == "user"
    assert messages[-1]["content"] == "last"


async def test_uses_anthropic_model_when_set_and_a_default_otherwise():
    env: dict[str, str] = {}
    provider, client = setup(env=env)

    await provider.generate_response("chat", "a", CTX)
    env["ANTHROPIC_MODEL"] = "custom-model"
    await provider.generate_response("chat", "b", CTX)

    assert client.requests[0]["model"] == "claude-haiku-4-5-20251001"
    assert client.requests[1]["model"] == "custom-model"


class TestTools:
    async def test_does_not_send_a_tools_field_when_none_are_configured(self):
        provider, client = setup()

        await provider.generate_response("chat", "oi", CTX)

        assert "tools" not in client.requests[0]

    async def test_runs_the_requested_tool_and_returns_the_final_reply(self):
        provider, client = setup(
            tool_use("greet", {"name": "Rafa"}), text("Olá, Rafa!"), tools=[GreeterTool()]
        )

        reply = await provider.generate_response("chat", "hello world, sou o Rafa", CTX)

        assert reply == "Olá, Rafa!"
        assert client.requests[1]["tools"][0]["name"] == "greet"
        _, assistant, result = client.requests[1]["messages"]
        assert assistant["role"] == "assistant"
        assert result == {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "Hello, Rafa!"}],
        }

    async def test_reports_a_failing_tool_to_the_model_instead_of_raising(self):
        provider, client = setup(tool_use("broken", {}), text("desculpe"), tools=[BrokenTool()])

        assert await provider.generate_response("chat", "x", CTX) == "desculpe"
        result = client.requests[1]["messages"][2]["content"][0]
        assert result["is_error"] is True
        assert result["content"] == "boom"

    async def test_reports_an_unknown_tool_to_the_model(self):
        provider, client = setup(tool_use("nope", {}), text("ok"))

        await provider.generate_response("chat", "x", CTX)

        assert client.requests[1]["messages"][2]["content"][0]["is_error"] is True

    async def test_passes_the_message_context_to_the_tool(self):
        spy = SpyTool()
        provider, _ = setup(tool_use("spy", {}), text("ok"), tools=[spy])

        await provider.generate_response("chat", "x", CTX)

        assert spy.seen == [CTX]

    async def test_gives_up_after_too_many_tool_rounds(self):
        provider, _ = setup(*(tool_use("greet", {}) for _ in range(10)), tools=[GreeterTool()])

        with pytest.raises(RuntimeError, match="tool rounds"):
            await provider.generate_response("chat", "x", CTX)

    async def test_never_starts_the_history_on_an_orphaned_tool_result(self):
        provider, client = setup(tool_use("greet", {}), tools=[GreeterTool()])

        await provider.generate_response("chat", "hello world", CTX)
        for i in range(12):
            await provider.generate_response("chat", f"q{i}", CTX)

        for request in client.requests:
            first = request["messages"][0]
            assert first["role"] == "user"
            assert isinstance(first["content"], str)
