import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TypeGuard
from zoneinfo import ZoneInfo

type Clock = Callable[[], datetime]
"""Returns the current instant, timezone-aware."""


@dataclass(frozen=True, slots=True)
class DateRange:
    """Inclusive range of calendar days, `YYYY-MM-DD`."""

    from_: str
    to: str


DEFAULT_TIMEZONE = "America/Sao_Paulo"

_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

# Indexed by date.weekday(), where Monday is 0.
_WEEKDAYS_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def is_valid_iso_date(value: object) -> TypeGuard[str]:
    """True for a real calendar day written as `YYYY-MM-DD` (rejects `2026-02-30`)."""
    if not isinstance(value, str):
        return False

    # Checked first: date.fromisoformat also accepts formats like `20261001`.
    match = _ISO_DAY.fullmatch(value)
    if not match:
        return False

    year, month, day = (int(part) for part in match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def to_iso_instant(now: datetime) -> str:
    """UTC instant with milliseconds, e.g. `2026-10-01T12:00:00.000Z`."""
    return now.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def today_in(timezone: str, now: datetime) -> str:
    """The calendar day `now` falls on in `timezone`, as `YYYY-MM-DD`."""
    return now.astimezone(ZoneInfo(timezone)).date().isoformat()


def weekday_in(timezone: str, now: datetime) -> str:
    """Weekday name of `now` in `timezone`, in Portuguese (e.g. `quinta-feira`)."""
    return _WEEKDAYS_PT[now.astimezone(ZoneInfo(timezone)).weekday()]
