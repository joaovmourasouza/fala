import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class Recorder:
    """Grava do microfone em mono 16 kHz, o formato que o Whisper espera."""

    def __init__(self, device: str = "", on_level: Callable[[float], None] | None = None):
        self._device = int(device) if device.isdigit() else (device or None)
        self._on_level = on_level
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        with self._lock:
            self._chunks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=SAMPLE_RATE // 20,
            device=self._device,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
            self._chunks = []
        return audio

    def _callback(self, indata, frames, time, status) -> None:
        chunk = indata[:, 0].copy()
        with self._lock:
            self._chunks.append(chunk)
        if self._on_level:
            self._on_level(float(np.sqrt(np.mean(chunk**2))))
