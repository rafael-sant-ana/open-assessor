from openai import AsyncOpenAI

from open_assessor.domain.messages import Audio

DEFAULT_MODEL = "gpt-4o-mini-transcribe"
LANGUAGE = "pt"
"""The assistant speaks Portuguese; a language hint makes short voice notes more accurate."""


class OpenAITranscriber:
    def __init__(self, client: AsyncOpenAI, model: str = DEFAULT_MODEL) -> None:
        self._client = client
        self._model = model

    async def transcribe(self, audio: Audio) -> str:
        transcription = await self._client.audio.transcriptions.create(
            file=(audio.file_name, audio.data, audio.mime_type),
            model=self._model,
            language=LANGUAGE,
        )
        return transcription.text.strip()
