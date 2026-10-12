from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Facts about the current message that the model must never choose itself."""

    user_id: str
    """`<platform>:<authorId>`, same format as `ALLOWED_USERS`."""
    message_key: str
    """`<platform>:<chatId>:<messageId>`, unique per incoming message."""
