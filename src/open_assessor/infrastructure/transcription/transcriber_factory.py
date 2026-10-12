import os
from collections.abc import Mapping

from openai import AsyncOpenAI

from open_assessor.infrastructure.transcription.openai_transcriber import (
    DEFAULT_MODEL,
    OpenAITranscriber,
)
from open_assessor.ports.transcriber import Transcriber


def create_transcriber(env: Mapping[str, str] = os.environ) -> Transcriber | None:
    """Returns None when no OpenAI key is set: audio messages then get a polite refusal."""
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        return None

    model = env.get("OPENAI_TRANSCRIPTION_MODEL") or DEFAULT_MODEL
    return OpenAITranscriber(AsyncOpenAI(api_key=api_key), model)
