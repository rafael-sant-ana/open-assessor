import pytest
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIResponsesModel

from open_assessor.infrastructure.llm.llm_provider_factory import create_llm_provider
from open_assessor.infrastructure.llm.pydantic_ai_provider import PydanticAIProvider


def test_uses_openai_when_only_openai_api_key_is_set():
    created = create_llm_provider(env={"OPENAI_API_KEY": "openai-key"})

    assert created.name == "OpenAI"
    assert isinstance(created.model, OpenAIResponsesModel)
    assert isinstance(created.provider, PydanticAIProvider)


def test_uses_claude_when_only_anthropic_api_key_is_set():
    created = create_llm_provider(env={"ANTHROPIC_API_KEY": "anthropic-key"})

    assert created.name == "Claude"
    assert isinstance(created.model, AnthropicModel)


def test_uses_gemini_when_only_gemini_api_key_is_set():
    created = create_llm_provider(env={"GEMINI_API_KEY": "gemini-key"})

    assert created.name == "Gemini"
    assert isinstance(created.model, GoogleModel)


def test_prefers_openai_over_claude_and_gemini_when_all_keys_are_set():
    env = {"OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g"}

    assert create_llm_provider(env=env).name == "OpenAI"


def test_prefers_claude_over_gemini_when_openai_is_not_configured():
    env = {"ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g"}

    assert create_llm_provider(env=env).name == "Claude"


def test_ignores_keys_set_to_an_empty_string():
    env = {"OPENAI_API_KEY": "", "GEMINI_API_KEY": "gemini-key"}

    assert create_llm_provider(env=env).name == "Gemini"


@pytest.mark.parametrize(
    ("env", "default"),
    [
        ({"OPENAI_API_KEY": "k"}, "gpt-5.6-luna"),
        ({"ANTHROPIC_API_KEY": "k"}, "claude-haiku-4-5-20251001"),
        ({"GEMINI_API_KEY": "k"}, "gemini-3.6-flash"),
    ],
)
def test_uses_a_default_model_per_provider(env: dict[str, str], default: str):
    assert create_llm_provider(env=env).model.model_name == default


@pytest.mark.parametrize(
    "env",
    [
        {"OPENAI_API_KEY": "k", "OPENAI_MODEL": "custom-model"},
        {"ANTHROPIC_API_KEY": "k", "ANTHROPIC_MODEL": "custom-model"},
        {"GEMINI_API_KEY": "k", "GEMINI_MODEL": "custom-model"},
    ],
)
def test_reads_the_model_from_the_environment(env: dict[str, str]):
    assert create_llm_provider(env=env).model.model_name == "custom-model"


def test_raises_listing_every_accepted_variable_when_no_key_is_configured():
    with pytest.raises(ValueError, match="OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY"):
        create_llm_provider(env={})
