from typing import Protocol

from open_assessor.domain.users import User


class UserRepository(Protocol):
    async def get(self, user_id: str) -> User | None: ...

    async def save(self, user: User) -> None:
        """Inserts or replaces the user with the same id."""
        ...

    async def delete(self, user_id: str) -> bool:
        """Returns whether a user was deleted."""
        ...
