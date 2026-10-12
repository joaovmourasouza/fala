"""Números do painel Insights, calculados a partir do histórico. Sem dependência de Qt."""

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .history import CATEGORIES, Dictation

TYPING_WPM = 40
WORDS_PER_BOOK = 60_000
WORDS_PER_PAGE = 300
FILLERS = {"hã", "ahn", "hum", "éh", "é", "tipo", "né"}

_WORD = re.compile(r"\w+")


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


@dataclass
class Fixes:
    corrected: int = 0
    fillers: int = 0

    @property
    def total(self) -> int:
        return self.corrected + self.fillers


@dataclass
class Stats:
    total_words: int = 0
    dictations: int = 0
    wpm: float = 0.0
    speaking_seconds: float = 0.0
    fixes: Fixes = field(default_factory=Fixes)
    month_growth: float | None = None  # fração: 0.022 = +2,2%
    categories: Counter = field(default_factory=Counter)
    words_by_day: dict[date, int] = field(default_factory=dict)
    current_streak: int = 0
    longest_streak: int = 0
    streak_days: set[date] = field(default_factory=set)

    @property
    def speed_ratio(self) -> float:
        return self.wpm / TYPING_WPM

    @property
    def gauge(self) -> float:
        return min(self.wpm / 200, 1.0)

    @property
    def typing_seconds(self) -> float:
        return self.total_words / TYPING_WPM * 60

    @property
    def saved_seconds(self) -> float:
        return max(0.0, self.typing_seconds - self.speaking_seconds)


def count_fixes(raw: str, final: str) -> Fixes:
    a, b = words(raw), words(final)
    fillers = sum(1 for w in a if w in FILLERS) - sum(1 for w in b if w in FILLERS)
    fillers = max(0, fillers)
    changed = 0
    for tag, i1, i2, _, _ in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            changed += i2 - i1
    return Fixes(corrected=max(0, changed - fillers), fillers=fillers)


def streaks(days: set[date], today: date) -> tuple[int, int, set[date]]:
    """(sequência atual, maior sequência, dias da sequência atual). A atual vale até ontem se hoje ainda não teve ditado."""
    longest = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        longest = max(longest, run)
        prev = d
    current_days: set[date] = set()
    d = today if today in days else today - timedelta(days=1)
    while d in days:
        current_days.add(d)
        d -= timedelta(days=1)
    return len(current_days), longest, current_days


def _month_start(d: date) -> date:
    return d.replace(day=1)


def compute(entries: list[Dictation], now: datetime | None = None) -> Stats:
    now = now or datetime.now()
    today = now.date()
    s = Stats()
    timed_words = 0
    timed_seconds = 0.0
    this_month = _month_start(today)
    last_month = _month_start(this_month - timedelta(days=1))
    month_words = Counter()
    by_day: Counter = Counter()

    for e in entries:
        n = word_count(e.text)
        s.total_words += n
        s.dictations += 1
        s.speaking_seconds += e.duration
        if e.duration >= 1:
            timed_words += n
            timed_seconds += e.duration
        f = count_fixes(e.raw, e.text)
        s.fixes.corrected += f.corrected
        s.fixes.fillers += f.fillers
        s.categories[e.category if e.category in CATEGORIES else "outro"] += 1
        d = datetime.fromtimestamp(e.ts).date()
        by_day[d] += n
        month_words[_month_start(d)] += n

    s.wpm = timed_words / (timed_seconds / 60) if timed_seconds else 0.0
    if month_words[last_month]:
        s.month_growth = (month_words[this_month] - month_words[last_month]) / month_words[last_month]
    s.words_by_day = dict(by_day)
    s.current_streak, s.longest_streak, s.streak_days = streaks(set(by_day), today)
    return s


def written_message(total_words: int) -> str:
    books = total_words // WORDS_PER_BOOK
    if books >= 1:
        return f"Você já escreveu {books} {'livro completo' if books == 1 else 'livros completos'}!"
    pages = total_words // WORDS_PER_PAGE
    if pages >= 1:
        return f"Você já escreveu {pages} {'página' if pages == 1 else 'páginas'}!"
    return "Sua primeira página está a caminho."


def format_duration(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    h, m = divmod(minutes, 60)
    if h:
        return f"{h} h {m:02d} min"
    return f"{m} min"


def format_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")
