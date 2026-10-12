"""Janela principal: painel Insights (estatísticas) e histórico de ditados."""

import functools
import math
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from . import history, portal, stats
from .config import CONFIG_PATH

REPO_URL = "https://github.com/joaovmourasouza/fala"
CONTENT_MAX_WIDTH = 1100
NARROW_WIDTH = 1000  # abaixo disso (largura da janela), os cards empilham

THEMES = {
    "light": {
        "outer": "#F3F2F7",
        "panel": "#FBFBFD",
        "card": "#F5F4FA",
        "border": "#E5E3EE",
        "divider": "#D8D6E3",
        "text": "#1E1E24",
        "muted": "#6C6A78",
        "track": "#E3E1EC",
        "active": "#E7E5F0",
        "bars": ["#3B3D8F", "#5B5FC7", "#8F93E3"],
        "heat": ["#DCDDF8", "#A9ACEE", "#6E72D6", "#3B3D8F"],
        "missed": "#D9D6E6",
        "future": "#EFEEF5",
        "streak_outline": "#2A2C6B",
        "badge_bg": "#E7E8FB",
        "badge_fg": "#3B3D8F",
        "on_teal": "#FFFFFF",
        "toast_bg": "#1E1E24",
        "toast_fg": "#FFFFFF",
    },
    "dark": {
        "outer": "#151519",
        "panel": "#1C1C21",
        "card": "#232329",
        "border": "#303038",
        "divider": "#3B3B45",
        "text": "#ECEBF2",
        "muted": "#9D9BAA",
        "track": "#36363F",
        "active": "#2C2C34",
        "bars": ["#7A7EE0", "#5F63C4", "#4A4DA0"],
        "heat": ["#2B2C52", "#3F4290", "#6064C8", "#9A9DF0"],
        "missed": "#34323C",
        "future": "#222228",
        "streak_outline": "#C9CBF8",
        "badge_bg": "#2A2B4D",
        "badge_fg": "#B9BCF6",
        "on_teal": "#FFFFFF",
        "toast_bg": "#ECEBF2",
        "toast_fg": "#1E1E24",
    },
}

T = dict(THEMES["light"])

CATEGORY_INFO = [
    ("prompt", "robot", "PROMPTS DE IA", "Prompt de IA"),
    ("trabalho", "chat", "MENSAGENS DE TRABALHO", "Trabalho"),
    ("pessoal", "bubble", "MENSAGENS PESSOAIS", "Pessoal"),
    ("documento", "x-office-document-symbolic", "DOCUMENTOS", "Documento"),
    ("email", "mail-unread-symbolic", "E-MAILS", "E-mail"),
    ("outro", "infinity", "OUTRAS TAREFAS", "Outro"),
]
CATEGORY_LABELS = {key: chip for key, _, _, chip in CATEGORY_INFO}

WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


# ---------------------------------------------------------------- fontes e ícones


def font_family() -> str:
    families = set(QFontDatabase.families())
    for name in ("Adwaita Sans", "Cantarell", "Open Sans"):
        if name in families:
            return name
    return QApplication.font().family()


