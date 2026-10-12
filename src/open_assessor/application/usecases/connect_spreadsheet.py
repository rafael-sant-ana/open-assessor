from dataclasses import dataclass

from open_assessor.application.usecases.results import Invalid
from open_assessor.domain.users import User, parse_spreadsheet_id
from open_assessor.ports.spreadsheet_access import SpreadsheetAccess, SpreadsheetProblem
from open_assessor.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class Connected:
    user: User


@dataclass(frozen=True, slots=True)
class Unavailable:
    problem: SpreadsheetProblem


type ConnectSpreadsheetResult = Connected | Unavailable | Invalid


class ConnectSpreadsheet:
    def __init__(self, users: UserRepository, spreadsheets: SpreadsheetAccess) -> None:
        self._users = users
        self._spreadsheets = spreadsheets

    async def execute(self, user: User, link: str) -> ConnectSpreadsheetResult:
        spreadsheet_id = parse_spreadsheet_id(link)
        if spreadsheet_id is None:
            return Invalid("not a Google Sheets link or spreadsheet id")

        # Checked before saving, so a user is never pointed at a sheet the bot cannot write.
        problem = await self._spreadsheets.check(spreadsheet_id)
        if problem is not None:
            return Unavailable(problem)

        connected = user.connect_spreadsheet(spreadsheet_id)
        await self._users.save(connected)
        return Connected(connected)
