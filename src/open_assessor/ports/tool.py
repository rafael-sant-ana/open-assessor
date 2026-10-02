from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Facts about the current message that the model must never choose itself."""

    user_id: str
    """`<platform>:<authorId>`, same format as `ALLOWED_USERS`."""
    message_key: str
    """`<platform>:<chatId>:<messageId>`, unique per incoming message."""


class Tool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters(self) -> Mapping[str, object]:
        """JSON Schema describing the arguments object."""
        ...

    async def execute(self, args: Mapping[str, object], context: ToolContext) -> str: ...
