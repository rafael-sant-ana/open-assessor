import os
from collections.abc import Mapping

from open_assessor.domain.messages import ChatPlatform, MessageUser


class AllowList:
    def __init__(self, entries: frozenset[str]) -> None:
        self._entries = entries

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "AllowList":
        """Reads `ALLOWED_USERS` (comma-separated `platform:id`, e.g. `telegram:123456`)
        and the legacy `ALLOWED_JIDS` (WhatsApp JIDs)."""
        entries = {entry.strip() for entry in env.get("ALLOWED_USERS", "").split(",")}
        entries |= {f"whatsapp:{jid.strip()}" for jid in env.get("ALLOWED_JIDS", "").split(",")}
        return cls(frozenset(e for e in entries if e and e != "whatsapp:"))

    @classmethod
    def from_csv(cls, raw: str) -> "AllowList":
        """Comma-separated `platform:id` entries, e.g. `ADMIN_USERS`."""
        return cls(frozenset(e for e in (entry.strip() for entry in raw.split(",")) if e))

    @property
    def is_empty(self) -> bool:
        return not self._entries

    @property
    def entries(self) -> list[str]:
        return sorted(self._entries)

    def is_allowed(self, platform: ChatPlatform, user: MessageUser) -> bool:
        return any(f"{platform}:{id}" in self._entries for id in (user.id, *user.aliases))
