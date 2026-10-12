import asyncio
import contextlib
import os
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal

from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    ExtBot,
    MessageHandler,
    filters,
)

from open_assessor.domain.messages import Audio, Message, MessageUser
from open_assessor.infrastructure.logging.std_logger import StdLogger
from open_assessor.ports.chat_provider import MessageListener, Unsubscribe
from open_assessor.ports.logger import MessageContext

MAX_MESSAGE_LENGTH = 4096
TYPING_REFRESH_SECONDS = 4.0
"""Telegram's typing action expires after about 5 seconds, so it is renewed while active."""
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
"""Bots cannot download files larger than this through getFile."""
VOICE_FILE_NAME = "voice.ogg"
AUDIO_FILE_NAME = "audio.mp3"
DEFAULT_AUDIO_MIME_TYPE = "audio/ogg"

type Sleep = Callable[[float], Awaitable[None]]
type TelegramApplication = Application[ExtBot[None], ContextTypes.DEFAULT_TYPE, Any, Any, Any, Any]


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    chunks: list[str] = []
    rest = text

    while len(rest) > limit:
        newline = rest.rfind("\n", 0, limit)
        # Prefer to break on a newline, otherwise cut at the limit.
        cut = newline + 1 if newline > 0 else limit
        chunks.append(rest[:cut])
        rest = rest[cut:]

    if rest or not chunks:
        chunks.append(rest)
    return chunks


class TelegramProvider:
    def __init__(
        self,
        application: TelegramApplication | None = None,
        *,
        env: Mapping[str, str] = os.environ,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if application is None:
            token = env.get("TELEGRAM_BOT_TOKEN")
            if not token:
                raise ValueError(
                    "Missing required environment variable: TELEGRAM_BOT_TOKEN. "
                    "Check the .env.example"
                )
            application = ApplicationBuilder().token(token).build()

        self._application: TelegramApplication = application
        self._sleep = sleep
        self._logger = StdLogger("telegram")
        self._is_connected = False
        self._listeners: list[MessageListener] = []
        self._typing_tasks: dict[str, asyncio.Task[None]] = {}

        # Commands are text too, and /meu-id must get through.
        self._application.add_handler(MessageHandler(filters.TEXT, self._on_text))
        self._application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._on_audio))
        self._application.add_error_handler(self._on_error)

    @property
    def platform(self) -> Literal["telegram"]:
        return "telegram"

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        if self._is_connected:
            return

        # Validates the token (getMe) and fails fast.
        await self._application.initialize()
        await self._application.start()
        if self._application.updater is not None:
            await self._application.updater.start_polling()
        self._is_connected = True
        self._logger.info("Telegram conectado!")

    async def disconnect(self) -> None:
        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()

        if not self._is_connected:
            return
        self._is_connected = False
        if self._application.updater is not None:
            await self._application.updater.stop()
        await self._application.stop()
        await self._application.shutdown()

    async def send_message(self, chat_id: str, text: str) -> None:
        for chunk in split_message(text):
            await self._application.bot.send_message(chat_id=chat_id, text=chunk)

    async def send_typing(self, chat_id: str, active: bool) -> None:
        if not active:
            task = self._typing_tasks.pop(chat_id, None)
            if task is not None:
                task.cancel()
            return

        if chat_id in self._typing_tasks:
            return

        self._typing_tasks[chat_id] = asyncio.create_task(self._keep_typing(chat_id))
        await self._send_typing_action(chat_id)

    def on_message(self, listener: MessageListener) -> Unsubscribe:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._listeners.remove(listener)

        return unsubscribe

    async def _on_text(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if (
            message is None
            or message.text is None
            or message.chat.type != ChatType.PRIVATE
            or message.from_user is None
        ):
            return

        await self._dispatch(
            Message(
                id=str(message.message_id),
                platform=self.platform,
                author=MessageUser(str(message.from_user.id)),
                content=message.text,
                chat_id=str(message.chat.id),
            )
        )

    async def _on_audio(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if message is None or message.chat.type != ChatType.PRIVATE or message.from_user is None:
            return

        if message.voice is not None:
            media, file_name = message.voice, VOICE_FILE_NAME
        elif message.audio is not None:
            media, file_name = message.audio, message.audio.file_name or AUDIO_FILE_NAME
        else:
            return

        context: MessageContext = {
            "chat_id": str(message.chat.id),
            "message_id": str(message.message_id),
        }
        if media.file_size is not None and media.file_size > MAX_DOWNLOAD_BYTES:
            # Logged only: replying here would reach users outside the allow list.
            self._logger.warning("Ignoring audio above the bot download limit", context)
            return

        file = await media.get_file()
        data = bytes(await file.download_as_bytearray())

        await self._dispatch(
            Message(
                id=str(message.message_id),
                platform=self.platform,
                author=MessageUser(str(message.from_user.id)),
                content="",
                chat_id=str(message.chat.id),
                audio=Audio(data, file_name, media.mime_type or DEFAULT_AUDIO_MIME_TYPE),
            )
        )

    async def _dispatch(self, received: Message) -> None:
        context: MessageContext = {"chat_id": received.chat_id, "message_id": received.id}
        self._logger.debug("Message received", context)

        for listener in list(self._listeners):
            try:
                await listener(received)
            except Exception:
                self._logger.exception("Message listener failed", context)

    async def _on_error(self, _: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._logger.error(f"Telegram bot error: {context.error!r}")

    async def _keep_typing(self, chat_id: str) -> None:
        while True:
            await self._sleep(TYPING_REFRESH_SECONDS)
            await self._send_typing_action(chat_id)

    async def _send_typing_action(self, chat_id: str) -> None:
        try:
            await self._application.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception as error:
            self._logger.warning(f"Failed to send typing action: {error!r}")
