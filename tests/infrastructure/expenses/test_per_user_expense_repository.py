import pytest

from open_assessor.domain.dates import DateRange
from open_assessor.domain.users import User
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.infrastructure.expenses.per_user_expense_repository import (
    PerUserExpenseRepository,
    SpreadsheetNotConnectedError,
)
from open_assessor.infrastructure.users.in_memory_user_repository import InMemoryUserRepository
from tests.factories import make_expense

YEAR = DateRange("2026-01-01", "2026-12-31")


class Sheets:
    """One in-memory repository per spreadsheet id."""

    def __init__(self) -> None:
        self.by_id: dict[str, InMemoryExpenseRepository] = {}

    async def open(self, spreadsheet_id: str) -> InMemoryExpenseRepository:
        return self.by_id.setdefault(spreadsheet_id, InMemoryExpenseRepository())


@pytest.fixture
def sheets() -> Sheets:
    return Sheets()


@pytest.fixture
def repo(sheets: Sheets) -> PerUserExpenseRepository:
    users = InMemoryUserRepository(
        [
            User("telegram:1", "env", "2026-10-01T12:00:00.000Z", "sheet-a"),
            User("telegram:2", "env", "2026-10-01T12:00:00.000Z", "sheet-b"),
            User("telegram:3", "env", "2026-10-01T12:00:00.000Z"),
        ]
    )
    return PerUserExpenseRepository(users, sheets.open)


async def test_writes_each_users_expenses_to_their_own_spreadsheet(
    repo: PerUserExpenseRepository, sheets: Sheets
):
    mine = make_expense(user_id="telegram:1", message_key="k1")
    theirs = make_expense(user_id="telegram:2", message_key="k2")

    await repo.add(mine)
    await repo.add(theirs)

    assert await sheets.by_id["sheet-a"].list_by("telegram:1", YEAR) == [mine]
    assert await sheets.by_id["sheet-b"].list_by("telegram:2", YEAR) == [theirs]
    assert await repo.list_by("telegram:1", YEAR) == [mine]


async def test_checks_message_keys_in_the_users_own_spreadsheet(repo: PerUserExpenseRepository):
    await repo.add(make_expense(user_id="telegram:1", message_key="k1"))

    assert await repo.exists_by_message_key("telegram:1", "k1")
    assert not await repo.exists_by_message_key("telegram:2", "k1")


async def test_removes_from_the_users_own_spreadsheet(repo: PerUserExpenseRepository):
    expense = make_expense(user_id="telegram:2", message_key="k2")
    await repo.add(expense)

    assert await repo.remove_last_by("telegram:1") is None
    assert await repo.remove_last_by("telegram:2") == expense


@pytest.mark.parametrize("user_id", ["telegram:3", "telegram:404"])
async def test_refuses_users_without_a_spreadsheet(repo: PerUserExpenseRepository, user_id: str):
    with pytest.raises(SpreadsheetNotConnectedError):
        await repo.list_by(user_id, YEAR)
