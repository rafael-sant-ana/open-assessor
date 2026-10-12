import asyncio
import os
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv

from open_assessor.application.handlers.message_handler import MessageHandler
from open_assessor.application.handlers.user_commands import UserCommands
from open_assessor.application.security.allow_list import AllowList
from open_assessor.application.security.authorizer import Authorizer
from open_assessor.application.usecases.add_expense import AddExpense
from open_assessor.application.usecases.authorize_user import AuthorizeUser
from open_assessor.application.usecases.list_expenses import ListExpenses
from open_assessor.application.usecases.seed_users import SeedUsers
from open_assessor.domain.dates import DEFAULT_TIMEZONE
from open_assessor.domain.messages import Message
from open_assessor.infrastructure.chat.chat_provider_factory import create_chat_provider
from open_assessor.infrastructure.expenses.expense_storage_factory import create_expense_storage
from open_assessor.infrastructure.llm.llm_provider_factory import create_llm_provider
from open_assessor.infrastructure.llm.toolset import build_toolset
from open_assessor.infrastructure.logging.std_logger import StdLogger, configure_logging
from open_assessor.infrastructure.transcription.transcriber_factory import create_transcriber
from open_assessor.infrastructure.users.user_repository_factory import create_user_repository


class ConfigurationError(Exception):
    pass


def clock() -> datetime:
    return datetime.now(UTC)


async def main() -> None:
    logger = StdLogger("main")

    allow_list = AllowList.from_env()
    admins = AllowList.from_csv(os.environ.get("ADMIN_USERS", ""))
    if allow_list.is_empty and admins.is_empty:
        raise ConfigurationError(
            "You must configure one of those environment variables: ADMIN_USERS, "
            "ALLOWED_USERS or ALLOWED_JIDS. Check the .env.example"
        )

    logger.debug("Initializing...")
    users = await create_user_repository()
    if users.persistent:
        logger.info(f"Using {users.name} user storage")
    else:
        logger.warning("MONGODB_URL is not set: users added with /autorizar are lost on restart")

    storage = await create_expense_storage(users.repository)
    if storage.persistent:
        logger.info(f"Using {storage.name} expense storage")
    else:
        logger.warning(
            "SPREADSHEET_ID and MONGODB_URL are not set: expenses are kept in memory and lost "
            "on restart"
        )

    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip() or None
    await SeedUsers(users.repository, clock).execute(
        admins.entries + allow_list.entries, spreadsheet_id
    )
    timezone = os.environ.get("TIMEZONE") or DEFAULT_TIMEZONE

    toolset = build_toolset(
        AddExpense(storage.repository, clock, timezone),
        ListExpenses(storage.repository),
        clock,
        timezone,
    )
    llm = create_llm_provider([toolset])
    logger.info(f"Using {llm.name} LLM provider ({llm.model.model_name})")

    chat = create_chat_provider()
    logger.info(f"Using {chat.platform} chat provider")

    transcriber = create_transcriber()
    if transcriber is None:
        logger.warning("OPENAI_API_KEY is not set: audio messages will not be transcribed")

    commands = UserCommands(
        users.repository, admins, AuthorizeUser(users.repository, clock), storage.spreadsheets
    )
    handler = MessageHandler(
        llm.provider,
        Authorizer(users.repository),
        commands,
        StdLogger("handler"),
        transcriber,
    )

    async def on_message(message: Message) -> None:
        await handler.handle(message, chat)

    chat.on_message(on_message)

    logger.debug("Connecting...")
    await chat.connect()
    logger.info("The bot is ready!")

    try:
        await asyncio.Event().wait()
    finally:
        # Ctrl+C cancels main(), which lands here.
        await chat.disconnect()
        await users.close()


def run() -> None:
    load_dotenv()
    # pydantic-ai otherwise prints a promotional banner into the logs on the first run.
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    configure_logging()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except (ConfigurationError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
