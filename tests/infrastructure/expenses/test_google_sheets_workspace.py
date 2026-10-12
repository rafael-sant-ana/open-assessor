import pytest

from open_assessor.infrastructure.expenses.google_sheets_workspace import GoogleSheetsWorkspace
from tests.infrastructure.expenses.fake_sheets import FakeSheets, http_error


@pytest.fixture
def fake() -> FakeSheets:
    return FakeSheets()


@pytest.fixture
def workspace(fake: FakeSheets) -> GoogleSheetsWorkspace:
    return GoogleSheetsWorkspace(fake, "bot@project.iam.gserviceaccount.com")


async def test_prepares_each_spreadsheet_once(fake: FakeSheets, workspace: GoogleSheetsWorkspace):
    first = await workspace.open("sheet-a")
    again = await workspace.open("sheet-a")

    assert first is again
    assert [c["spreadsheetId"] for c in fake.calls_to("spreadsheets.get")] == ["sheet-a"]


async def test_check_passes_and_prepares_the_tab(
    fake: FakeSheets, workspace: GoogleSheetsWorkspace
):
    assert await workspace.check("sheet-a") is None
    assert "gastos" in fake.tabs


@pytest.mark.parametrize("status", [400, 403, 404])
async def test_check_reports_a_spreadsheet_that_is_not_shared(
    fake: FakeSheets, workspace: GoogleSheetsWorkspace, status: int
):
    fake.fail_on("spreadsheets.get", http_error(status), times=1)

    assert await workspace.check("sheet-a") == "not_shared"


async def test_check_reports_a_foreign_expenses_tab(
    fake: FakeSheets, workspace: GoogleSheetsWorkspace
):
    fake.seed_tab("gastos", [["something", "else"]])

    assert await workspace.check("sheet-a") == "invalid_layout"


async def test_check_raises_other_errors(fake: FakeSheets, workspace: GoogleSheetsWorkspace):
    fake.fail_on("spreadsheets.get", http_error(401), times=1)

    with pytest.raises(Exception, match="401"):
        await workspace.check("sheet-a")


def test_exposes_the_service_account_email(workspace: GoogleSheetsWorkspace):
    assert workspace.service_account_email == "bot@project.iam.gserviceaccount.com"
