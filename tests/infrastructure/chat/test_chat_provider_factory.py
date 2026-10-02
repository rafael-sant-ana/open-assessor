import pytest

from open_assessor.infrastructure.chat.chat_provider_factory import create_chat_provider
from open_assessor.infrastructure.chat.telegram_provider import TelegramProvider

TOKEN = {"TELEGRAM_BOT_TOKEN": "123:abc"}


def test_defaults_to_telegram():
    provider = create_chat_provider(env=TOKEN)

    assert isinstance(provider, TelegramProvider)
    assert provider.platform == "telegram"


def test_creates_the_telegram_provider():
    assert isinstance(create_chat_provider("telegram", env=TOKEN), TelegramProvider)


def test_reads_chat_provider_from_the_environment():
    assert isinstance(
        create_chat_provider(env={"CHAT_PROVIDER": "telegram", **TOKEN}), TelegramProvider
    )


def test_explains_that_whatsapp_is_not_available_yet():
    with pytest.raises(ValueError, match="WhatsApp is not available"):
        create_chat_provider("whatsapp", env=TOKEN)


def test_raises_for_an_unsupported_platform():
    with pytest.raises(ValueError, match='Unsupported CHAT_PROVIDER "signal"'):
        create_chat_provider("signal", env=TOKEN)
