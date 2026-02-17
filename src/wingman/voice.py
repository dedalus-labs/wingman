"""Voice recording and transcription for Wingman."""

from __future__ import annotations

import io
import wave
from dataclasses import asdict, dataclass

import orjson as oj
from dedalus_labs import AsyncDedalus

from .config import CONFIG_DIR

SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM
BANK_FILE = CONFIG_DIR / "transcript_bank.json"

MODEL = "openai/gpt-4o-transcribe"


@dataclass
class TranscriptEntry:
    """One F2 listening session's full transcript."""

    timestamp: float
    text: str
    id: int


# --- Bank persistence ---


def load_bank() -> list[TranscriptEntry]:
    """Load transcript bank from disk."""
    if BANK_FILE.exists():
        try:
            data = oj.loads(BANK_FILE.read_bytes())
            return [TranscriptEntry(**e) for e in data]
        except Exception:
            return []
    return []


def save_bank(entries: list[TranscriptEntry]) -> None:
    """Save transcript bank to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BANK_FILE.write_bytes(oj.dumps([asdict(e) for e in entries], option=oj.OPT_INDENT_2))


# --- Recording ---


class VoiceRecorder:
    """Record from the default microphone using sounddevice."""

    def __init__(self) -> None:
        self._stream = None
        self._chunks: list[bytes] = []
        self._drain_cursor: int = 0

    @property
    def is_recording(self) -> bool:
        return self._stream is not None and self._stream.active

    def start(self) -> None:
        """Open the microphone and begin capturing audio."""
        import sounddevice as sd

        self._chunks = []
        self._drain_cursor = 0
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop capturing."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def drain(self) -> bytes:
        """Return WAV of audio captured since last drain, then advance cursor."""
        new_chunks = self._chunks[self._drain_cursor :]
        self._drain_cursor = len(self._chunks)
        return self._encode_wav(new_chunks)

    def _callback(self, indata, frames, time_info, status) -> None:
        self._chunks.append(bytes(indata))

    @staticmethod
    def _encode_wav(chunks: list[bytes]) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(chunks))
        buf.seek(0)
        return buf.read()


# --- Transcription ---


async def transcribe(client: AsyncDedalus, audio_wav: bytes, language: str = "en") -> str:
    """Send WAV audio to the Dedalus API and return transcribed text."""
    result = await client.audio.transcriptions.create(
        file=("recording.wav", audio_wav, "audio/wav"),
        model=MODEL,
        language=language,
        response_format="json",
        temperature=0.0,
    )
    return result.text.strip() if result.text else ""
