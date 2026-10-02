import contextlib

from open_assessor.application.security.allow_list import AllowList
from open_assessor.domain.messages import Message
from open_assessor.ports.chat_provider import ChatProvider
from open_assessor.ports.llm_provider import LLMProvider
from open_assessor.ports.logger import Logger, MessageContext
from open_assessor.ports.tool import ToolContext

WHOAMI_COMMANDS = frozenset({"/meu-id", "/meu-jid"})

ERROR_REPLY = "Desculpe, houve um erro interno ao tentar processar sua mensagem."


class MessageHandler:
    def __init__(self, llm: LLMProvider, allow_list: AllowList, logger: Logger) -> None:
        self._llm = llm
        self._allow_list = allow_list
        self._logger = logger

    async def handle(self, message: Message, chat: ChatProvider) -> None:
        context: MessageContext = {"chat_id": message.chat_id, "message_id": message.id}

        if message.content.strip().lower() in WHOAMI_COMMANDS:
            await self._reply(chat, message, f"Seu ID é:\n> {message.author.id}")
            return

        if not self._allow_list.is_allowed(message.platform, message.author):
            self._logger.debug("Ignoring message from unauthorized user", context)
            return

        await chat.send_typing(message.chat_id, True)

        try:
            self._logger.debug("Generating response", context)
            try:
                response = await self._llm.generate_response(
                    f"{message.platform}:{message.chat_id}",
                    message.content,
                    ToolContext(
                        user_id=f"{message.platform}:{message.author.id}",
                        message_key=f"{message.platform}:{message.chat_id}:{message.id}",
                    ),
                )
            except Exception:
                self._logger.exception("Failed to generate response", context)
                response = ERROR_REPLY

            await self._reply(chat, message, response)
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
