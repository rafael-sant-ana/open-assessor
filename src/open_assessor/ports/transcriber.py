from typing import Protocol

from open_assessor.domain.messages import Audio


class Transcriber(Protocol):
    async def transcribe(self, audio: Audio) -> str: ...