def make_font(size: float, weight: QFont.Weight = QFont.Weight.Normal, spacing: float = 0) -> QFont:
    f = QFont(font_family())
    f.setPixelSize(round(size))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def _paint_glyph(p: QPainter, name: str, s: float) -> None:
    """Glifos desenhados à mão para o que o Adwaita não tem. Coordenadas em um quadrado s×s."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    k = s / 24
    if name == "chart":
        p.drawRoundedRect(QRectF(3 * k, 3 * k, 18 * k, 18 * k), 3 * k, 3 * k)
        for x, top in ((8, 11), (12, 7), (16, 13)):
            p.drawLine(QPointF(x * k, top * k), QPointF(x * k, 17 * k))
    elif name == "robot":
        p.drawRoundedRect(QRectF(4 * k, 8 * k, 16 * k, 12 * k), 3 * k, 3 * k)
        p.drawLine(QPointF(12 * k, 8 * k), QPointF(12 * k, 4.5 * k))
        p.drawEllipse(QPointF(12 * k, 3.5 * k), 1.2 * k, 1.2 * k)
        p.drawLine(QPointF(2 * k, 13 * k), QPointF(2 * k, 16 * k))
        p.drawLine(QPointF(22 * k, 13 * k), QPointF(22 * k, 16 * k))
        p.drawEllipse(QPointF(9 * k, 13 * k), 0.8 * k, 0.8 * k)
        p.drawEllipse(QPointF(15 * k, 13 * k), 0.8 * k, 0.8 * k)
        p.drawLine(QPointF(10 * k, 17 * k), QPointF(14 * k, 17 * k))
    elif name == "chat":
        path = QPainterPath()
        path.addRoundedRect(QRectF(3 * k, 4 * k, 18 * k, 13 * k), 2 * k, 2 * k)
        p.drawPath(path)
        p.drawLine(QPointF(7 * k, 17 * k), QPointF(7 * k, 21 * k))
        p.drawLine(QPointF(7 * k, 21 * k), QPointF(11 * k, 17 * k))
        for y in (8.5, 12.5):
            p.drawLine(QPointF(7 * k, y * k), QPointF(17 * k, y * k))
    elif name == "bubble":
        p.drawEllipse(QRectF(3 * k, 3.5 * k, 18 * k, 16 * k))
        p.drawLine(QPointF(5.5 * k, 16.5 * k), QPointF(3.5 * k, 21 * k))
        p.drawLine(QPointF(3.5 * k, 21 * k), QPointF(8.5 * k, 19 * k))
        for x in (8, 12, 16):
            p.drawPoint(QPointF(x * k, 11.5 * k))
    elif name == "infinity":
        path = QPainterPath()
        path.moveTo(12 * k, 12 * k)
        path.cubicTo(9 * k, 7 * k, 3 * k, 7.5 * k, 3 * k, 12 * k)
        path.cubicTo(3 * k, 16.5 * k, 9 * k, 17 * k, 12 * k, 12 * k)
        path.cubicTo(15 * k, 7 * k, 21 * k, 7.5 * k, 21 * k, 12 * k)
        path.cubicTo(21 * k, 16.5 * k, 15 * k, 17 * k, 12 * k, 12 * k)
        p.drawPath(path)
    elif name == "question":
        p.drawEllipse(QRectF(3 * k, 3 * k, 18 * k, 18 * k))
        path = QPainterPath()
        path.moveTo(9.3 * k, 9.5 * k)
        path.cubicTo(9.3 * k, 6.2 * k, 14.8 * k, 6.2 * k, 14.8 * k, 9.5 * k)
        path.cubicTo(14.8 * k, 11.8 * k, 12 * k, 11.8 * k, 12 * k, 14 * k)
        p.drawPath(path)
        p.drawPoint(QPointF(12 * k, 17.2 * k))


@functools.cache
def _symbolic_icon(name: str) -> QIcon:
    """SVG do Adwaita: primeiro a cópia empacotada (o runtime do Flatpak não tem o tema),
    depois o disco, porque o Qt do pip nem sempre enxerga o tema do sistema."""
    bundled = Path(__file__).parent / "icons" / f"{name}.svg"
    if bundled.exists():
        return QIcon(str(bundled))
    dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    dirs += ["/usr/share", "/run/host/usr/share", str(Path.home() / ".local/share")]
    for base in dirs:
        for path in Path(base, "icons", "Adwaita", "symbolic").glob(f"*/{name}.svg"):
            return QIcon(str(path))
    return QIcon.fromTheme(name)


def icon_pixmap(name: str, size: int, color: str) -> QPixmap:
    """Ícone Adwaita simbólico recolorido, ou um glifo próprio."""
    dpr = QApplication.primaryScreen().devicePixelRatio() if QApplication.primaryScreen() else 1.0
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if name.endswith("-symbolic"):
        _symbolic_icon(name).paint(p, 0, 0, size, size)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(QRectF(0, 0, size, size), QColor(color))
    else:
        pen = QPen(QColor(color), max(1.4, size / 14))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        _paint_glyph(p, name, size)
    p.end()
    return pm


def icon_label(name: str, size: int, color_key: str = "text") -> QLabel:
    label = QLabel()
    label.setPixmap(icon_pixmap(name, size, T[color_key]))
    label.setFixedSize(size, size)
    label.setStyleSheet("background: transparent;")
    return label


def text_label(
    text: str,
    size: float,
    color_key: str = "text",
    weight: QFont.Weight = QFont.Weight.Normal,
    spacing: float = 0,
) -> QLabel:
    label = QLabel(text)
    label.setFont(make_font(size, weight, spacing))
    label.setStyleSheet(f"color: {T[color_key]}; background: transparent;")
    return label


def caps_label(text: str, color_key: str = "muted", size: float = 12.5) -> QLabel:
    return text_label(text.upper(), size, color_key, QFont.Weight.Medium, 1.4)


# ---------------------------------------------------------------- blocos visuais


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(T["border"]), 1))
        p.setBrush(QColor(T["card"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)


class Divider(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(1)

    def paintEvent(self, event) -> None:
        QPainter(self).fillRect(self.rect(), QColor(T["divider"]))


class Gauge(QWidget):
    def __init__(self, fill: float, caption: str, value: str):
        super().__init__()
        self._fill, self._caption, self._value = fill, caption, value
        self.setMinimumSize(150, 96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        thick = 15.0
        size = min(self.width() * 0.72, (self.height() - thick / 2) * 2)
        size = max(size, 80)
        rect = QRectF(thick / 2, thick / 2, size - thick, size - thick)
        pen = QPen(QColor(T["track"]), thick)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 180 * 16, -180 * 16)
        if self._fill > 0:
            pen.setColor(QColor(T["bars"][0]))
            p.setPen(pen)
            p.drawArc(rect, 180 * 16, -round(180 * 16 * self._fill))
        cx = rect.center().x()
        p.setPen(QColor(T["muted"]))
        p.setFont(make_font(14))
        p.drawText(QRectF(cx - 80, rect.center().y() - size * 0.30, 160, 20), Qt.AlignmentFlag.AlignCenter, self._caption)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(21, QFont.Weight.Medium))
        p.drawText(QRectF(cx - 80, rect.center().y() - size * 0.15, 160, 30), Qt.AlignmentFlag.AlignCenter, self._value)


class SplitBar(QWidget):
    """Barra de duas cores (tempo economizado vs. tempo falando)."""

    def __init__(self, left: tuple[str, str, float], right: tuple[str, str, float]):
        super().__init__()
        self._left, self._right = left, right
        self.setFixedHeight(22)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        gap = 4
        total = self._left[2] + self._right[2]
        share = self._left[2] / total if total else 0.5
        p.setFont(make_font(13))
        fm = p.fontMetrics()
        min_l = fm.horizontalAdvance(self._left[1]) + 44
        min_r = fm.horizontalAdvance(self._right[1]) + 44
        w = self.width() - gap
        left_w = min(max(w * share, min_l), w - min_r)
        segments = [
            (QRectF(0, 0, left_w, self.height()), T["bars"][0], *self._left[:2]),
            (QRectF(left_w + gap, 0, w - left_w, self.height()), T["bars"][2], *self._right[:2]),
        ]
        for rect, color, icon, text in segments:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(rect, 3, 3)
            p.drawPixmap(QPointF(rect.x() + 8, rect.y() + 3), icon_pixmap(icon, 16, T["on_teal"]))
            p.setPen(QColor(T["on_teal"]))
            p.setFont(make_font(13))
            p.drawText(rect.adjusted(30, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter, text)


class CategoryRow(QWidget):
    def __init__(self, icon: str, share: float, max_share: float, rank: int, label: str):
        super().__init__()
        self._icon, self._share, self._max, self._rank, self._label = icon, share, max_share, rank, label
        self.setFixedHeight(28)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(QPointF(0, 5), icon_pixmap(self._icon, 22, T["text"]))
        x0 = 36
        label_font = make_font(13, QFont.Weight.Medium, 1.3)
        p.setFont(label_font)
        label_w = p.fontMetrics().horizontalAdvance(self._label) + 16
        avail = max(60, self.width() - x0 - label_w)
        bar_w = max(38, (self._share / self._max if self._max else 0) * min(avail, (self.width() - x0) * 0.58))
        bar = QRectF(x0, 2, bar_w, self.height() - 4)
        color = T["bars"][min(self._rank, 2)]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(bar, 3, 3)
        p.setPen(QColor(T["on_teal"]))
        p.setFont(make_font(13, QFont.Weight.Medium, 1.0))
        p.drawText(bar, Qt.AlignmentFlag.AlignCenter, f"{round(self._share * 100)}%")
        p.setPen(QColor(T["text"]))
        p.setFont(label_font)
        p.drawText(QRectF(bar.right() + 14, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignVCenter, self._label)


class Heatmap(QWidget):
    """Calendário de atividade: colunas são semanas (domingo a sábado)."""

    COLS = 19

    def __init__(self, s: stats.Stats, first_day: date | None):
        super().__init__()
        self._s = s
        self._first_day = first_day
        self._page = 0
        self._cells: list[tuple[QRectF, date]] = []
        self._prev_rect = QRectF()
        self._next_rect = QRectF()
        self.setMouseTracking(True)
        self.setFixedHeight(232)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _range(self) -> tuple[date, date]:
        today = date.today()
        this_week = today - timedelta(days=(today.weekday() + 1) % 7)
        last_col = this_week - timedelta(weeks=self.COLS * self._page)
        return last_col - timedelta(weeks=self.COLS - 1), last_col

    def _can_go_back(self) -> bool:
        start, _ = self._range()
        return self._first_day is not None and self._first_day < start

    @staticmethod
    def level(words: int) -> int:
        if words >= 600:
            return 4
        if words >= 250:
            return 3
        if words >= 80:
            return 2
        return 1 if words > 0 else 0

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        if self._prev_rect.contains(pos) and self._can_go_back():
            self._page += 1
            self.update()
        elif self._next_rect.contains(pos) and self._page > 0:
            self._page -= 1
            self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        for rect, d in self._cells:
            if rect.contains(pos):
                n = self._s.words_by_day.get(d, 0)
                QToolTip.showText(event.globalPosition().toPoint(), f"{d:%d/%m/%Y}: {stats.format_int(n)} palavras", self)
                return
        QToolTip.hideText()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        today = date.today()
        start, _ = self._range()
        label_w = 38
        top = 30
        legend_h = 34
        avail_w = self.width() - label_w
        avail_h = self.height() - top - legend_h - 10
        cell = min(avail_w / (self.COLS + 0.42 * (self.COLS - 1)), avail_h / (7 + 0.42 * 6), 20)
        gap = cell * 0.42
        grid_w = self.COLS * cell + (self.COLS - 1) * gap
        x0 = label_w + (avail_w - grid_w)

        # navegação e meses
        p.setFont(make_font(13))
        arrow_color = lambda enabled: QColor(T["text"] if enabled else T["divider"])  # noqa: E731
        self._prev_rect = QRectF(x0 - 30, 0, 22, 22)
        self._next_rect = QRectF(x0 + grid_w - 14, 0, 22, 22)
        for rect, glyph, enabled in (
            (self._prev_rect, "go-previous-symbolic", self._can_go_back()),
            (self._next_rect, "go-next-symbolic", self._page > 0),
        ):
            p.drawPixmap(rect.topLeft() + QPointF(3, 3), icon_pixmap(glyph, 16, arrow_color(enabled).name()))
        p.setPen(QColor(T["muted"]))
        prev_month = None
        for col in range(self.COLS):
            week = start + timedelta(weeks=col)
            month = (week + timedelta(days=6)).month
            x = x0 + col * (cell + gap)
            if month != prev_month and col > 0 and x < x0 + grid_w - 40:
                p.drawText(QRectF(x, 2, 60, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, MONTHS[month - 1])
            prev_month = month

        # dias da semana
        p.setFont(make_font(12))
        for row, name in enumerate(WEEKDAYS):
            y = top + row * (cell + gap)
            p.drawText(QRectF(0, y, label_w, cell), Qt.AlignmentFlag.AlignVCenter, name)

        # células
        self._cells = []
        radius = cell * 0.18
        for col in range(self.COLS):
            for row in range(7):
                d = start + timedelta(weeks=col, days=row)
                rect = QRectF(x0 + col * (cell + gap), top + row * (cell + gap), cell, cell)
                if d > today or self._first_day is None or d < self._first_day:
                    color = T["future"]
                else:
                    lvl = self.level(self._s.words_by_day.get(d, 0))
                    color = T["heat"][lvl - 1] if lvl else T["missed"]
                    self._cells.append((rect, d))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(color))
                p.drawRoundedRect(rect, radius, radius)
                if d in self._s.streak_days:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(T["streak_outline"]), 1.4))
                    p.drawRoundedRect(rect.adjusted(-1.8, -1.8, 1.8, 1.8), radius + 1.5, radius + 1.5)

        # legenda
        ly = self.height() - 22
        p.setFont(make_font(14))
        p.setPen(QColor(T["muted"]))
        x = float(label_w) - 38
        fm = p.fontMetrics()
        p.drawText(QPointF(x, ly + 13), "Mais")
        x += fm.horizontalAdvance("Mais") + 10
        for color in reversed(T["heat"]):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(x, ly, 17, 17), 3, 3)
            x += 25
        p.setPen(QColor(T["muted"]))
        p.drawText(QPointF(x + 2, ly + 13), "Menos")
        text = "Sequência atual"
        tx = self.width() - fm.horizontalAdvance(text)
        p.drawText(QPointF(tx, ly + 13), text)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(T["streak_outline"]), 1.4))
        p.drawRoundedRect(QRectF(tx - 30, ly - 2, 20, 20), 4, 4)


class Tabs(QWidget):
    changed = pyqtSignal(int)

    def __init__(self, names: list[str]):
        super().__init__()
        self._names = names
        self.current = 0
        self.setFixedHeight(42)
        self._rects: list[QRectF] = []
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_current(self, index: int) -> None:
        self.current = index
        self.update()

    def mousePressEvent(self, event) -> None:
        for i, rect in enumerate(self._rects):
            if rect.contains(event.position()) and i != self.current:
                self.set_current(i)
                self.changed.emit(i)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(QRectF(0, self.height() - 1, self.width(), 1), QColor(T["border"]))
        font = make_font(16, QFont.Weight.Medium)
        p.setFont(font)
        fm = p.fontMetrics()
        x = 0.0
        self._rects = []
        for i, name in enumerate(self._names):
            w = fm.horizontalAdvance(name)
            rect = QRectF(x, 0, w, self.height() - 4)
            self._rects.append(rect)
            p.setPen(QColor(T["text"] if i == self.current else T["muted"]))
            p.drawText(rect, Qt.AlignmentFlag.AlignVCenter, name)
            if i == self.current:
                p.fillRect(QRectF(x, self.height() - 3, w, 3), QColor(T["text"]))
            x += w + 28


class SideButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon: str, tooltip: str, size: int = 46, icon_size: int = 22):
        super().__init__()
        self._icon = icon
        self._icon_size = icon_size
        self.active = False
        self._hover = False
        self.setFixedSize(size, size)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.active or self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T["active"]))
            p.drawRoundedRect(QRectF(self.rect()), 9, 9)
        offset = (self.width() - self._icon_size) / 2
        p.drawPixmap(QPointF(offset, offset), icon_pixmap(self._icon, self._icon_size, T["text"]))


class Panel(QWidget):
    """Painel claro arredondado que contém o conteúdo."""

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(T["border"]), 1))
        p.setBrush(QColor(T["panel"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, 20), 16, 16)


class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFont(make_font(14))
        self.hide()
        self._timer = QTimer(self, singleShot=True, interval=3500)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str) -> None:
        self.setStyleSheet(
            f"background: {T['toast_bg']}; color: {T['toast_fg']}; padding: 10px 18px; border-radius: 10px;"
        )
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 28)
        self.raise_()
        self.show()
        self._timer.start()


# ---------------------------------------------------------------- páginas


def _info(tooltip: str) -> QLabel:
    label = icon_label("help-about-symbolic", 16, "muted")
    label.setToolTip(tooltip)
    return label


def _stat_header(value: str, caption: str, info: str | None = None) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setSpacing(6)
    box.addWidget(text_label(value, 31, weight=QFont.Weight.Medium))
    row = QHBoxLayout()
    row.setSpacing(6)
    row.addWidget(caps_label(caption))
    if info:
        row.addWidget(_info(info))
    row.addStretch()
    box.addLayout(row)
    return box


def build_usage_page(s: stats.Stats, first_day: date | None, narrow: bool = False) -> QWidget:
    page = QWidget()
    grid = QGridLayout(page)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(20)
    grid.setVerticalSpacing(20)
    for col, stretch in enumerate((1, 1, 1, 1)):
        grid.setColumnStretch(col, stretch)

    if s.dictations == 0:
        hint = QLabel("Aperte <b>Super+D</b> e comece a falar. Seus números aparecem aqui.")
        hint.setFont(make_font(15))
        hint.setStyleSheet(
            f"color: {T['badge_fg']}; background: {T['badge_bg']}; border-radius: 8px; padding: 12px 16px;"
        )
        grid.addWidget(hint, 0, 0, 1, 4)

    row = grid.rowCount() if s.dictations == 0 else 0

    # Palavras por minuto
    wpm_card = Card()
    v = QVBoxLayout(wpm_card)
    v.setContentsMargins(22, 18, 22, 14)
    v.addLayout(_stat_header(
        stats.format_int(round(s.wpm)),
        "Palavras por minuto",
        f"Média do texto final por minuto de fala. Digitando, a média é {stats.TYPING_WPM} palavras por minuto.",
    ))
    ratio = f"{s.speed_ratio:.1f}×".replace(".", ",") if s.wpm else "—"
    v.addWidget(Gauge(s.gauge, "vs. digitar", ratio), 1)
    grid.addWidget(wpm_card, row, 0, 1, 2 if narrow else 1)

    # Correções
    fix_card = Card()
    v = QVBoxLayout(fix_card)
    v.setContentsMargins(22, 18, 22, 18)
    v.addLayout(_stat_header(stats.format_int(s.fixes.total), "Correções feitas pela Fala"))
    v.addSpacing(10)
    v.addWidget(Divider())
    v.addSpacing(10)
    for value, text, tip in (
        (s.fixes.corrected, "palavras corrigidas", "Palavras da transcrição que o ajuste trocou ou removeu."),
        (s.fixes.fillers, "muletas removidas", "Hesitações como “hã”, “tipo” e “né” que saíram do texto."),
    ):
        line = QHBoxLayout()
        line.addWidget(text_label(f"{stats.format_int(value)} {text}", 16))
        line.addStretch()
        line.addWidget(_info(tip))
        v.addLayout(line)
        v.addSpacing(8)
    v.addStretch()
    grid.addWidget(fix_card, row, 2 if narrow else 1, 1, 2 if narrow else 1)

    # Total de palavras
    total_card = Card()
    v = QVBoxLayout(total_card)
    v.setContentsMargins(22, 18, 22, 18)
    top = QHBoxLayout()
    top.addLayout(_stat_header(stats.format_int(s.total_words), "Total de palavras ditadas"))
    if s.month_growth is not None:
        sign = "↗" if s.month_growth >= 0 else "↘"
        pct = f"{abs(s.month_growth) * 100:.1f}".replace(".", ",")
        badge = QLabel(f"{sign} {pct}% este mês")
        badge.setFont(make_font(14))
        badge.setStyleSheet(f"color: {T['badge_fg']}; background: {T['badge_bg']}; border-radius: 4px; padding: 3px 8px;")
        top.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
    v.addLayout(top)
    v.addSpacing(10)
    v.addWidget(Divider())
    v.addSpacing(10)
    v.addWidget(text_label(stats.written_message(s.total_words), 16))
    v.addSpacing(10)
    v.addStretch()
    v.addWidget(SplitBar(
        ("document-open-recent-symbolic", f"Tempo economizado {stats.format_duration(s.saved_seconds)}", s.saved_seconds),
        ("audio-input-microphone-symbolic", f"Falando {stats.format_duration(s.speaking_seconds)}", s.speaking_seconds),
    ))
    total_row = row + 1 if narrow else row
    grid.addWidget(total_card, total_row, 0 if narrow else 2, 1, 4 if narrow else 2)

    # Uso por tipo
    usage_card = Card()
    v = QVBoxLayout(usage_card)
    v.setContentsMargins(22, 18, 22, 18)
    head = QHBoxLayout()
    head.addWidget(text_label("Uso por tipo", 30, weight=QFont.Weight.Medium))
    head.addStretch()
    head.addWidget(caps_label(f"Total de ditados | {stats.format_int(s.dictations)}", "text", 13))
    v.addLayout(head)
    v.addSpacing(12)
    total = sum(s.categories.values())
    shares = sorted(
        ((s.categories.get(key, 0) / total if total else 0, key) for key, *_ in CATEGORY_INFO),
        key=lambda item: -item[0],
    )
    max_share = shares[0][0] if shares else 0
    info = {key: (icon, label) for key, icon, label, _ in CATEGORY_INFO}
    for rank, (share, key) in enumerate(shares):
        icon, label = info[key]
        v.addWidget(CategoryRow(icon, share, max_share, rank, f"{stats.format_int(s.categories.get(key, 0))} {label}"))
        v.addSpacing(6)
    v.addStretch()
    lower = total_row + 1
    grid.addWidget(usage_card, lower, 0, 1, 4 if narrow else 2)

    # Sequência
    streak_card = Card()
    v = QVBoxLayout(streak_card)
    v.setContentsMargins(22, 18, 22, 18)
    head = QHBoxLayout()
    days = s.current_streak
    head.addWidget(text_label(f"{days} {'dia seguido' if days == 1 else 'dias seguidos'}", 30, weight=QFont.Weight.Medium))
    head.addStretch()
    longest = s.longest_streak
    head.addWidget(caps_label(f"Maior sequência | {longest} {'dia' if longest == 1 else 'dias'}", "text", 13))
    v.addLayout(head)
    v.addSpacing(10)
    v.addWidget(Heatmap(s, first_day))
    v.addStretch()
    grid.addWidget(streak_card, lower + 1 if narrow else lower, 0 if narrow else 2, 1, 4 if narrow else 2)

    grid.setRowMinimumHeight(row, 236)
    grid.setRowStretch(grid.rowCount(), 1)
    return page


def build_history_page(entries: list[history.Dictation], on_copy) -> QWidget:
    page = QWidget()
    v = QVBoxLayout(page)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(14)
    if not entries:
        empty = text_label("Nenhum ditado ainda. Aperte Super+D e comece a falar.", 16, "muted")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setMinimumHeight(240)
        v.addWidget(empty)
    for e in entries:
        card = Card()
        cv = QVBoxLayout(card)
        cv.setContentsMargins(20, 14, 14, 16)
        cv.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(10)
        when = datetime.fromtimestamp(e.ts)
        head.addWidget(text_label(f"{when.day} {MONTHS[when.month - 1].lower()}, {when:%H:%M}", 13, "muted"))
        chip = QLabel(CATEGORY_LABELS.get(e.category, "Outro"))
        chip.setFont(make_font(12, QFont.Weight.Medium))
        chip.setStyleSheet(f"color: {T['badge_fg']}; background: {T['badge_bg']}; border-radius: 4px; padding: 2px 8px;")
        chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        head.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch()
        copy = SideButton("edit-copy-symbolic", "Copiar", 32, 18)
        copy.clicked.connect(lambda text=e.text: on_copy(text))
        head.addWidget(copy)
        cv.addLayout(head)
        body = text_label(e.text, 15)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cv.addWidget(body)
        v.addWidget(card)
    v.addStretch()
    return page


# ---------------------------------------------------------------- janela


def _desktop_theme() -> str:
    """Tema inicial igual ao do desktop. Lê o portal Settings direto: o Qt do pip nem sempre
    enxerga a preferência do GNOME."""
    try:
        dark = portal.prefers_dark()
    except Exception:
        dark = None
    if dark is None:
        dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return "dark" if dark else "light"


APP_ICON = Path(__file__).parent / "icons" / "fala.svg"


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fala")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.resize(self.sizeHint())
        self.setMinimumSize(900, 600)
        self._theme = _desktop_theme()
        self._tab = 0
        self._build()

    # --- estrutura

    def _build(self) -> None:
        T.clear()
        T.update(THEMES[self._theme])
        self.setStyleSheet(f"MainWindow {{ background: {T['outer']}; }}")
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(T["outer"]))
        self.setPalette(pal)

        if self.layout() is not None:
            QWidget().setLayout(self.layout())  # descarta o layout antigo e seus widgets

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 14, 14)
        root.setSpacing(10)

        side = QVBoxLayout()
        side.setSpacing(8)
        side.addSpacing(12)
        logo = QLabel()
        logo.setPixmap(QIcon(str(APP_ICON)).pixmap(QSize(34, 34), self.devicePixelRatio()))
        side.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        side.addSpacing(26)
        self._nav = []
        for icon, tip, index in (("chart", "Insights", 0), ("document-open-recent-symbolic", "Histórico", 1)):
            button = SideButton(icon, tip)
            button.clicked.connect(lambda i=index: self.set_tab(i))
            side.addWidget(button)
            self._nav.append(button)
        side.addStretch()
        for icon, tip, slot in (
            ("emblem-system-symbolic", "Configurações", self._open_settings),
            ("question", "Ajuda", lambda: QDesktopServices.openUrl(QUrl(REPO_URL))),
        ):
            button = SideButton(icon, tip)
            button.clicked.connect(slot)
            side.addWidget(button)
        root.addLayout(side)

        right = QVBoxLayout()
        right.setSpacing(6)
        top = QHBoxLayout()
        top.addStretch()
        theme_button = SideButton(
            "weather-clear-night-symbolic" if self._theme == "light" else "weather-clear-symbolic",
            "Tema escuro" if self._theme == "light" else "Tema claro",
        )
        theme_button.setFixedSize(46, 46)
        theme_button.clicked.connect(self.toggle_theme)
        top.addWidget(theme_button)
        right.addLayout(top)

        self._panel = Panel()
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(1, 1, 1, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical { background: transparent; width: 10px; margin: 14px 3px 14px 0; }"
            f"QScrollBar::handle:vertical {{ background: {T['divider']}; border-radius: 3px; min-height: 40px; }}"
            "QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page "
            "{ background: none; height: 0; }"
        )
        panel_layout.addWidget(scroll)

        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(36, 22, 36, 28)
        self._content = QWidget()
        self._content.setMaximumWidth(CONTENT_MAX_WIDTH)
        hl.addWidget(self._content)
        scroll.setWidget(holder)

        cv = QVBoxLayout(self._content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        header = QHBoxLayout()
        title = text_label("Insights", 22, weight=QFont.Weight.Medium)
        header.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch()
        cv.addLayout(header)
        cv.addSpacing(10)
        self._tabs = Tabs(["Seu uso", "Histórico"])
        self._tabs.changed.connect(self.set_tab)
        cv.addWidget(self._tabs)
        cv.addSpacing(20)
        self._stack = QStackedWidget()
        cv.addWidget(self._stack, 1)

        right.addWidget(self._panel, 1)
        root.addLayout(right, 1)

        self._toast = Toast(self)
        self.refresh()

    def refresh(self) -> None:
        entries = history.all_entries()
        s = stats.compute(entries)
        first_day = datetime.fromtimestamp(entries[0].ts).date() if entries else None
        while self._stack.count():
            widget = self._stack.widget(0)
            self._stack.removeWidget(widget)
            widget.deleteLater()
        self._narrow = self.width() < NARROW_WIDTH
        self._usage = build_usage_page(s, first_day, self._narrow)
        self._stack.addWidget(self._usage)
        self._stack.addWidget(build_history_page(list(reversed(entries[-200:])), self._copy))
        self.set_tab(self._tab)

    # --- ações

    def set_tab(self, index: int) -> None:
        self._tab = index
        self._stack.setCurrentIndex(index)
        # A pilha teria a altura da maior página; só a página visível conta.
        for i in range(self._stack.count()):
            policy = QSizePolicy.Policy.Preferred if i == index else QSizePolicy.Policy.Ignored
            self._stack.widget(i).setSizePolicy(QSizePolicy.Policy.Preferred, policy)
        self._stack.adjustSize()
        self._tabs.set_current(index)
        for i, button in enumerate(self._nav):
            button.active = i == index
            button.update()

    def toggle_theme(self) -> None:
        self._theme = "dark" if self._theme == "light" else "light"
        self._build()

    def _copy(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self._toast.show_message("Texto copiado")

    def _open_settings(self) -> None:
        if not CONFIG_PATH.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            example = Path(__file__).resolve().parent / "config.example.toml"
            CONFIG_PATH.write_text(
                example.read_text() if example.exists() else "# Configuração do Fala — veja src/fala/config.example.toml no repositório.\n"
            )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_PATH)))

    def show_and_raise(self) -> None:
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        # Fechar a janela só esconde; o ditado continua funcionando.
        event.ignore()
        self.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if (self.width() < NARROW_WIDTH) != getattr(self, "_narrow", None) and hasattr(self, "_stack"):
            self.refresh()
        if self._toast.isVisible():
            self._toast.move((self.width() - self._toast.width()) // 2, self.height() - self._toast.height() - 28)

    def sizeHint(self) -> QSize:
        screen = QApplication.primaryScreen()
        if screen is None:
            return QSize(1280, 820)
        area = screen.availableGeometry()
        return QSize(min(1280, int(area.width() * 0.85)), min(820, int(area.height() * 0.88)))
