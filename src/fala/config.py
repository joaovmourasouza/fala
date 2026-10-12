import os
import sys
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "fala" / "config.toml"

DEFAULT_WHISPER_MODELS = {
    "local": "small",
    "groq": "whisper-large-v3-turbo",
}


@dataclass
class Config:
    language: str = "pt"
    transcriber: str = "local"
    whisper_model: str = ""
    cleanup: bool = True
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "low"
    paste_keys: str = "ctrl+v"
    audio_device: str = ""
    max_seconds: int = 300

    def __post_init__(self):
        if self.transcriber not in DEFAULT_WHISPER_MODELS:
            raise ValueError(f"transcriber inválido: {self.transcriber!r} (use 'local' ou 'groq')")
        if not self.whisper_model:
            self.whisper_model = DEFAULT_WHISPER_MODELS[self.transcriber]


def load(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    with path.open("rb") as f:
        data = tomllib.load(f)
    known = {f.name for f in fields(Config)}
    for key in data.keys() - known:
        print(f"fala: ignorando opção desconhecida em {path}: {key}", file=sys.stderr)
    return Config(**{k: v for k, v in data.items() if k in known})
