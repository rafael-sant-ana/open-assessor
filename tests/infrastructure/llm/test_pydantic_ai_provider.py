from collections.abc import Sequence

import pytest
from pydantic_ai import RunContext, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart
from pydantic_ai.toolsets import FunctionToolset

from open_assessor.infrastructure.llm.pydantic_ai_provider import PydanticAIProvider
from open_assessor.infrastructure.llm.system_prompt import SYSTEM_PROMPT
from open_assessor.ports.tool import ToolContext
from tests.infrastructure.llm.scripted_model import ScriptedModel, Step, call, text

CTX = ToolContext(user_id="telegram:1", message_key="telegram:10:100")


def greeter_toolset(seen: list[ToolContext] | None = None) -> FunctionToolset[ToolContext]:
    toolset = FunctionToolset[ToolContext]()

    @toolset.tool
    def greet(ctx: RunContext[ToolContext], name: str = "World") -> str:  # pyright: ignore[reportUnusedFunction]
        """Greets someone."""
        if seen is not None:
            seen.append(ctx.deps)
        return f"Hello, {name}!"

    return toolset


def setup(
    *steps: Step, toolset: FunctionToolset[ToolContext] | None = None
) -> tuple[PydanticAIProvider, ScriptedModel]:
    scripted = ScriptedModel(*steps)
    return PydanticAIProvider(scripted.model, [toolset] if toolset else None), scripted


def user_prompts(request: Sequence[ModelMessage]) -> list[str]:
    return [
        str(part.content)
        for message in request
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, UserPromptPart)
    ]


async def test_returns_the_reply_text_and_sends_the_user_message():
    provider, model = setup(text("olá"))

    assert await provider.generate_response("chat", "oi", CTX) == "olá"
    assert user_prompts(model.requests[0]) == ["oi"]


async def test_sends_the_system_prompt_as_instructions():
    provider, model = setup()

    await provider.generate_response("chat", "oi", CTX)

    assert model.infos[0].instructions == SYSTEM_PROMPT.strip()


async def test_sends_the_previous_turns_on_the_next_call():
    provider, model = setup(text("a1"), text("a2"))

    await provider.generate_response("chat", "q1", CTX)
    await provider.generate_response("chat", "q2", CTX)

    request = model.requests[1]
    assert user_prompts(request) == ["q1", "q2"]
    assert isinstance(request[1], ModelResponse)


async def test_keeps_conversations_isolated_per_chat():
    provider, model = setup(text("a1"), text("b1"))

    await provider.generate_response("chat-a", "from a", CTX)
    await provider.generate_response("chat-b", "from b", CTX)

    assert user_prompts(model.requests[1]) == ["from b"]


async def test_asks_again_after_an_empty_reply():
    provider, _ = setup(text(""), text("fine"))

    assert await provider.generate_response("chat", "x", CTX) == "fine"


async def test_raises_on_repeated_empty_replies_without_storing_the_turn():
    provider, model = setup(text(""), text(""), text(""), text("fine"))

    with pytest.raises(UnexpectedModelBehavior):
        await provider.generate_response("chat", "lost", CTX)
    await provider.generate_response("chat", "next", CTX)

    assert user_prompts(model.requests[-1]) == ["next"]


async def test_does_not_store_the_turn_when_the_model_call_fails():
    provider, model = setup(RuntimeError("429"), text("fine"))

    with pytest.raises(RuntimeError, match="429"):
        await provider.generate_response("chat", "lost", CTX)
    await provider.generate_response("chat", "next", CTX)

    assert user_prompts(model.requests[-1]) == ["next"]


async def test_caps_history_at_20_messages_and_starts_on_a_user_turn():
    provider, model = setup()

    for i in range(12):
        await provider.generate_response("chat", f"q{i}", CTX)
    await provider.generate_response("chat", "last", CTX)

    request = model.requests[12]
    # 20 stored messages + the new user message
    assert len(request) == 21
    assert user_prompts(request[:1]) != []
    assert user_prompts(request)[-1] == "last"


class TestTools:
    async def test_runs_the_requested_tool_and_returns_the_final_reply(self):
        provider, model = setup(
            call("greet", {"name": "Rafa"}), text("Olá, Rafa!"), toolset=greeter_toolset()
        )

        reply = await provider.generate_response("chat", "hello world, sou o Rafa", CTX)

        assert reply == "Olá, Rafa!"
        assert [t.name for t in model.infos[0].function_tools] == ["greet"]
        [result] = model.tool_returns()
        assert result.content == "Hello, Rafa!"

    async def test_passes_the_message_context_to_the_tool(self):
        seen: list[ToolContext] = []
        provider, _ = setup(call("greet"), text("ok"), toolset=greeter_toolset(seen))

        await provider.generate_response("chat", "x", CTX)

        assert seen == [CTX]

    async def test_asks_the_model_to_fix_arguments_that_do_not_match_the_schema(self):
        provider, model = setup(
            call("greet", {"name": 42}),
            call("greet", {"name": "Rafa"}, id="call_2"),
            text("ok"),
            toolset=greeter_toolset(),
        )

        await provider.generate_response("chat", "x", CTX)

        assert model.retry_prompts(1) != []
        assert model.tool_returns(2)[0].content == "Hello, Rafa!"

    async def test_gives_up_after_too_many_tool_rounds(self):
        provider, _ = setup(
            *(call("greet", id=f"call_{i}") for i in range(10)), toolset=greeter_toolset()
        )

        with pytest.raises(UsageLimitExceeded):
            await provider.generate_response("chat", "x", CTX)

    async def test_never_starts_the_history_on_an_orphaned_tool_result(self):
        provider, model = setup(call("greet"), toolset=greeter_toolset())

        await provider.generate_response("chat", "hello world", CTX)
        for i in range(12):
            await provider.generate_response("chat", f"q{i}", CTX)

        for request in model.requests:
            first = request[0]
            assert isinstance(first, ModelRequest)
            assert any(isinstance(part, UserPromptPart) for part in first.parts)
