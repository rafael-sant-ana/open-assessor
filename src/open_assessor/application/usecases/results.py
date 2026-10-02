from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Invalid:
    """The input was rejected; `reason` is meant to be relayed to the user."""

    reason: str
