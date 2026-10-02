from collections.abc import Mapping

import pytest

from open_assessor.infrastructure.expenses.expense_repository_factory import (
    create_expense_repository,
)
from open_assessor.infrastructure.expenses.google_sheets_expense_repository import (
    GoogleSheetsExpenseRepository,
)
from open_assessor.infrastructure.expenses.in_memory_expense_repository import (
    InMemoryExpenseRepository,
)
from tests.infrastructure.expenses.fake_sheets import FakeSheets


async def test_falls_back_to_memory_when_spreadsheet_id_is_not_set():
    result = await create_expense_repository({})

    assert not result.persistent
    assert isinstance(result.repository, InMemoryExpenseRepository)


async def test_treats_a_blank_spreadsheet_id_as_not_set():
    result = await create_expense_repository({"SPREADSHEET_ID": "  "})

    assert isinstance(result.repository, InMemoryExpenseRepository)


async def test_uses_google_sheets_and_prepares_the_tab_when_spreadsheet_id_is_set():
    fake = FakeSheets()
    received: list[Mapping[str, str]] = []

    def create_api(env: Mapping[str, str]) -> FakeSheets:
        received.append(env)
        return fake

    result = await create_expense_repository({"SPREADSHEET_ID": "abc"}, create_api)

    assert result.persistent
    assert isinstance(result.repository, GoogleSheetsExpenseRepository)
    assert "gastos" in fake.tabs
    assert received == [{"SPREADSHEET_ID": "abc"}]
    assert fake.calls_to("spreadsheets.get")[0]["spreadsheetId"] == "abc"


async def test_fails_at_startup_when_the_credentials_are_missing():
    with pytest.raises(
        ValueError, match="GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS"
    ):
        await create_expense_repository({"SPREADSHEET_ID": "abc"})
