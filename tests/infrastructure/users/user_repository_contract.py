from open_assessor.domain.users import User
from open_assessor.ports.user_repository import UserRepository

USER = User("telegram:1", "telegram:9", "2026-10-01T12:00:00.000Z")


class UserRepositoryContract:
    """Behavior every `UserRepository` implementation must honour.

    Subclass it as `Test...` and define an async `repo` fixture that starts empty.
    """

    async def test_returns_none_for_an_unknown_user(self, repo: UserRepository):
        assert await repo.get("telegram:1") is None

    async def test_round_trips_a_user_exactly(self, repo: UserRepository):
        await repo.save(USER)

        assert await repo.get("telegram:1") == USER

    async def test_saving_again_replaces_the_user(self, repo: UserRepository):
        await repo.save(USER)
        await repo.save(USER.connect_spreadsheet("sheet"))

        assert await repo.get("telegram:1") == USER.connect_spreadsheet("sheet")

    async def test_deletes_and_reports_whether_the_user_existed(self, repo: UserRepository):
        await repo.save(USER)

        assert await repo.delete("telegram:1")
        assert await repo.get("telegram:1") is None
        assert not await repo.delete("telegram:1")
