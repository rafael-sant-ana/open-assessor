from typing import get_args

from open_assessor.application.security.allow_list import AllowList
from open_assessor.application.usecases.authorize_user import AlreadyAuthorized, AuthorizeUser
from open_assessor.application.usecases.connect_spreadsheet import (
    Connected,
    ConnectSpreadsheet,
    Unavailable,
)
from open_assessor.domain.messages import ChatPlatform, Message
from open_assessor.domain.users import User
from open_assessor.ports.spreadsheet_access import SpreadsheetAccess
from open_assessor.ports.user_repository import UserRepository

AUTHORIZE_COMMAND = "/autorizar"
REMOVE_COMMAND = "/remover"
SPREADSHEET_COMMAND = "/planilha"

ADMIN_ONLY_REPLY = "Só administradores podem usar esse comando."
NO_SPREADSHEETS_REPLY = "Este bot guarda os gastos em memória, então não usa planilhas."
INVALID_LINK_REPLY = "Não reconheci esse link. Envie o link da planilha do Google Sheets."
INVALID_LAYOUT_REPLY = (
    'Essa planilha já tem uma aba "gastos" que não foi criada por mim. '
    "Renomeie ou apague essa aba e tente de novo."
)
CONNECTED_REPLY = "Pronto! A partir de agora seus gastos vão para essa planilha."

_PLATFORMS: tuple[str, ...] = get_args(ChatPlatform.__value__)


class UserCommands:
    """Chat commands for managing who uses the bot and where their expenses go."""

    def __init__(
        self,
        users: UserRepository,
        admins: AllowList,
        authorize: AuthorizeUser,
        spreadsheets: SpreadsheetAccess | None,
    ) -> None:
        """`spreadsheets` is `None` when expenses are kept in memory."""
        self._users = users
        self._admins = admins
        self._authorize = authorize
        self._spreadsheets = spreadsheets
        self._connect = None if spreadsheets is None else ConnectSpreadsheet(users, spreadsheets)

    async def run(self, user: User, message: Message) -> str | None:
        """The reply to a command, or `None` if the message is not one."""
        command, _, argument = message.content.strip().partition(" ")
        argument = argument.strip()

        match command.lower():
            case "/planilha":
                return await self._connect_spreadsheet(user, argument)
            case "/autorizar" | "/remover" if not self._is_admin(message):
                return ADMIN_ONLY_REPLY
            case "/autorizar":
                return await self._authorize_user(user, message, argument)
            case "/remover":
                return await self._remove_user(message, argument)
            case _:
                return None

    def missing_spreadsheet_reply(self, user: User) -> str | None:
        """Instructions for a user who must connect a spreadsheet before saving expenses."""
        if self._spreadsheets is None or user.has_spreadsheet:
            return None
        return "Você ainda não conectou sua planilha.\n\n" + self._instructions()

    def _is_admin(self, message: Message) -> bool:
        return self._admins.is_allowed(message.platform, message.author)

    async def _connect_spreadsheet(self, user: User, link: str) -> str:
        if self._connect is None:
            return NO_SPREADSHEETS_REPLY
        if not link:
            return self._instructions()

        match await self._connect.execute(user, link):
            case Connected():
                return CONNECTED_REPLY
            case Unavailable(problem="invalid_layout"):
                return INVALID_LAYOUT_REPLY
            case Unavailable():
                return "Não consegui abrir essa planilha.\n\n" + self._instructions()
            case _:
                return INVALID_LINK_REPLY

    async def _authorize_user(self, admin: User, message: Message, argument: str) -> str:
        user_id = _parse_user_id(argument, message.platform)
        if user_id is None:
            return f"Use: {AUTHORIZE_COMMAND} <id>, com o id que a pessoa recebe em /meu-id."

        match await self._authorize.execute(user_id, admin.id):
            case AlreadyAuthorized():
                return f"{user_id} já estava autorizado."
            case _:
                next_step = (
                    "Ela já pode usar o bot."
                    if self._spreadsheets is None
                    else f"Peça para ela me enviar {SPREADSHEET_COMMAND} para conectar a planilha."
                )
                return f"{user_id} autorizado! {next_step}"

    async def _remove_user(self, message: Message, argument: str) -> str:
        user_id = _parse_user_id(argument, message.platform)
        if user_id is None:
            return f"Use: {REMOVE_COMMAND} <id>"
        # Admins come from ADMIN_USERS and would be recreated on the next start anyway.
        if user_id in self._admins.entries:
            return "Administradores são definidos em ADMIN_USERS e não podem ser removidos aqui."
        if not await self._users.delete(user_id):
            return f"{user_id} não estava autorizado."
        return f"{user_id} removido. A planilha dele não foi alterada."

    def _instructions(self) -> str:
        email = (self._spreadsheets and self._spreadsheets.service_account_email) or (
            "o e-mail da service account do bot"
        )
        return (
            "1. Crie uma planilha no Google Sheets.\n"
            f"2. Compartilhe com {email} como Editor.\n"
            f"3. Me envie: {SPREADSHEET_COMMAND} <link da planilha>"
        )


def _parse_user_id(argument: str, platform: ChatPlatform) -> str | None:
    """Accepts `platform:id` or a bare id on the admin's own platform."""
    if not argument or " " in argument:
        return None
    prefix, separator, id = argument.partition(":")
    if not separator:
        return f"{platform}:{argument}"
    return argument if prefix in _PLATFORMS and id else None
