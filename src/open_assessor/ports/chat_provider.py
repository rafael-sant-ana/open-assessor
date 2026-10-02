from collections.abc import Awaitable, Callable
from typing import Protocol

from open_assessor.domain.messages import ChatPlatform, Message

type MessageListener = Callable[[Message], Awaitable[None]]
type Unsubscribe = Callable[[], None]


class ChatProvider(Protocol):
    @property
    def platform(self) -> ChatPlatform: ...

    @property
    def is_connected(self) -> bool: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def send_message(self, chat_id: str, text: str) -> None: ...

    async def send_typing(self, chat_id: str, active: bool) -> None: ...

    def on_message(self, listener: MessageListener) -> Unsubscribe: ...
