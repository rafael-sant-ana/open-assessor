from datetime import UTC, datetime

import pytest

from open_assessor.domain.dates import is_valid_iso_date, today_in, weekday_in


class TestIsValidIsoDate:
    def test_accepts_real_calendar_days(self):
        assert is_valid_iso_date("2026-10-01")
        assert is_valid_iso_date("2028-02-29")

    @pytest.mark.parametrize(
        "value",
        [
            "2026-02-30",
            "2027-02-29",
            "2026-13-01",
            "01/10/2026",
            "2026-1-1",
            "20261001",
            "",
            42,
            None,
        ],
    )
    def test_rejects_impossible_days_and_other_formats(self, value: object):
        assert not is_valid_iso_date(value)


class TestTodayIn:
    def test_uses_the_timezone_not_utc(self):
        # 02:30 UTC on Oct 2nd is still Oct 1st in São Paulo (UTC-3).
        now = datetime(2026, 10, 2, 2, 30, tzinfo=UTC)

        assert today_in("America/Sao_Paulo", now) == "2026-10-01"
        assert today_in("UTC", now) == "2026-10-02"


class TestWeekdayIn:
    def test_returns_the_portuguese_weekday_in_the_timezone(self):
        now = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)

        assert weekday_in("America/Sao_Paulo", now) == "quinta-feira"
