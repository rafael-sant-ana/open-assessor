from datetime import UTC, datetime

from open_assessor.application.usecases.seed_users import SeedUsers
from open_assessor.domain.users import User
from open_assessor.infrastructure.users.in_memory_user_repository import InMemoryUserRepository


def clock() -> datetime:
    return datetime(2026, 10, 1, 12, tzinfo=UTC)


async def test_creates_missing_users_with_the_shared_spreadsheet():
    users = InMemoryUserRepository()

    await SeedUsers(users, clock).execute(["telegram:1", "telegram:2"], "sheet")

    assert await users.get("telegram:1") == User(
        "telegram:1", "env", "2026-10-01T12:00:00.000Z", "sheet"
    )
    assert await users.get("telegram:2") is not None


async def test_never_replaces_a_spreadsheet_the_user_connected():
    own = User("telegram:1", "telegram:9", "2026-01-01T00:00:00.000Z", "own-sheet")
    users = InMemoryUserRepository([own])

    await SeedUsers(users, clock).execute(["telegram:1"], "shared-sheet")

    assert await users.get("telegram:1") == own


async def test_gives_the_shared_spreadsheet_to_existing_users_without_one():
    users = InMemoryUserRepository([User("telegram:1", "telegram:9", "2026-01-01T00:00:00.000Z")])

    await SeedUsers(users, clock).execute(["telegram:1"], "shared-sheet")

    user = await users.get("telegram:1")
    assert user is not None and user.spreadsheet_id == "shared-sheet"
