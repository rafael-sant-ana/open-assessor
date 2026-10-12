from collections.abc import Mapping

import pytest

from open_assessor.infrastructure.expenses.expense_storage_factory import create_expense_storage
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from open_assessor.infrastructure.expenses.per_user_expense_repository import (
    PerUserExpenseRepository,
)
from open_assessor.infrastructure.users.in_memory_user_repository import InMemoryUserRepository
from tests.infrastructure.expenses.fake_sheets import FakeSheets


def fixed_email(env: Mapping[str, str]) -> str | None:
    return "bot@project.iam.gserviceaccount.com"


async def test_keeps_expenses_in_memory_without_a_spreadsheet_or_mongodb():
    storage = await create_expense_storage(InMemoryUserRepository(), {})

    assert not storage.persistent
    assert isinstance(storage.repository, InMemoryExpenseRepository)
    assert storage.spreadsheets is None


@pytest.mark.parametrize("env", [{"SPREADSHEET_ID": "abc"}, {"MONGODB_URL": "mongodb://localhost"}])
async def test_uses_one_spreadsheet_per_user_when_configured(env: dict[str, str]):
    storage = await create_expense_storage(
        InMemoryUserRepository(), env, lambda _: FakeSheets(), fixed_email
    )

    assert storage.persistent
    assert isinstance(storage.repository, PerUserExpenseRepository)
    assert storage.spreadsheets is not None
    assert storage.spreadsheets.service_account_email == "bot@project.iam.gserviceaccount.com"


async def test_validates_the_shared_spreadsheet_at_startup():
    fake = FakeSheets()

    await create_expense_storage(
        InMemoryUserRepository(), {"SPREADSHEET_ID": "abc"}, lambda _: fake, fixed_email
    )

    assert fake.calls_to("spreadsheets.get")[0]["spreadsheetId"] == "abc"
    assert "gastos" in fake.tabs
