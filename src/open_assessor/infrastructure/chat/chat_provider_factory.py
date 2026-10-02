import os
from collections.abc import Callable, Mapping

from open_assessor.infrastructure.chat.telegram_provider import TelegramProvider
from open_assessor.ports.chat_provider import ChatProvider

DEFAULT_PLATFORM = "telegram"

_PROVIDERS: dict[str, Callable[[Mapping[str, str]], ChatProvider]] = {
    "telegram": lambda env: TelegramProvider(env=env),
}


def create_chat_provider(
    platform: str | None = None, env: Mapping[str, str] = os.environ
) -> ChatProvider:
    platform = platform or env.get("CHAT_PROVIDER") or DEFAULT_PLATFORM

    if platform == "whatsapp":
        raise ValueError(
            "WhatsApp is not available in this version: it is coming back through a separate "
            "gateway. Use CHAT_PROVIDER=telegram for now."
        )

    create = _PROVIDERS.get(platform)
    if create is None:
        raise ValueError(
            f'Unsupported CHAT_PROVIDER "{platform}". Supported: {", ".join(_PROVIDERS)}'
        )

    return create(env)
