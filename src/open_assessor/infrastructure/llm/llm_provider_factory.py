import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset

from open_assessor.infrastructure.llm.pydantic_ai_provider import PydanticAIProvider
from open_assessor.ports.llm_provider import LLMProvider
from open_assessor.ports.tool import ToolContext


@dataclass(frozen=True, slots=True)
class _Entry:
    name: str
    api_key_variable: str
    model_variable: str
    default_model: str
    create: Callable[[str, str], Model]
    """(model name, API key) → model. The key is passed explicitly: pydantic-ai would look
    for GOOGLE_API_KEY, not GEMINI_API_KEY."""


# Order defines priority when more than one API key is configured.
_ENTRIES = (
    _Entry(
        "OpenAI",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "gpt-5.6-luna",
        lambda model, key: OpenAIResponsesModel(model, provider=OpenAIProvider(api_key=key)),
    ),
    _Entry(
        "Claude",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "claude-haiku-4-5-20251001",
        lambda model, key: AnthropicModel(model, provider=AnthropicProvider(api_key=key)),
    ),
    _Entry(
        "Gemini",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "gemini-3.6-flash",
        lambda model, key: GoogleModel(model, provider=GoogleProvider(api_key=key)),
    ),
)

LLM_API_KEY_VARIABLES = tuple(e.api_key_variable for e in _ENTRIES)


@dataclass(frozen=True, slots=True)
class CreatedLLMProvider:
    name: str
    model: Model
    provider: LLMProvider


def create_llm_provider(
    toolsets: list[AbstractToolset[ToolContext]] | None = None,
    env: Mapping[str, str] = os.environ,
) -> CreatedLLMProvider:
    entry = next((e for e in _ENTRIES if env.get(e.api_key_variable)), None)
    if entry is None:
        raise ValueError(
            "You must configure one of those environment variables: "
            + ", ".join(LLM_API_KEY_VARIABLES)
        )

    model = entry.create(
        env.get(entry.model_variable) or entry.default_model, env[entry.api_key_variable]
    )
    return CreatedLLMProvider(entry.name, model, PydanticAIProvider(model, toolsets))
