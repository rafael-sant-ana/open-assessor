import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from open_assessor.infrastructure.users.in_memory_user_repository import InMemoryUserRepository
from open_assessor.infrastructure.users.mongo_user_repository import MongoUserRepository
from open_assessor.ports.user_repository import UserRepository


async def _nothing() -> None: ...


@dataclass(frozen=True, slots=True)
class CreatedUserRepository:
    name: str
    persistent: bool
    repository: UserRepository
    close: Callable[[], Awaitable[None]] = _nothing


async def create_user_repository(env: Mapping[str, str] = os.environ) -> CreatedUserRepository:
    """MongoDB when `MONGODB_URL` is set, otherwise memory (rebuilt from the env on start)."""
    url = env.get("MONGODB_URL", "").strip()
    if not url:
        return CreatedUserRepository("in-memory", False, InMemoryUserRepository())

    repository, client = await MongoUserRepository.connect(url)
    return CreatedUserRepository("MongoDB", True, repository, client.close)
