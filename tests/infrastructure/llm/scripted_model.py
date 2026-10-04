from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

type Step = ModelResponse | Exception


def text(content: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content)])


def call(tool: str, args: dict[str, Any] | None = None, id: str = "call_1") -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool, args or {}, tool_call_id=id)])


class ScriptedModel:
    """A fake model that replies with the given steps, in order, and records every request."""

    def __init__(self, *steps: Step) -> None:
        self._steps = list(steps)
        self.requests: list[list[ModelMessage]] = []
        self.infos: list[AgentInfo] = []
        self.model = FunctionModel(self._reply)

    def _reply(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.requests.append(list(messages))
        self.infos.append(info)
        step = self._steps.pop(0) if self._steps else text("ok")
        if isinstance(step, Exception):
            raise step
        return step

    def tool_returns(self, request: int = -1) -> list[ToolReturnPart]:
        """Tool results the model received in a request (the last one by default)."""
        last = self.requests[request][-1]
        assert isinstance(last, ModelRequest)
        return [part for part in last.parts if isinstance(part, ToolReturnPart)]

    def retry_prompts(self, request: int = -1) -> list[RetryPromptPart]:
        last = self.requests[request][-1]
        assert isinstance(last, ModelRequest)
        return [part for part in last.parts if isinstance(part, RetryPromptPart)]
