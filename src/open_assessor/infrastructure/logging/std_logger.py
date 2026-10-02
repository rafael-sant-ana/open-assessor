import logging
import os

from open_assessor.ports.logger import MessageContext

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Sets up the root logger once, from `LOG_LEVEL` unless a level is given."""
    logging.basicConfig(
        level=(level or os.environ.get("LOG_LEVEL") or "INFO").upper(),
        format=_FORMAT,
    )
    # httpx logs every Telegram long-polling request at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)


class StdLogger:
    """`Logger` over the standard library, with the message context appended to each line."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def debug(self, message: str, context: MessageContext | None = None) -> None:
        self._logger.debug(_with_context(message, context))

    def info(self, message: str, context: MessageContext | None = None) -> None:
        self._logger.info(_with_context(message, context))

    def warning(self, message: str, context: MessageContext | None = None) -> None:
        self._logger.warning(_with_context(message, context))

    def error(self, message: str, context: MessageContext | None = None) -> None:
        self._logger.error(_with_context(message, context))

    def exception(self, message: str, context: MessageContext | None = None) -> None:
        self._logger.exception(_with_context(message, context))


def _with_context(message: str, context: MessageContext | None) -> str:
    if not context:
        return message
    return f"{message} (chat_id={context['chat_id']} message_id={context['message_id']})"
