import copy
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httplib2
from googleapiclient.errors import HttpError

type Row = list[Any]


def http_error(status: int) -> HttpError:
    return HttpError(httplib2.Response({"status": status}), f"HTTP {status}".encode())


@dataclass
class _Tab:
    sheet_id: int
    rows: list[Row]


@dataclass
class _FailurePlan:
    error: Exception
    left: int
    apply_before_failing: bool
    """Apply the write before raising, like a request whose response got lost."""


@dataclass
class FakeSheets:
    """In-memory stand-in for the `SheetsApi` methods the repository uses."""

    tabs: dict[str, _Tab] = field(default_factory=dict[str, _Tab])
    formats: list[Any] = field(default_factory=list[Any])
    calls: list[tuple[str, dict[str, Any]]] = field(
        default_factory=list[tuple[str, dict[str, Any]]]
    )
    _failures: dict[str, _FailurePlan] = field(default_factory=dict[str, _FailurePlan])
    _next_sheet_id: int = 1

    def seed_tab(self, title: str, rows: list[Row]) -> None:
        """Pre-existing tab, e.g. one with a foreign header."""
        self.tabs[title] = _Tab(self._next_sheet_id, rows)
        self._next_sheet_id += 1

    def fail_on(
        self, method: str, error: Exception, times: int, *, apply_before_failing: bool = False
    ) -> None:
        self._failures[method] = _FailurePlan(error, times, apply_before_failing)

    def calls_to(self, method: str) -> list[dict[str, Any]]:
        return [params for name, params in self.calls if name == method]

    def rows(self, title: str = "gastos") -> list[Row]:
        return self.tabs[title].rows

    async def spreadsheets_get(self, **params: Any) -> dict[str, Any]:
        return self._run(
            "spreadsheets.get",
            params,
            lambda: {
                "sheets": [
                    {"properties": {"sheetId": tab.sheet_id, "title": title}}
                    for title, tab in self.tabs.items()
                ]
            },
        )

    async def spreadsheets_batch_update(self, **params: Any) -> dict[str, Any]:
        return self._run(
            "spreadsheets.batchUpdate",
            params,
            lambda: {"replies": [self._apply(r) for r in params["body"]["requests"]]},
        )

    async def values_get(self, **params: Any) -> dict[str, Any]:
        def read() -> dict[str, Any]:
            rows = self._tab(params["range"]).rows
            selected = rows[:1] if params["range"].endswith("A1:G1") else rows
            # Like the real API, an empty range has no `values` at all.
            return {"values": copy.deepcopy(selected)} if selected else {}

        return self._run("values.get", params, read)

    async def values_update(self, **params: Any) -> dict[str, Any]:
        def update() -> dict[str, Any]:
            rows = self._tab(params["range"]).rows
            header = copy.deepcopy(params["body"]["values"][0])
            if rows:
                rows[0] = header
            else:
                rows.append(header)
            return {}

        return self._run("values.update", params, update)

    async def values_append(self, **params: Any) -> dict[str, Any]:
        def append() -> dict[str, Any]:
            self._tab(params["range"]).rows.append(copy.deepcopy(params["body"]["values"][0]))
            return {}

        return self._run("values.append", params, append)

    def _run(
        self, method: str, params: dict[str, Any], action: Callable[[], dict[str, Any]]
    ) -> dict[str, Any]:
        self.calls.append((method, copy.deepcopy(params)))

        plan = self._failures.get(method)
        if plan and plan.left > 0:
            plan.left -= 1
            if plan.apply_before_failing:
                action()
            raise plan.error

        return action()

    def _apply(self, request: dict[str, Any]) -> dict[str, Any]:
        if "addSheet" in request:
            title = request["addSheet"]["properties"]["title"]
            self.seed_tab(title, [])
            return {
                "addSheet": {"properties": {"sheetId": self.tabs[title].sheet_id, "title": title}}
            }
        if "repeatCell" in request:
            self.formats.append(request["repeatCell"])
            return {}
        if "deleteDimension" in request:
            target = request["deleteDimension"]["range"]
            tab = next(t for t in self.tabs.values() if t.sheet_id == target["sheetId"])
            del tab.rows[target["startIndex"] : target["endIndex"]]
            return {}
        raise ValueError(f"FakeSheets: unsupported request {next(iter(request))}")

    def _tab(self, range: str) -> _Tab:
        match = re.match(r"^'(.+)'!", range)
        assert match, f"FakeSheets: bad range {range}"
        return self.tabs[match.group(1)]
