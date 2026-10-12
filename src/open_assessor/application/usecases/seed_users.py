from collections.abc import Iterable

from open_assessor.domain.dates import Clock, to_iso_instant
from open_assessor.domain.users import User
from open_assessor.ports.user_repository import UserRepository

SEEDED_BY = "env"


class SeedUsers:
    """Makes sure the users listed in the environment exist, so the single-sheet setup keeps
    working: `SPREADSHEET_ID` becomes their spreadsheet unless they already connected one."""

    def __init__(self, users: UserRepository, clock: Clock) -> None:
        self._users = users
        self._clock = clock

    async def execute(self, user_ids: Iterable[str], spreadsheet_id: str | None) -> None:
        for user_id in user_ids:
            user = await self._users.get(user_id)
            if user is None:
                user = User(user_id, SEEDED_BY, to_iso_instant(self._clock()), spreadsheet_id)
                await self._users.save(user)
            elif not user.has_spreadsheet and spreadsheet_id:
                await self._users.save(user.connect_spreadsheet(spreadsheet_id))
