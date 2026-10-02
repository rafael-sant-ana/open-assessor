from dataclasses import dataclass
from typing import Literal

type ChatPlatform = Literal["whatsapp", "telegram"]


@dataclass(frozen=True, slots=True)
class MessageUser:
    id: str
    aliases: tuple[str, ...] = ()
    """Other identifiers the platform may know this user by (e.g. WhatsApp LID vs phone JID)."""


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    platform: ChatPlatform
    author: MessageUser
    content: str
    chat_id: str
