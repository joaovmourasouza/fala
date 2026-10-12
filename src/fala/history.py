"""Histórico de ditados em SQLite. Cada chamada abre a própria conexão (usado de threads de trabalho)."""

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

CATEGORIES = ("prompt", "trabalho", "pessoal", "documento", "email", "outro")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    duration REAL NOT NULL,
    raw TEXT NOT NULL,
    text TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'outro'
);
CREATE INDEX IF NOT EXISTS dictations_ts ON dictations (ts);
"""


@dataclass(frozen=True)
class Dictation:
    id: int
    ts: float
    duration: float
    raw: str
    text: str
    category: str


def db_path() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "fala" / "history.db"


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.executescript(SCHEMA)
    return conn


def add(duration: float, raw: str, text: str, category: str, ts: float | None = None) -> None:
    if category not in CATEGORIES:
        category = "outro"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO dictations (ts, duration, raw, text, category) VALUES (?, ?, ?, ?, ?)",
            (time.time() if ts is None else ts, duration, raw, text, category),
        )
    conn.close()


def all_entries() -> list[Dictation]:
    """Todos os ditados, do mais antigo ao mais recente."""
    with _connect() as conn:
        rows = conn.execute("SELECT id, ts, duration, raw, text, category FROM dictations ORDER BY ts").fetchall()
    conn.close()
    return [Dictation(*row) for row in rows]


def recent(limit: int = 200) -> list[Dictation]:
    """Os ditados mais recentes, do mais novo ao mais antigo."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, ts, duration, raw, text, category FROM dictations ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [Dictation(*row) for row in rows]
