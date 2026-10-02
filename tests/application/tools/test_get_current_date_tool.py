import json
from datetime import UTC, datetime

from open_assessor.application.tools.get_current_date_tool import GetCurrentDateTool
from open_assessor.ports.tool import ToolContext

CONTEXT = ToolContext(user_id="telegram:1", message_key="telegram:10:100")


async def test_returns_the_day_and_weekday_in_the_configured_timezone():
    # 02:30 UTC on Oct 2nd is still Thursday Oct 1st in São Paulo.
    tool = GetCurrentDateTool(lambda: datetime(2026, 10, 2, 2, 30, tzinfo=UTC), "America/Sao_Paulo")

    assert json.loads(await tool.execute({}, CONTEXT)) == {
        "date": "2026-10-01",
        "weekday": "quinta-feira",
        "timezone": "America/Sao_Paulo",
    }


async def test_reads_the_clock_on_every_call_so_a_long_running_process_never_goes_stale():
    now = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
    tool = GetCurrentDateTool(lambda: now, "America/Sao_Paulo")

    first = json.loads(await tool.execute({}, CONTEXT))["date"]
    now = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)
    second = json.loads(await tool.execute({}, CONTEXT))["date"]

    assert first == "2026-10-01"
    assert second == "2026-10-02"
