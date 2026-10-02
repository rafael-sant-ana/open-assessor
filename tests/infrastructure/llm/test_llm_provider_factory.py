import pytest

from open_assessor.infrastructure.llm.claude_llm_provider import ClaudeLLMProvider
from open_assessor.infrastructure.llm.gemini_llm_provider import GeminiLLMProvider
from open_assessor.infrastructure.llm.llm_provider_factory import create_llm_provider
from open_assessor.infrastructure.llm.openai_llm_provider import OpenAILLMProvider
from tests.infrastructure.llm.fixtures import GreeterTool


def test_creates_the_openai_provider_when_only_openai_api_key_is_set():
    created = create_llm_provider(env={"OPENAI_API_KEY": "openai-key"})

    assert created.name == "OpenAI"
    assert isinstance(created.provider, OpenAILLMProvider)


def test_creates_the_claude_provider_when_only_anthropic_api_key_is_set():
    created = create_llm_provider(env={"ANTHROPIC_API_KEY": "anthropic-key"})

    assert created.name == "Claude"
    assert isinstance(created.provider, ClaudeLLMProvider)


def test_creates_the_gemini_provider_when_only_gemini_api_key_is_set():
    created = create_llm_provider(env={"GEMINI_API_KEY": "gemini-key"})

    assert created.name == "Gemini"
    assert isinstance(created.provider, GeminiLLMProvider)


def test_prefers_openai_over_claude_and_gemini_when_all_keys_are_set():
    env = {"OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g"}

    assert create_llm_provider(env=env).name == "OpenAI"


def test_prefers_claude_over_gemini_when_openai_is_not_configured():
    env = {"ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "g"}

    assert create_llm_provider(env=env).name == "Claude"


def test_passes_the_tools_on_to_the_created_provider():
    created = create_llm_provider([GreeterTool()], env={"ANTHROPIC_API_KEY": "anthropic-key"})

    assert isinstance(created.provider, ClaudeLLMProvider)
    assert [t.name for t in created.provider.tools] == ["greet"]


def test_ignores_keys_set_to_an_empty_string():
    env = {"OPENAI_API_KEY": "", "GEMINI_API_KEY": "gemini-key"}

    assert create_llm_provider(env=env).name == "Gemini"


def test_raises_listing_every_accepted_variable_when_no_key_is_configured():
    with pytest.raises(ValueError, match="OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY"):
        create_llm_provider(env={})
