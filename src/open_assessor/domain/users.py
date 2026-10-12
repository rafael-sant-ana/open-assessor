import re
from dataclasses import dataclass, replace

_SPREADSHEET_URL = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")
_SPREADSHEET_ID = re.compile(r"[A-Za-z0-9_-]{20,}")


@dataclass(frozen=True, slots=True)
class User:
    id: str
    """`platform:id`, e.g. `telegram:123456`."""
    authorized_by: str
    """The admin's id, or `env` for users seeded from the environment."""
    created_at: str
    spreadsheet_id: str | None = None

    @property
    def has_spreadsheet(self) -> bool:
        return self.spreadsheet_id is not None

    def connect_spreadsheet(self, spreadsheet_id: str) -> "User":
        return replace(self, spreadsheet_id=spreadsheet_id)


def parse_spreadsheet_id(text: str) -> str | None:
    """Accepts a Google Sheets link or a bare spreadsheet id."""
    text = text.strip()
    if match := _SPREADSHEET_URL.search(text):
        return match.group(1)
    return text if _SPREADSHEET_ID.fullmatch(text) else None
