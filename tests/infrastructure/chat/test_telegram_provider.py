import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from telegram.ext import MessageHandler, filters

from open_assessor.domain.messages import Message, MessageUser
from open_assessor.infrastructure.chat.telegram_provider import TelegramProvider, split_message


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.actions: list[tuple[str, str]] = []
        self.fail_actions = False

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    async def send_chat_action(self, chat_id: str, action: str) -> None:
        self.actions.append((chat_id, action))
        if self.fail_actions:
            raise ConnectionError("network")


class FakeUpdater:
    def __init__(self) -> None:
        self.polling = False

    async def start_polling(self) -> None:
        self.polling = True

    async def stop(self) -> None:
        self.polling = False


class FakeApplication:
    def __init__(self) -> None:
        self.bot = FakeBot()
        self.updater = FakeUpdater()
        self.handlers: list[Any] = []
        self.error_handlers: list[Any] = []
        self.calls: list[str] = []
        self.init_error: Exception | None = None

    def add_handler(self, handler: Any) -> None:
        self.handlers.append(handler)

    def add_error_handler(self, handler: Any) -> None:
        self.error_handlers.append(handler)

    async def initialize(self) -> None:
        self.calls.append("initialize")
        if self.init_error:
            raise self.init_error

    async def start(self) -> None:
        self.calls.append("start")

    async def stop(self) -> None:
        self.calls.append("stop")

    async def shutdown(self) -> None:
        self.calls.append("shutdown")


class Ticker:
    """Stands in for asyncio.sleep: sleepers only wake when the test ticks."""

    def __init__(self) -> None:
        self._sleepers: list[asyncio.Future[None]] = []

    async def sleep(self, seconds: float) -> None:
        future = asyncio.get_running_loop().create_future()
        self._sleepers.append(future)
        await future

    async def tick(self) -> None:
        sleepers, self._sleepers = self._sleepers, []
        for future in sleepers:
            if not future.done():
                future.set_result(None)
        await settle()


async def settle() -> None:
    """Lets background tasks run until they block again."""
    for _ in range(5):
        await asyncio.sleep(0)


def update(
    text: str | None = "oi", chat_type: str = "private", from_id: int | None = 99
) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(
            message_id=7,
            text=text,
            chat=SimpleNamespace(id=42, type=chat_type),
            from_user=None if from_id is None else SimpleNamespace(id=from_id),
        )
    )


class Setup:
    def __init__(self) -> None:
        self.app = FakeApplication()
        self.ticker = Ticker()
        self.provider = TelegramProvider(self.app, sleep=self.ticker.sleep)  # pyright: ignore[reportArgumentType]
        self.received: list[Message] = []

    async def deliver(self, u: SimpleNamespace) -> None:
        await self.app.handlers[0].callback(u, None)

    def collect(self) -> None:
        async def listener(message: Message) -> None:
            self.received.append(message)

        self.provider.on_message(listener)


@pytest.fixture
async def setup():
    s = Setup()
    yield s
    await s.provider.disconnect()


def test_raises_when_telegram_bot_token_is_missing():
    with pytest.raises(
        ValueError, match="Missing required environment variable: TELEGRAM_BOT_TOKEN"
    ):
        TelegramProvider(env={})


def test_builds_a_real_application_from_the_token_without_touching_the_network():
    assert TelegramProvider(env={"TELEGRAM_BOT_TOKEN": "123:abc"}).platform == "telegram"


def test_has_the_telegram_platform(setup: Setup):
    assert setup.provider.platform == "telegram"


def test_listens_to_all_text_messages_including_commands(setup: Setup):
    [handler] = setup.app.handlers

    assert isinstance(handler, MessageHandler)
    assert handler.filters is filters.TEXT


async def test_connect_validates_the_token_starts_polling_and_sets_is_connected(setup: Setup):
    await setup.provider.connect()

    assert setup.app.calls == ["initialize", "start"]
    assert setup.app.updater.polling
    assert setup.provider.is_connected


