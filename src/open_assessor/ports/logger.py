from typing import Protocol, TypedDict


class MessageContext(TypedDict):
    chat_id: str
    message_id: str


class Logger(Protocol):
    def debug(self, message: str, context: MessageContext | None = None) -> None: ...

    def info(self, message: str, context: MessageContext | None = None) -> None: ...

    def warning(self, message: str, context: MessageContext | None = None) -> None: ...

    def error(self, message: str, context: MessageContext | None = None) -> None: ...

    def exception(self, message: str, context: MessageContext | None = None) -> None:
        """Logs at error level with the traceback of the exception being handled."""
        ...
