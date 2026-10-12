from collections.abc import Iterable

from open_assessor.domain.users import User


class InMemoryUserRepository:
    def __init__(self, users: Iterable[User] = ()) -> None:
        self._users: dict[str, User] = {user.id: user for user in users}

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def save(self, user: User) -> None:
        self._users[user.id] = user

    async def delete(self, user_id: str) -> bool:
        return self._users.pop(user_id, None) is not None
