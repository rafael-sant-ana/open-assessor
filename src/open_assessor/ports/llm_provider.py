from typing import Protocol

from open_assessor.ports.tool import ToolContext


class LLMProvider(Protocol):
    async def generate_response(self, chat_id: str, message: str, context: ToolContext) -> str: ...
