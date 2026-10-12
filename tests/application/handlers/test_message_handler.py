from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from open_assessor.application.handlers.message_handler import (
    AUDIO_EMPTY_REPLY,
    AUDIO_ERROR_REPLY,
    AUDIO_UNSUPPORTED_REPLY,
    ERROR_REPLY,
    MessageHandler,
)
from open_assessor.application.handlers.user_commands import UserCommands
from open_assessor.application.security.allow_list import AllowList
from open_assessor.application.security.authorizer import Authorizer
from open_assessor.application.usecases.authorize_user import AuthorizeUser
from open_assessor.domain.messages import Audio, ChatPlatform, Message, MessageUser
from open_assessor.domain.users import User
from open_assessor.infrastructure.users.in_memory_user_repository import InMemoryUserRepository
from open_assessor.ports.chat_provider import MessageListener, Unsubscribe
from open_assessor.ports.logger import MessageContext
from open_assessor.ports.spreadsheet_access import SpreadsheetProblem
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


USER = User("telegram:1", "env", "2026-10-01T12:00:00.000Z")


@dataclass
class FakeTranscriber:
    text: str | Exception = "gastei 10 reais em pão"
    calls: list[Audio] = field(default_factory=list[Audio])

    async def transcribe(self, audio: Audio) -> str:
        self.calls.append(audio)
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


@dataclass
class FakeSpreadsheets:
    service_account_email: str | None = "bot@project.iam.gserviceaccount.com"

    async def check(self, spreadsheet_id: str) -> SpreadsheetProblem | None:
        return None


def handler(
    llm: FakeLLM,
    transcriber: FakeTranscriber | None = None,
    *,
    users: InMemoryUserRepository | None = None,
    spreadsheets: FakeSpreadsheets | None = None,
) -> MessageHandler:
    repository = users or InMemoryUserRepository([USER])
    commands = UserCommands(
        repository,
        AllowList.from_csv("telegram:1"),
        AuthorizeUser(repository, lambda: datetime(2026, 10, 1, tzinfo=UTC)),
        spreadsheets,
    )
    return MessageHandler(llm, Authorizer(repository), commands, SilentLogger(), transcriber)


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


async def test_passes_the_registered_user_id_when_matched_by_an_alias(chat: FakeChat):
    llm = FakeLLM()
    aliased = Message(
        id="100",
        platform="telegram",
        author=MessageUser("999", aliases=("1",)),
        content="oi",
        chat_id="10",
    )

    await handler(llm).handle(aliased, chat)

    assert llm.calls[0][2].user_id == "telegram:1"


async def test_replies_to_commands_without_asking_the_llm(chat: FakeChat):
    llm = FakeLLM()

    await handler(llm).handle(message(content="/autorizar 2"), chat)

    assert llm.calls == []
    assert chat.sent == [("10", "telegram:2 autorizado! Ela já pode usar o bot.")]


async def test_asks_users_without_a_spreadsheet_to_connect_one(chat: FakeChat):
    llm = FakeLLM()

    await handler(llm, spreadsheets=FakeSpreadsheets()).handle(message(), chat)

    assert llm.calls == []
    [(_, reply)] = chat.sent
    assert reply.startswith("Você ainda não conectou sua planilha.")
    assert "bot@project.iam.gserviceaccount.com" in reply


async def test_users_with_a_spreadsheet_go_straight_to_the_llm(chat: FakeChat):
    llm = FakeLLM()
    users = InMemoryUserRepository([USER.connect_spreadsheet("sheet-1")])

    await handler(llm, users=users, spreadsheets=FakeSpreadsheets()).handle(message(), chat)

    assert len(llm.calls) == 1


async def test_replies_with_an_apology_when_the_user_lookup_fails(chat: FakeChat):
    class BrokenUsers(InMemoryUserRepository):
        async def get(self, user_id: str) -> User | None:
            raise ConnectionError("mongo is down")

    await handler(FakeLLM(), users=BrokenUsers()).handle(message(), chat)

    assert chat.sent == [("10", ERROR_REPLY)]


VOICE = Audio(b"ogg-bytes", "voice.ogg", "audio/ogg")


def voice_message(author: str = "1") -> Message:
    return Message(
        id="100",
        platform="telegram",
        author=MessageUser(author),
        content="",
        chat_id="10",
        audio=VOICE,
    )


def audio_handler(llm: FakeLLM, transcriber: FakeTranscriber | None) -> MessageHandler:
    return handler(llm, transcriber)


async def test_transcribes_audio_and_sends_the_text_to_the_llm(chat: FakeChat):
    llm = FakeLLM(reply="Salvo!")
    transcriber = FakeTranscriber()

    await audio_handler(llm, transcriber).handle(voice_message(), chat)

    assert transcriber.calls == [VOICE]
    assert [text for _, text, _ in llm.calls] == ["gastei 10 reais em pão"]
    assert chat.sent == [("10", '🎙️ "gastei 10 reais em pão"\n\nSalvo!')]
    assert chat.typing == [True, False]


async def test_does_not_transcribe_audio_from_unauthorized_users(chat: FakeChat):
    llm = FakeLLM()
    transcriber = FakeTranscriber()

    await audio_handler(llm, transcriber).handle(voice_message(author="2"), chat)

    assert transcriber.calls == []
    assert llm.calls == []
    assert chat.sent == []


async def test_asks_for_text_when_no_transcriber_is_configured(chat: FakeChat):
    llm = FakeLLM()

    await audio_handler(llm, None).handle(voice_message(), chat)

    assert llm.calls == []
    assert chat.sent == [("10", AUDIO_UNSUPPORTED_REPLY)]


async def test_replies_with_an_apology_when_transcription_fails(chat: FakeChat):
    llm = FakeLLM()

    await audio_handler(llm, FakeTranscriber(text=RuntimeError("boom"))).handle(
        voice_message(), chat
    )

    assert llm.calls == []
    assert chat.sent == [("10", AUDIO_ERROR_REPLY)]
    assert chat.typing == [True, False]


async def test_asks_to_repeat_when_the_transcription_is_empty(chat: FakeChat):
    llm = FakeLLM()

    await audio_handler(llm, FakeTranscriber(text="")).handle(voice_message(), chat)

    assert llm.calls == []
    assert chat.sent == [("10", AUDIO_EMPTY_REPLY)]
