from dataclasses import dataclass
from typing import Literal

type ChatPlatform = Literal["whatsapp", "telegram"]


@dataclass(frozen=True, slots=True)
class MessageUser:
    id: str
    aliases: tuple[str, ...] = ()
    """Other identifiers the platform may know this user by (e.g. WhatsApp LID vs phone JID)."""


@dataclass(frozen=True, slots=True)
class Audio:
    data: bytes
    file_name: str
    """Carries the extension transcription services use to detect the format (e.g. voice.ogg)."""
    mime_type: str


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    platform: ChatPlatform
    author: MessageUser
    content: str
    chat_id: str
    audio: Audio | None = None
    """Set for voice notes and audio files; content is empty until it is transcribed."""