async def test_connect_fails_fast_when_initialize_raises(setup: Setup):
    setup.app.init_error = RuntimeError("Unauthorized")

    with pytest.raises(RuntimeError, match="Unauthorized"):
        await setup.provider.connect()
    assert setup.app.calls == ["initialize"]
    assert not setup.provider.is_connected


async def test_disconnect_stops_polling_and_the_application(setup: Setup):
    await setup.provider.connect()

    await setup.provider.disconnect()

    assert not setup.app.updater.polling
    assert setup.app.calls == ["initialize", "start", "stop", "shutdown"]
    assert not setup.provider.is_connected


async def test_maps_private_text_messages(setup: Setup):
    setup.collect()

    await setup.deliver(update())

    assert setup.received == [
        Message(id="7", platform="telegram", author=MessageUser("99"), content="oi", chat_id="42")
    ]


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
async def test_ignores_groups_and_channels(setup: Setup, chat_type: str):
    setup.collect()

    await setup.deliver(update(chat_type=chat_type))

    assert setup.received == []


async def test_ignores_messages_without_sender(setup: Setup):
    setup.collect()

    await setup.deliver(update(from_id=None))

    assert setup.received == []


async def test_keeps_working_when_a_listener_raises(setup: Setup):
    async def broken(message: Message) -> None:
        raise RuntimeError("boom")

    setup.provider.on_message(broken)
    setup.collect()

    await setup.deliver(update())

    assert len(setup.received) == 1


async def test_registers_an_error_handler_that_does_not_raise(setup: Setup):
    [handler] = setup.app.error_handlers

    await handler(None, SimpleNamespace(error=RuntimeError("x")))


async def test_stops_delivering_after_unsubscribing(setup: Setup):
    received: list[Message] = []

    async def listener(message: Message) -> None:
        received.append(message)

    unsubscribe = setup.provider.on_message(listener)
    unsubscribe()
    await setup.deliver(update())

    assert received == []


async def test_sends_short_messages_as_a_single_chunk(setup: Setup):
    await setup.provider.send_message("42", "olá")

    assert setup.app.bot.sent == [("42", "olá")]


async def test_splits_long_messages_into_ordered_chunks_of_at_most_4096_chars(setup: Setup):
    text = "a" * 4096 + "b" * 4096 + "c" * 10

    await setup.provider.send_message("42", text)

    sent = [chunk for _, chunk in setup.app.bot.sent]
    assert len(sent) == 3
    assert all(len(chunk) <= 4096 for chunk in sent)
    assert "".join(sent) == text


def test_prefers_newline_boundaries_when_splitting():
    line = "x" * 3000
    text = f"{line}\n{line}\n{line}"

    chunks = split_message(text)

    assert len(chunks) == 3
    assert chunks[0] == f"{line}\n"
    assert "".join(chunks) == text


async def test_sends_typing_immediately_and_refreshes_until_stopped(setup: Setup):
    await setup.provider.send_typing("42", True)
    await settle()
    assert setup.app.bot.actions == [("42", "typing")]

    await setup.ticker.tick()
    await setup.ticker.tick()
    assert len(setup.app.bot.actions) == 3

    await setup.provider.send_typing("42", False)
    await setup.ticker.tick()
    assert len(setup.app.bot.actions) == 3


async def test_keeps_one_typing_refresher_per_chat(setup: Setup):
    await setup.provider.send_typing("42", True)
    await setup.provider.send_typing("42", True)
    await settle()
    await setup.ticker.tick()

    assert len(setup.app.bot.actions) == 2


async def test_does_not_crash_when_the_typing_refresh_fails(setup: Setup):
    await setup.provider.send_typing("42", True)
    await settle()
    setup.app.bot.fail_actions = True

    await setup.ticker.tick()
    setup.app.bot.fail_actions = False
    await setup.ticker.tick()

    assert len(setup.app.bot.actions) == 3


async def test_stops_typing_refreshers_on_disconnect(setup: Setup):
    await setup.provider.send_typing("42", True)
    await settle()

    await setup.provider.disconnect()
    await setup.ticker.tick()

    assert len(setup.app.bot.actions) == 1
