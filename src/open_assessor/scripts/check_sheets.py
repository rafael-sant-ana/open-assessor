"""Checks that expenses can be saved, without involving an LLM or a chat platform:
clock, credentials, access to the spreadsheet, then the real AddExpense use case
(add → read back → duplicate protection → undo).

    uv run check-sheets          leaves the sheet as it found it
    uv run check-sheets --keep   keeps the test row, to look at it in the spreadsheet
"""

import asyncio
import io
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv

from open_assessor.application.usecases.add_expense import (
    AddExpense,
    AddExpenseInput,
    Duplicate,
    Saved,
)
from open_assessor.domain.dates import DEFAULT_TIMEZONE, DateRange, today_in
from open_assessor.domain.expenses.money import format_brl
from open_assessor.infrastructure.expenses.expense_repository_factory import (
    create_expense_repository,
)

USER_ID = "script:check-sheets"
DESCRIPTION = "teste do check-sheets"

_HINTS = (
    (
        r"Token must be a short-lived token|iat and exp|invalid_grant",
        "Your computer clock is wrong. Sync it (Windows: Settings → Time & language → Sync now).",
    ),
    (
        r"Invalid JWT Signature",
        "Google does not accept this key: it was deleted or disabled, or belongs to another "
        "service account. Create a new JSON key for the service account and replace the file.",
    ),
    (
        r"Missing Google credentials",
        "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS in .env.",
    ),
    (
        r"No such file|FileNotFoundError|cannot find the file",
        "The file in GOOGLE_APPLICATION_CREDENTIALS does not exist. Check the path.",
    ),
    (
        r"not found|404",
        "Wrong SPREADSHEET_ID, or the spreadsheet is not shared with the service account email "
        "as Editor.",
    ),
    (
        r"permission|403",
        "Share the spreadsheet with the service account email as Editor, and enable the Google "
        "Sheets API in its project.",
    ),
    (
        r"unexpected headers",
        'A "gastos" tab already exists with a different header. Rename it or fix its header.',
    ),
)


class Report:
    def __init__(self) -> None:
        self.failed = False

    def ok(self, message: str) -> None:
        print(f"  ✔ {message}")

    def fail(self, message: str, error: object = None) -> None:
        self.failed = True
        print(f"  ✘ {message}")
        if error is None:
            return
        text = str(error) or type(error).__name__
        print(f"    {text}")
        hint = next((hint for pattern, hint in _HINTS if re.search(pattern, text, re.I)), None)
        if hint:
            print(f"    → {hint}")


def _google_time() -> datetime | None:
    request = urllib.request.Request("https://www.googleapis.com", method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            header: str | None = response.headers.get("date")
    except urllib.error.HTTPError as error:
        # An error status still carries the server's date.
        header = error.headers.get("date")
    except OSError:
        return None
    return parsedate_to_datetime(header) if header else None


async def check_clock(report: Report, timezone: str) -> None:
    print("1. Clock")
    remote = await asyncio.to_thread(_google_time)
    if remote is None:
        report.ok("Could not reach Google to compare time, skipping")
        return

    now = datetime.now(UTC)
    skew = round((now - remote).total_seconds())
    if abs(skew) > 60:
        direction = "behind" if skew < 0 else "ahead of"
        report.fail(
            f"Your clock is {abs(skew)}s {direction} Google's",
            "Google rejects logins when the clock is off by more than a few minutes.",
        )
    else:
        report.ok(
            f"In sync with Google (off by {skew}s). Today is {today_in(timezone, now)} in {timezone}"
        )


async def check(report: Report, keep: bool) -> None:
    timezone = os.environ.get("TIMEZONE") or DEFAULT_TIMEZONE
    message_key = f"script:check-sheets:{int(time.time() * 1000)}#0"

    print("Expense storage check\n")
    await check_clock(report, timezone)

    print("2. Storage")
    if not os.environ.get("SPREADSHEET_ID", "").strip():
        report.fail("SPREADSHEET_ID is not set, so expenses would only be kept in memory")
        return

    try:
        repository = (await create_expense_repository()).repository
        report.ok('Authenticated and the "gastos" tab is ready')
    except Exception as error:
        report.fail("Could not open the spreadsheet", error)
        return

    print("3. Add an expense (through the AddExpense use case)")
    add_expense = AddExpense(repository, lambda: datetime.now(UTC), timezone)
    input = AddExpenseInput(
        user_id=USER_ID,
        message_key=message_key,
        amount=12.34,
        description=DESCRIPTION,
        category="outros",
    )

    try:
        result = await add_expense.execute(input)
    except Exception as error:
        report.fail("Writing to the spreadsheet failed", error)
        return
    if not isinstance(result, Saved):
        report.fail(f'Expected "saved", got {result!r}')
        return
    report.ok(f"Saved {format_brl(result.expense.amount_cents)} dated {result.expense.date}")

    print("4. Read it back")
    try:
        today = today_in(timezone, datetime.now(UTC))
        found = await repository.list_by(USER_ID, DateRange(today, today))
        row = next((e for e in found if e.message_key == message_key), None)
        if row and row.amount_cents == 1234 and row.description == DESCRIPTION:
            report.ok("Found it with the right amount and description")
        else:
            report.fail("The expense was written but could not be read back correctly", found)
    except Exception as error:
        report.fail("Reading from the spreadsheet failed", error)

    print("5. Replaying the same message")
    try:
        replay = await add_expense.execute(input)
        if isinstance(replay, Duplicate):
            report.ok("Reported as a duplicate, no second row")
        else:
            report.fail(f'Expected "duplicate", got {replay!r}')
    except Exception as error:
        report.fail("Replay check failed", error)

    print("6. Cleanup")
    if keep:
        report.ok(f'Kept the test row (--keep). Look for "{DESCRIPTION}" in the spreadsheet')
        return
    try:
        removed = await repository.remove_last_by(USER_ID)
        if removed and removed.message_key == message_key:
            report.ok("Removed the test row")
        else:
            report.fail(f'Could not find the test row to remove. Delete "{DESCRIPTION}" by hand')
    except Exception as error:
        report.fail(f'Removing the test row failed. Delete "{DESCRIPTION}" by hand', error)


def run() -> None:
    # Windows consoles default to a legacy code page that cannot print ✔ and ✘.
    stdout = sys.stdout
    if isinstance(stdout, io.TextIOWrapper):
        stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportUnknownMemberType]
    load_dotenv()
    report = Report()
    asyncio.run(check(report, keep="--keep" in sys.argv[1:]))
    print(
        "\nFAILED: expenses cannot be saved yet."
        if report.failed
        else "\nOK: expenses can be saved."
    )
    sys.exit(1 if report.failed else 0)


if __name__ == "__main__":
    run()
