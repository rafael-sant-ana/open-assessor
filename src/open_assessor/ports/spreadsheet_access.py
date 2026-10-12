from typing import Literal, Protocol

type SpreadsheetProblem = Literal["not_shared", "invalid_layout"]


class SpreadsheetAccess(Protocol):
    @property
    def service_account_email(self) -> str | None:
        """The address users must share their spreadsheet with."""
        ...

    async def check(self, spreadsheet_id: str) -> SpreadsheetProblem | None:
        """Prepares the expenses tab if needed; returns why the bot cannot use the sheet."""
        ...
