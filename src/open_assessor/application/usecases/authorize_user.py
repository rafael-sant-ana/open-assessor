from dataclasses import dataclass

from open_assessor.domain.dates import Clock, to_iso_instant
from open_assessor.domain.users import User
from open_assessor.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class Authorized:
    user: User


@dataclass(frozen=True, slots=True)
class AlreadyAuthorized:
    user: User


type AuthorizeUserResult = Authorized | AlreadyAuthorized


class AuthorizeUser:
    def __init__(self, users: UserRepository, clock: Clock) -> None:
        self._users = users
        self._clock = clock

    async def execute(self, user_id: str, admin_id: str) -> AuthorizeUserResult:
        existing = await self._users.get(user_id)
        if existing is not None:
            return AlreadyAuthorized(existing)

        user = User(user_id, admin_id, to_iso_instant(self._clock()))
        await self._users.save(user)
        return Authorized(user)
