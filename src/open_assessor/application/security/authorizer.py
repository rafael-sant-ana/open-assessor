from open_assessor.domain.messages import ChatPlatform, MessageUser
from open_assessor.domain.users import User
from open_assessor.ports.user_repository import UserRepository


class Authorizer:
    """A sender is authorized when any of their identifiers is a registered user."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def find(self, platform: ChatPlatform, author: MessageUser) -> User | None:
        for id in (author.id, *author.aliases):
            user = await self._users.get(f"{platform}:{id}")
            if user is not None:
                return user
        return None
