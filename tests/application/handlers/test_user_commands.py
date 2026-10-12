from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from open_assessor.application.handlers.user_commands import (
    ADMIN_ONLY_REPLY,
    CONNECTED_REPLY,
    INVALID_LAYOUT_REPLY,
    INVALID_LINK_REPLY,
    NO_SPREADSHEETS_REPLY,
    UserCommands,
)
from open_assessor.application.security.allow_list import AllowList
from open_assessor.application.usecases.authorize_user import AuthorizeUser
from open_assessor.domain.messages import Message, MessageUser
from open_assessor.domain.users import User
from open_assessor.infrastructure.users.in_memory_user_repository import InMemoryUserRepository
from open_assessor.ports.spreadsheet_access import SpreadsheetProblem

SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz_0123456789-ab"
SHEET_LINK = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
ADMIN = User("telegram:1", "env", "2026-10-01T12:00:00.000Z")
MEMBER = User("telegram:2", "telegram:1", "2026-10-01T12:00:00.000Z")


@dataclass
class FakeSpreadsheets:
    problem: SpreadsheetProblem | None = None
    service_account_email: str | None = "bot@project.iam.gserviceaccount.com"
    checked: list[str] = field(default_factory=list[str])

    async def check(self, spreadsheet_id: str) -> SpreadsheetProblem | None:
        self.checked.append(spreadsheet_id)
        return self.problem


class Setup:
    def __init__(self, spreadsheets: FakeSpreadsheets | None) -> None:
        self.users = InMemoryUserRepository([ADMIN, MEMBER])
        self.commands = UserCommands(
            self.users,
            AllowList.from_csv("telegram:1"),
            AuthorizeUser(self.users, lambda: datetime(2026, 10, 2, tzinfo=UTC)),
            spreadsheets,
        )

    async def run(self, user: User, content: str) -> str | None:
        author = MessageUser(user.id.removeprefix("telegram:"))
        message = Message(id="1", platform="telegram", author=author, content=content, chat_id="1")
        return await self.commands.run(user, message)


@pytest.fixture
def spreadsheets() -> FakeSpreadsheets:
    return FakeSpreadsheets()


@pytest.fixture
def setup(spreadsheets: FakeSpreadsheets) -> Setup:
    return Setup(spreadsheets)


async def test_ignores_messages_that_are_not_commands(setup: Setup):
    assert await setup.run(MEMBER, "gastei 10 no mercado") is None


class TestAuthorize:
    async def test_admin_authorizes_a_bare_id_on_their_own_platform(self, setup: Setup):
        reply = await setup.run(ADMIN, "/autorizar 3")

        assert (
            reply
            == "telegram:3 autorizado! Peça para ela me enviar /planilha para conectar a planilha."
        )
        assert await setup.users.get("telegram:3") == User(
            "telegram:3", "telegram:1", "2026-10-02T00:00:00.000Z"
        )

    async def test_accepts_a_platform_prefixed_id(self, setup: Setup):
        await setup.run(ADMIN, "/AUTORIZAR whatsapp:5511999@s.whatsapp.net")

        assert await setup.users.get("whatsapp:5511999@s.whatsapp.net") is not None

    async def test_does_not_touch_an_existing_user(self, setup: Setup):
        reply = await setup.run(ADMIN, "/autorizar telegram:2")

        assert reply == "telegram:2 já estava autorizado."
        assert await setup.users.get("telegram:2") == MEMBER

    @pytest.mark.parametrize("argument", ["", "slack:3", "telegram:", "1 2"])
    async def test_explains_the_usage_for_a_bad_id(self, setup: Setup, argument: str):
        reply = await setup.run(ADMIN, f"/autorizar {argument}")

        assert reply is not None and reply.startswith("Use: /autorizar")

    async def test_is_admin_only(self, setup: Setup):
        assert await setup.run(MEMBER, "/autorizar 3") == ADMIN_ONLY_REPLY
        assert await setup.users.get("telegram:3") is None


class TestRemove:
    async def test_admin_removes_a_user(self, setup: Setup):
        reply = await setup.run(ADMIN, "/remover 2")

        assert reply == "telegram:2 removido. A planilha dele não foi alterada."
        assert await setup.users.get("telegram:2") is None

    async def test_reports_an_unknown_user(self, setup: Setup):
        assert await setup.run(ADMIN, "/remover 3") == "telegram:3 não estava autorizado."

    async def test_refuses_to_remove_an_admin(self, setup: Setup):
        reply = await setup.run(ADMIN, "/remover 1")

        assert reply is not None and "ADMIN_USERS" in reply
        assert await setup.users.get("telegram:1") is not None

    async def test_is_admin_only(self, setup: Setup):
        assert await setup.run(MEMBER, "/remover 1") == ADMIN_ONLY_REPLY


class TestConnectSpreadsheet:
    async def test_saves_a_spreadsheet_the_bot_can_use(
        self, setup: Setup, spreadsheets: FakeSpreadsheets
    ):
        reply = await setup.run(MEMBER, f"/planilha {SHEET_LINK}")

        assert reply == CONNECTED_REPLY
        assert spreadsheets.checked == [SHEET_ID]
        assert await setup.users.get("telegram:2") == MEMBER.connect_spreadsheet(SHEET_ID)

    async def test_explains_how_to_share_when_the_bot_has_no_access(
        self, setup: Setup, spreadsheets: FakeSpreadsheets
    ):
        spreadsheets.problem = "not_shared"

        reply = await setup.run(MEMBER, f"/planilha {SHEET_LINK}")

        assert reply is not None and reply.startswith("Não consegui abrir essa planilha.")
        assert "bot@project.iam.gserviceaccount.com" in reply
        assert await setup.users.get("telegram:2") == MEMBER

    async def test_reports_a_foreign_expenses_tab(
        self, setup: Setup, spreadsheets: FakeSpreadsheets
    ):
        spreadsheets.problem = "invalid_layout"

        assert await setup.run(MEMBER, f"/planilha {SHEET_LINK}") == INVALID_LAYOUT_REPLY

    async def test_rejects_something_that_is_not_a_link(
        self, setup: Setup, spreadsheets: FakeSpreadsheets
    ):
        assert await setup.run(MEMBER, "/planilha minha planilha") == INVALID_LINK_REPLY
        assert spreadsheets.checked == []

    async def test_shows_the_instructions_without_a_link(self, setup: Setup):
        reply = await setup.run(MEMBER, "/planilha")

        assert reply is not None and "bot@project.iam.gserviceaccount.com" in reply

    async def test_is_unavailable_when_expenses_live_in_memory(self):
        assert await Setup(None).run(MEMBER, "/planilha x") == NO_SPREADSHEETS_REPLY


class TestMissingSpreadsheetReply:
    def test_asks_users_without_a_spreadsheet_to_connect_one(self, setup: Setup):
        reply = setup.commands.missing_spreadsheet_reply(MEMBER)

        assert reply is not None and "/planilha" in reply

    def test_is_none_once_connected(self, setup: Setup):
        assert setup.commands.missing_spreadsheet_reply(MEMBER.connect_spreadsheet("s")) is None

    def test_is_none_when_expenses_live_in_memory(self):
        assert Setup(None).commands.missing_spreadsheet_reply(MEMBER) is None
