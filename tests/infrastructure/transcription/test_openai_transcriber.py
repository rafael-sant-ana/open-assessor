from types import SimpleNamespace
from typing import Any

from open_assessor.domain.messages import Audio
from open_assessor.infrastructure.transcription.openai_transcriber import OpenAITranscriber
from open_assessor.infrastructure.transcription.transcriber_factory import create_transcriber


class FakeTranscriptions:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


def fake_client(transcriptions: FakeTranscriptions) -> Any:
    return SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions))


async def test_sends_the_audio_as_a_named_file_in_portuguese():
    transcriptions = FakeTranscriptions("gastei 10 reais em pão")
    transcriber = OpenAITranscriber(fake_client(transcriptions), "whisper-1")

    text = await transcriber.transcribe(Audio(b"ogg-bytes", "voice.ogg", "audio/ogg"))

    assert text == "gastei 10 reais em pão"
    assert transcriptions.calls == [
        {
            "file": ("voice.ogg", b"ogg-bytes", "audio/ogg"),
            "model": "whisper-1",
            "language": "pt",
        }
    ]


async def test_strips_surrounding_whitespace():
    transcriber = OpenAITranscriber(fake_client(FakeTranscriptions("  oi \n")))

    assert await transcriber.transcribe(Audio(b"", "voice.ogg", "audio/ogg")) == "oi"


def test_factory_returns_none_without_an_openai_key():
    assert create_transcriber({"GEMINI_API_KEY": "x"}) is None


def test_factory_builds_an_openai_transcriber_without_touching_the_network():
    assert isinstance(create_transcriber({"OPENAI_API_KEY": "sk-test"}), OpenAITranscriber)
