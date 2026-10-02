from collections.abc import Mapping

from open_assessor.application.tools._json import to_json
from open_assessor.domain.dates import DEFAULT_TIMEZONE, Clock, today_in, weekday_in
from open_assessor.ports.tool import ToolContext


class GetCurrentDateTool:
    name = "get_current_date"
    description = (
        "Returns today's date and weekday. Call it before resolving any relative date or period "
        '("hoje", "ontem", "sexta passada", "esse mês", "semana passada") '
        "for add_expense or list_expenses."
    )
    parameters: Mapping[str, object] = {"type": "object", "properties": {}}

    def __init__(self, clock: Clock, timezone: str = DEFAULT_TIMEZONE) -> None:
        self._clock = clock
        self._timezone = timezone

    async def execute(self, args: Mapping[str, object], context: ToolContext) -> str:
        now = self._clock()
        return to_json(
            {
                "date": today_in(self._timezone, now),
                "weekday": weekday_in(self._timezone, now),
                "timezone": self._timezone,
            }
        )
