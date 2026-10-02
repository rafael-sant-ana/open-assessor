import asyncio

import pytest

from open_assessor.domain.dates import DateRange
from open_assessor.infrastructure.expenses.google_sheets_expense_repository import (
    SHEET_HEADER,
    GoogleSheetsExpenseRepository,
    Sleep,
)
from tests.factories import make_expense
from tests.infrastructure.expenses.expense_repository_contract import ExpenseRepositoryContract
from tests.infrastructure.expenses.fake_sheets import FakeSheets, http_error

SPREADSHEET_ID = "sheet-id"


async def no_sleep(seconds: float) -> None:
    pass


async def create(fake: FakeSheets, sleep: Sleep = no_sleep) -> GoogleSheetsExpenseRepository:
    return await GoogleSheetsExpenseRepository.create(fake, SPREADSHEET_ID, sleep=sleep)


class TestGoogleSheetsExpenseRepositoryContract(ExpenseRepositoryContract):
    @pytest.fixture
    async def repo(self) -> GoogleSheetsExpenseRepository:
        return await create(FakeSheets())


class TestSchema:
    async def test_creates_the_gastos_tab_with_header_and_formats_when_missing(self):
        fake = FakeSheets()
        await create(fake)

        assert fake.rows() == [list(SHEET_HEADER)]
        types = [f["cell"]["userEnteredFormat"]["numberFormat"]["type"] for f in fake.formats]
        assert types == ["DATE", "CURRENCY"]

    async def test_writes_the_header_into_an_existing_empty_tab(self):
        fake = FakeSheets()
        fake.seed_tab("gastos", [])
        await create(fake)

        assert fake.rows() == [list(SHEET_HEADER)]

    async def test_leaves_a_valid_existing_tab_and_its_rows_untouched(self):
        fake = FakeSheets()
        fake.seed_tab("gastos", [list(SHEET_HEADER), [46000, 10, "x", "outros", "t", "k", "u"]])
        await create(fake)

        assert len(fake.rows()) == 2
        assert fake.calls_to("values.update") == []

    async def test_refuses_to_touch_a_tab_with_unexpected_headers(self):
        fake = FakeSheets()
        fake.seed_tab("gastos", [["date", "amount"]])

        with pytest.raises(RuntimeError, match="unexpected headers"):
            await create(fake)
        assert fake.rows() == [["date", "amount"]]

    async def test_ignores_other_tabs(self):
        fake = FakeSheets()
        fake.seed_tab("Dashboard", [["charts live here"]])
        await create(fake)

        assert fake.rows("Dashboard") == [["charts live here"]]


class TestWrites:
    async def test_appends_typed_values_with_raw_input_a_serial_date_and_a_decimal_amount(self):
        fake = FakeSheets()
        repo = await create(fake)

        await repo.add(make_expense(date="2026-10-01", amount_cents=5090))

        [append] = fake.calls_to("values.append")
        assert append["valueInputOption"] == "RAW"
        assert append["insertDataOption"] == "INSERT_ROWS"
        assert append["body"]["values"][0] == [
            46296,  # days since 1899-12-30
            50.9,
            "burger king",
            "alimentacao",
            "2026-10-01T12:00:00.000Z",
            "telegram:10:100#0",
            "telegram:1",
        ]

    async def test_deletes_exactly_the_row_of_the_removed_expense_and_leaves_the_header(self):
        fake = FakeSheets()
        repo = await create(fake)
        await repo.add(make_expense(message_key="k1"))
        await repo.add(make_expense(message_key="k2", description="segundo"))
        await repo.add(make_expense(message_key="k3", user_id="telegram:2"))

        await repo.remove_last_by("telegram:1")

        assert [row[5] for row in fake.rows()] == ["message_key", "k1", "k3"]

    async def test_does_not_write_a_duplicate_key_twice_in_parallel(self):
        fake = FakeSheets()
        repo = await create(fake)

        await asyncio.gather(*(repo.add(make_expense()) for _ in range(3)))

        assert len(fake.calls_to("values.append")) == 1


