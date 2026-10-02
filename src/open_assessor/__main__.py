import asyncio
import os
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv

from open_assessor.application.handlers.message_handler import MessageHandler
from open_assessor.application.security.allow_list import AllowList
from open_assessor.application.tools.add_expense_tool import AddExpenseTool
from open_assessor.application.tools.get_current_date_tool import GetCurrentDateTool
from open_assessor.application.tools.list_expenses_tool import ListExpensesTool
from open_assessor.application.usecases.add_expense import AddExpense
from open_assessor.application.usecases.list_expenses import ListExpenses
from open_assessor.domain.dates import DEFAULT_TIMEZONE
from open_assessor.domain.messages import Message
from open_assessor.infrastructure.chat.chat_provider_factory import create_chat_provider
from open_assessor.infrastructure.expenses.expense_repository_factory import (
    create_expense_repository,
)
from open_assessor.infrastructure.llm.llm_provider_factory import create_llm_provider
from open_assessor.infrastructure.logging.std_logger import StdLogger, configure_logging


class ConfigurationError(Exception):
    pass


def clock() -> datetime:
    return datetime.now(UTC)


async def main() -> None:
    logger = StdLogger("main")

    allow_list = AllowList.from_env()
    if allow_list.is_empty:
        raise ConfigurationError(
            "You must configure one of those environment variables: ALLOWED_USERS or "
            "ALLOWED_JIDS. Check the .env.example"
        )

    logger.debug("Initializing...")
    storage = await create_expense_repository()
    if storage.persistent:
        logger.info(f"Using {storage.name} expense storage")
    else:
        logger.warning("SPREADSHEET_ID is not set: expenses are kept in memory and lost on restart")
    timezone = os.environ.get("TIMEZONE") or DEFAULT_TIMEZONE

    llm = create_llm_provider(
        [
            AddExpenseTool(AddExpense(storage.repository, clock, timezone)),
            ListExpensesTool(ListExpenses(storage.repository)),
            GetCurrentDateTool(clock, timezone),
        ]
    )
    logger.info(f"Using {llm.name} LLM provider")

    chat = create_chat_provider()
    logger.info(f"Using {chat.platform} chat provider")

    handler = MessageHandler(llm.provider, allow_list, StdLogger("handler"))

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


def run() -> None:
    load_dotenv()
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
