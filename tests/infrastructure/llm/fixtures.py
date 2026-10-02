from collections.abc import Mapping
from dataclasses import dataclass, field

from open_assessor.ports.tool import ToolContext

CTX = ToolContext(user_id="telegram:1", message_key="telegram:10:100")

EMPTY_SCHEMA: Mapping[str, object] = {"type": "object", "properties": {}}


class GreeterTool:
    """Minimal tool with an optional argument, used to exercise the providers' tool loops."""

    name = "greet"
    description = "Greets someone."
    parameters: Mapping[str, object] = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
    }

    async def execute(self, args: Mapping[str, object], context: ToolContext) -> str:
        name = args.get("name")
        return f"Hello, {name if isinstance(name, str) else 'World'}!"


class BrokenTool:
    name = "broken"
    description = "always fails"
    parameters = EMPTY_SCHEMA

    async def execute(self, args: Mapping[str, object], context: ToolContext) -> str:
        raise RuntimeError("boom")


@dataclass
class SpyTool:
    name: str = "spy"
    description: str = "records its context"
    parameters: Mapping[str, object] = field(default_factory=lambda: EMPTY_SCHEMA)
    seen: list[ToolContext] = field(default_factory=list[ToolContext])

    async def execute(self, args: Mapping[str, object], context: ToolContext) -> str:
        self.seen.append(context)
        return "ok"
