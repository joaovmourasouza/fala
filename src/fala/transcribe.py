import io
import os
import threading
import wave
from typing import Protocol

import httpx
import numpy as np

from .audio import SAMPLE_RATE
from .config import Config


class Transcriber(Protocol):
    def load(self) -> None: ...
    def transcribe(self, audio: np.ndarray) -> str: ...


class LocalWhisper:
    """faster-whisper rodando na CPU (ou GPU, se houver)."""

    def __init__(self, model: str, language: str):
        self._model_name = model
        self._language = language
        self._model = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as e:
                    raise RuntimeError("faster-whisper não instalado: pip install -e '.[local]'") from e
                self._model = WhisperModel(self._model_name, device="auto", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        segments, _ = self._model.transcribe(audio, language=self._language, beam_size=5, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()


class GroqWhisper:
    """Whisper hospedado na Groq (API compatível com OpenAI)."""

    URL = "https://api.groq.com/openai/v1/audio/transcriptions"

    def __init__(self, model: str, language: str):
        self._model = model
        self._language = language

    def load(self) -> None:
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("defina GROQ_API_KEY para usar transcriber = 'groq'")

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        response = httpx.post(
            self.URL,
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            files={"file": ("audio.wav", _to_wav(audio), "audio/wav")},
            data={"model": self._model, "language": self._language, "response_format": "json"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["text"].strip()


def _to_wav(audio: np.ndarray) -> bytes:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def make_transcriber(config: Config) -> Transcriber:
    if config.transcriber == "groq":
        return GroqWhisper(config.whisper_model, config.language)
    return LocalWhisper(config.whisper_model, config.language)