class TestMessageKeyCache:
    async def test_reads_the_sheet_once_for_any_number_of_existence_checks_and_adds(self):
        fake = FakeSheets()
        repo = await create(fake)
        reads_before = len(fake.calls_to("values.get"))

        await repo.exists_by_message_key("a")
        await repo.add(make_expense(message_key="a"))
        await repo.add(make_expense(message_key="b"))
        await repo.exists_by_message_key("b")

        assert len(fake.calls_to("values.get")) - reads_before == 1

    async def test_knows_the_keys_already_in_the_sheet_after_a_restart(self):
        fake = FakeSheets()
        await (await create(fake)).add(make_expense())

        restarted = await create(fake)

        assert await restarted.exists_by_message_key("telegram:10:100#0")


class TestReading:
    async def test_skips_malformed_rows_instead_of_failing(self):
        fake = FakeSheets()
        fake.seed_tab(
            "gastos",
            [
                list(SHEET_HEADER),
                ["not a date", 10, "x", "outros", "t", "k1", "telegram:1"],
                [46296, 10, "x", "viagem", "t", "k2", "telegram:1"],
                [46296],
                [46296, 12.5, "bom", "outros", "2026-10-01T12:00:00.000Z", "k3", "telegram:1"],
            ],
        )
        repo = await create(fake)

        found = await repo.list_by("telegram:1", DateRange("2026-01-01", "2026-12-31"))

        assert [e.message_key for e in found] == ["k3"]
        assert found[0].amount_cents == 1250


class TestRetries:
    async def test_retries_a_rate_limited_write_with_backoff_and_then_succeeds(self):
        fake = FakeSheets()
        sleeps: list[float] = []

        async def record(seconds: float) -> None:
            sleeps.append(seconds)

        repo = await create(fake, record)
        fake.fail_on("values.append", http_error(429), times=2)

        await repo.add(make_expense())

        assert sleeps == [0.2, 0.4]
        assert len(fake.rows()) == 2

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(http_error(503), id="server error"),
            pytest.param(ConnectionResetError("reset"), id="connection reset"),
            pytest.param(TimeoutError("timed out"), id="timeout"),
        ],
    )
    async def test_retries_server_errors_and_network_errors(self, error: Exception):
        fake = FakeSheets()
        repo = await create(fake)
        fake.fail_on("values.append", error, times=1)

        await repo.add(make_expense())

        assert len(fake.rows()) == 2

    async def test_gives_up_after_three_attempts_and_reports_the_error(self):
        fake = FakeSheets()
        repo = await create(fake)
        fake.fail_on("values.append", http_error(500), times=10)

        with pytest.raises(Exception, match="HTTP 500"):
            await repo.add(make_expense())
        assert len(fake.calls_to("values.append")) == 3

    async def test_does_not_retry_client_errors(self):
        fake = FakeSheets()
        repo = await create(fake)
        fake.fail_on("values.append", http_error(404), times=10)

        with pytest.raises(Exception, match="HTTP 404"):
            await repo.add(make_expense())
        assert len(fake.calls_to("values.append")) == 1

    async def test_does_not_write_twice_when_a_failed_attempt_had_actually_reached_the_sheet(self):
        fake = FakeSheets()
        repo = await create(fake)
        fake.fail_on("values.append", http_error(503), times=1, apply_before_failing=True)

        await repo.add(make_expense())

        assert len(fake.rows()) == 2
        assert await repo.exists_by_message_key("telegram:10:100#0")

    async def test_keeps_working_after_a_failed_operation(self):
        fake = FakeSheets()
        repo = await create(fake)
        fake.fail_on("values.append", http_error(404), times=1)

        with pytest.raises(Exception, match="HTTP 404"):
            await repo.add(make_expense(message_key="lost"))
        await repo.add(make_expense(message_key="fine"))

        assert await repo.exists_by_message_key("fine")
        assert not await repo.exists_by_message_key("lost")
