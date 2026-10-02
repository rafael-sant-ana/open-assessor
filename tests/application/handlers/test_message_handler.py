from dataclasses import dataclass, field

import pytest

from open_assessor.application.handlers.message_handler import ERROR_REPLY, MessageHandler
from open_assessor.application.security.allow_list import AllowList
from open_assessor.domain.messages import ChatPlatform, Message, MessageUser
from open_assessor.ports.chat_provider import MessageListener, Unsubscribe
from open_assessor.ports.logger import MessageContext
from open_assessor.ports.tool import ToolContext


@dataclass
class FakeChat:
    platform: ChatPlatform = "telegram"
    is_connected: bool = True
    sent: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    typing: list[bool] = field(default_factory=list[bool])

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    async def send_typing(self, chat_id: str, active: bool) -> None:
        self.typing.append(active)

    def on_message(self, listener: MessageListener) -> Unsubscribe:
        return lambda: None


@dataclass
class FakeLLM:
    reply: str | Exception = "ok"
    calls: list[tuple[str, str, ToolContext]] = field(
        default_factory=list[tuple[str, str, ToolContext]]
    )

    async def generate_response(self, chat_id: str, message: str, context: ToolContext) -> str:
        self.calls.append((chat_id, message, context))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class SilentLogger:
    def debug(self, message: str, context: MessageContext | None = None) -> None: ...
    def info(self, message: str, context: MessageContext | None = None) -> None: ...
    def warning(self, message: str, context: MessageContext | None = None) -> None: ...
    def error(self, message: str, context: MessageContext | None = None) -> None: ...
    def exception(self, message: str, context: MessageContext | None = None) -> None: ...


def message(content: str = "gastei 50 no burger king", author: str = "1") -> Message:
    return Message(
        id="100", platform="telegram", author=MessageUser(author), content=content, chat_id="10"
    )


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat()


def handler(llm: FakeLLM) -> MessageHandler:
    return MessageHandler(llm, AllowList.from_env({"ALLOWED_USERS": "telegram:1"}), SilentLogger())


async def test_replies_with_the_llm_response_and_stops_typing(chat: FakeChat):
    llm = FakeLLM(reply="Salvo!")

    await handler(llm).handle(message(), chat)

    assert chat.sent == [("10", "Salvo!")]
    assert chat.typing == [True, False]


async def test_passes_platform_scoped_ids_to_the_llm(chat: FakeChat):
    llm = FakeLLM()

    await handler(llm).handle(message(), chat)

    assert llm.calls == [
        (
            "telegram:10",
            "gastei 50 no burger king",
            ToolContext(user_id="telegram:1", message_key="telegram:10:100"),
        )
    ]


async def test_ignores_users_outside_the_allow_list(chat: FakeChat):
    llm = FakeLLM()

    await handler(llm).handle(message(author="2"), chat)

    assert llm.calls == []
    assert chat.sent == []


async def test_answers_whoami_even_for_unknown_users(chat: FakeChat):
    await handler(FakeLLM()).handle(message(content=" /MEU-ID ", author="2"), chat)

    assert chat.sent == [("10", "Seu ID é:\n> 2")]


async def test_replies_with_an_apology_when_the_llm_fails(chat: FakeChat):
    await handler(FakeLLM(reply=RuntimeError("boom"))).handle(message(), chat)

    assert chat.sent == [("10", ERROR_REPLY)]
    assert chat.typing == [True, False]
