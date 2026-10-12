import contextlib

from open_assessor.application.security.allow_list import AllowList
from open_assessor.domain.messages import Message
from open_assessor.ports.chat_provider import ChatProvider
from open_assessor.ports.llm_provider import LLMProvider
from open_assessor.ports.logger import Logger, MessageContext
from open_assessor.ports.tool import ToolContext
from open_assessor.ports.transcriber import Transcriber

WHOAMI_COMMANDS = frozenset({"/meu-id", "/meu-jid"})

ERROR_REPLY = "Desculpe, houve um erro interno ao tentar processar sua mensagem."
AUDIO_UNSUPPORTED_REPLY = "Ainda não consigo ouvir áudios por aqui. Pode mandar por texto?"
AUDIO_EMPTY_REPLY = "Não consegui entender o áudio. Pode repetir ou mandar por texto?"
AUDIO_ERROR_REPLY = "Desculpe, não consegui transcrever o seu áudio."


class MessageHandler:
    def __init__(
        self,
        llm: LLMProvider,
        allow_list: AllowList,
        logger: Logger,
        transcriber: Transcriber | None = None,
    ) -> None:
        self._llm = llm
        self._allow_list = allow_list
        self._logger = logger
        self._transcriber = transcriber

    async def handle(self, message: Message, chat: ChatProvider) -> None:
        context: MessageContext = {"chat_id": message.chat_id, "message_id": message.id}

        if message.content.strip().lower() in WHOAMI_COMMANDS:
            await self._reply(chat, message, f"Seu ID é:\n> {message.author.id}")
            return

        if not self._allow_list.is_allowed(message.platform, message.author):
            self._logger.debug("Ignoring message from unauthorized user", context)
            return

        if message.audio is not None and self._transcriber is None:
            await self._reply(chat, message, AUDIO_UNSUPPORTED_REPLY)
            return

        await chat.send_typing(message.chat_id, True)

        try:
            content = message.content
            heard = ""
            if message.audio is not None and self._transcriber is not None:
                try:
                    content = await self._transcriber.transcribe(message.audio)
                except Exception:
                    self._logger.exception("Failed to transcribe audio", context)
                    await self._reply(chat, message, AUDIO_ERROR_REPLY)
                    return
                if not content:
                    await self._reply(chat, message, AUDIO_EMPTY_REPLY)
                    return
                # Echoed back so a misheard amount is noticed before it is trusted.
                heard = f'🎙️ "{content}"\n\n'

            self._logger.debug("Generating response", context)
            try:
                response = await self._llm.generate_response(
                    f"{message.platform}:{message.chat_id}",
                    content,
                    ToolContext(
                        user_id=f"{message.platform}:{message.author.id}",
                        message_key=f"{message.platform}:{message.chat_id}:{message.id}",
                    ),
                )
            except Exception:
                self._logger.exception("Failed to generate response", context)
                response = ERROR_REPLY

            await self._reply(chat, message, heard + response)
        finally:
            with contextlib.suppress(Exception):
                await chat.send_typing(message.chat_id, False)

    async def _reply(self, chat: ChatProvider, message: Message, text: str) -> None:
        try:
            await chat.send_message(message.chat_id, text)
        except Exception:
            self._logger.exception(
                "Failed to send message response",
                {"chat_id": message.chat_id, "message_id": message.id},
            )
