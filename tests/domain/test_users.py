import pytest

from open_assessor.domain.users import User, parse_spreadsheet_id

SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz_0123456789-ab"


@pytest.mark.parametrize(
    "text",
    [
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}",
        f"  {SHEET_ID}  ",
    ],
)
def test_parses_a_spreadsheet_link_or_bare_id(text: str):
    assert parse_spreadsheet_id(text) == SHEET_ID


@pytest.mark.parametrize("text", ["", "planilha", "https://example.com/doc", "abc def"])
def test_rejects_text_that_is_not_a_spreadsheet(text: str):
    assert parse_spreadsheet_id(text) is None


def test_connecting_a_spreadsheet_keeps_everything_else():
    user = User("telegram:1", "telegram:9", "2026-10-01T12:00:00.000Z")

    connected = user.connect_spreadsheet("sheet")

    assert not user.has_spreadsheet
    assert connected.has_spreadsheet
    assert connected == User("telegram:1", "telegram:9", "2026-10-01T12:00:00.000Z", "sheet")
