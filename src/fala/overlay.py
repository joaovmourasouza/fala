from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

BARS = 24


class Overlay(QWidget):
    """Pílula flutuante: medidor de volume enquanto grava, texto de status enquanto processa."""

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(220, 44)
        self._recording = False
        self._text = ""
        self._levels = [0.0] * BARS

    def show_recording(self) -> None:
        self._recording = True
        self._levels = [0.0] * BARS
        self._show()

    def show_status(self, text: str) -> None:
        self._recording = False
        self._text = text
        self._show()

    def push_level(self, rms: float) -> None:
        if self._recording:
            self._levels = self._levels[1:] + [min(1.0, rms * 15)]
            self.update()

    def _show(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.bottom() - self.height() - 48)
        self.show()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 20, 24, 230))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        if not self._recording:
            p.setPen(QColor(235, 235, 235))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._text)
            return

        cy = r.center().y()
        p.setBrush(QColor(230, 60, 60))
        p.drawEllipse(QPointF(24, cy), 6, 6)
        p.setBrush(QColor(235, 235, 235))
        for i, level in enumerate(self._levels):
            h = max(3.0, level * (r.height() - 16))
            p.drawRoundedRect(QRectF(42 + i * 7, cy - h / 2, 4, h), 2, 2)
