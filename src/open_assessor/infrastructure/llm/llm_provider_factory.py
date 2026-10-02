import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from open_assessor.infrastructure.llm.claude_llm_provider import ClaudeLLMProvider
from open_assessor.infrastructure.llm.gemini_llm_provider import GeminiLLMProvider
from open_assessor.infrastructure.llm.openai_llm_provider import OpenAILLMProvider
from open_assessor.ports.llm_provider import LLMProvider
from open_assessor.ports.tool import Tool


@dataclass(frozen=True, slots=True)
class _Entry:
    name: str
    api_key_variable: str
    create: Callable[[Sequence[Tool], Mapping[str, str]], LLMProvider]


# Order defines priority when more than one API key is configured.
_ENTRIES = (
    _Entry("OpenAI", "OPENAI_API_KEY", lambda tools, env: OpenAILLMProvider(tools, env=env)),
    _Entry("Claude", "ANTHROPIC_API_KEY", lambda tools, env: ClaudeLLMProvider(tools, env=env)),
    _Entry("Gemini", "GEMINI_API_KEY", lambda tools, env: GeminiLLMProvider(tools, env=env)),
)

LLM_API_KEY_VARIABLES = tuple(e.api_key_variable for e in _ENTRIES)


@dataclass(frozen=True, slots=True)
class CreatedLLMProvider:
    name: str
    provider: LLMProvider


def create_llm_provider(
    tools: Sequence[Tool] = (), env: Mapping[str, str] = os.environ
) -> CreatedLLMProvider:
    entry = next((e for e in _ENTRIES if env.get(e.api_key_variable)), None)
    if entry is None:
        raise ValueError(
            "You must configure one of those environment variables: "
            + ", ".join(LLM_API_KEY_VARIABLES)
        )

    return CreatedLLMProvider(entry.name, entry.create(tools, env))
