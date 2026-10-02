import json
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from openai import Omit

from open_assessor.infrastructure.llm.openai_llm_provider import OpenAILLMProvider
from open_assessor.ports.tool import Tool
from tests.infrastructure.llm.fixtures import CTX, BrokenTool, GreeterTool, SpyTool


def function_call(name: str, args: object, call_id: str = "call_1") -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call", name=name, call_id=call_id, arguments=json.dumps(args)
    )


class FakeOpenAI:
    def __init__(self, outputs: Sequence[list[SimpleNamespace]]) -> None:
        self._outputs = list(outputs)
        self._counter = 0
        self.requests: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **request: Any) -> SimpleNamespace:
        self.requests.append({k: v for k, v in request.items() if not isinstance(v, Omit)})
        self._counter += 1
        return SimpleNamespace(
            id=f"resp_{self._counter}",
            output=self._outputs.pop(0) if self._outputs else [],
            output_text=f"reply {self._counter}",
        )


def setup(
    outputs: Sequence[list[SimpleNamespace]] = (),
    tools: Sequence[Tool] = (),
    env: dict[str, str] | None = None,
) -> tuple[OpenAILLMProvider, FakeOpenAI]:
    client = FakeOpenAI(outputs)
    provider = OpenAILLMProvider(tools, client=client, env=env if env is not None else {})  # pyright: ignore[reportArgumentType]
    return provider, client


def test_raises_when_openai_api_key_is_missing_and_no_client_is_given():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAILLMProvider(env={})


async def test_returns_the_output_text_without_a_previous_response_id_at_first():
    provider, client = setup()

    assert await provider.generate_response("chat", "oi", CTX) == "reply 1"
    assert client.requests[0]["input"] == "oi"
    assert "previous_response_id" not in client.requests[0]


async def test_chains_the_previous_response_id_on_the_next_call():
    provider, client = setup()

    await provider.generate_response("chat", "q1", CTX)
    await provider.generate_response("chat", "q2", CTX)

    assert client.requests[1]["previous_response_id"] == "resp_1"


async def test_does_not_share_response_ids_between_chats():
    provider, client = setup()

    await provider.generate_response("chat-a", "a", CTX)
    await provider.generate_response("chat-b", "b", CTX)

    assert "previous_response_id" not in client.requests[1]


async def test_uses_openai_model_when_set():
    provider, client = setup(env={"OPENAI_MODEL": "custom-model"})

    await provider.generate_response("chat", "x", CTX)

    assert client.requests[0]["model"] == "custom-model"


class TestTools:
    async def test_does_not_send_a_tools_field_when_none_are_configured(self):
        provider, client = setup()

        await provider.generate_response("chat", "oi", CTX)

        assert "tools" not in client.requests[0]

    async def test_runs_the_requested_tool_and_sends_its_output_back(self):
        provider, client = setup([[function_call("greet", {"name": "Rafa"})]], [GreeterTool()])

        reply = await provider.generate_response("chat", "hello world", CTX)

        assert reply == "reply 2"
        assert client.requests[0]["tools"][0]["name"] == "greet"
        assert client.requests[0]["tools"][0]["type"] == "function"
        assert client.requests[1]["previous_response_id"] == "resp_1"
        assert client.requests[1]["input"] == [
            {"type": "function_call_output", "call_id": "call_1", "output": "Hello, Rafa!"}
        ]

    async def test_chains_the_next_user_message_to_the_final_response_not_the_tool_round(self):
        provider, client = setup([[function_call("greet", {})]], [GreeterTool()])

        await provider.generate_response("chat", "hello world", CTX)
        await provider.generate_response("chat", "obrigado", CTX)

        assert client.requests[2]["previous_response_id"] == "resp_2"

    async def test_tolerates_malformed_arguments(self):
        malformed = SimpleNamespace(
            type="function_call", name="greet", call_id="c", arguments="{oops"
        )
        provider, client = setup([[malformed]], [GreeterTool()])

        await provider.generate_response("chat", "x", CTX)

        assert client.requests[1]["input"][0]["output"] == "Hello, World!"

    async def test_reports_a_failing_tool_to_the_model_instead_of_raising(self):
        provider, client = setup([[function_call("broken", {})]], [BrokenTool()])

        assert await provider.generate_response("chat", "x", CTX) == "reply 2"
        assert client.requests[1]["input"][0]["output"] == "boom"

    async def test_passes_the_message_context_to_the_tool(self):
        spy = SpyTool()
        provider, _ = setup([[function_call("spy", {})]], [spy])

        await provider.generate_response("chat", "x", CTX)

        assert spy.seen == [CTX]

    async def test_gives_up_after_too_many_tool_rounds(self):
        provider, _ = setup([[function_call("greet", {})] for _ in range(10)], [GreeterTool()])

        with pytest.raises(RuntimeError, match="tool rounds"):
            await provider.generate_response("chat", "x", CTX)
