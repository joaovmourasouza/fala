import enum
import os
import signal
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import history, host, inject, portal
from .audio import SAMPLE_RATE, Recorder
from .cleanup import Cleaner, claude_available
from .config import Config
from .ipc import CommandServer
from .overlay import Overlay
from .transcribe import make_transcriber
from .window import MainWindow

MIN_AUDIO_SECONDS = 0.3


class State(enum.Enum):
    IDLE = enum.auto()
    RECORDING = enum.auto()
    PROCESSING = enum.auto()


# Segurar o atalho por mais que isso = modo segurar-para-falar; menos = liga/desliga.
HOLD_SECONDS = 0.4
AUTOSTART_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / f"{portal.APP_ID}.desktop"


def notify(message: str) -> None:
    print(f"fala: {message}", file=sys.stderr)
    try:
        host.notify("Fala", message)
    except Exception as e:
        print(f"fala: notificação falhou: {e}", file=sys.stderr)


def _tray_icon(color: QColor) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(22, 6, 20, 34, 10, 10)
    p.drawRect(30, 44, 4, 10)
    p.drawRoundedRect(18, 52, 28, 5, 2, 2)
    p.end()
    return QIcon(pixmap)


class Fala(QObject):
    # Emitidos de threads de áudio/trabalho; o Qt entrega na thread principal.
    level = pyqtSignal(float)
    status = pyqtSignal(str)
    finished = pyqtSignal(str, str)  # texto final, mensagem de aviso/erro
    recorded = pyqtSignal()  # um ditado novo foi salvo no histórico
    shortcut_pressed = pyqtSignal()
    shortcut_released = pyqtSignal()

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.state = State.IDLE
        self.overlay = Overlay()
        self.recorder = Recorder(config.audio_device, on_level=self.level.emit)
        self.transcriber = make_transcriber(config)
        self.cleaner = Cleaner(config.claude_model, config.claude_effort) if config.cleanup else None

        self.level.connect(self.overlay.push_level)
        self.status.connect(self.overlay.show_status)
        self.finished.connect(self._on_finished)

        self.server = CommandServer(self)
        self.server.command.connect(self.handle_command)

        self.max_timer = QTimer(self, singleShot=True)
        self.max_timer.timeout.connect(self.stop)

        self.window = MainWindow()
        self.recorded.connect(self._on_recorded)

        self._key_down = False
        self._pressed_at = 0.0
        self._started_by_press = False
        self.shortcut_pressed.connect(self._on_shortcut_pressed)
        self.shortcut_released.connect(self._on_shortcut_released)

        self._setup_tray()
        for target in (self._warmup, self._run_shortcut, self._prepare_keyboard, self._setup_background):
            threading.Thread(target=target, daemon=True).start()

    def _setup_tray(self) -> None:
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._idle_icon = _tray_icon(QColor(200, 200, 200))
        self._rec_icon = _tray_icon(QColor(230, 60, 60))
        menu = QMenu()
        menu.addAction(QAction("Abrir Fala", menu, triggered=self.show_window))
        menu.addAction(QAction("Ditar / parar", menu, triggered=self.toggle))
        menu.addAction(QAction("Sair", menu, triggered=QApplication.quit))
        self.tray = QSystemTrayIcon(self._idle_icon, self)
        self.tray.setToolTip("Fala")
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.toggle() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray.show()

    def _warmup(self) -> None:
        if self.cleaner and not claude_available():
            self.cleaner = None
            notify("Comando `claude` não encontrado: ajuste com IA desativado, usando a transcrição bruta.")
        try:
            self.transcriber.load()
        except Exception as e:
            notify(f"Transcrição indisponível: {e}")

    def _run_shortcut(self) -> None:
        shortcut = portal.GlobalShortcut(
            "ditar", "Ditar com o Fala", self.config.shortcut,
            on_press=self.shortcut_pressed.emit, on_release=self.shortcut_released.emit,
        )
        try:
            shortcut.run()
        except Exception as e:
            notify(f"Não foi possível registrar o atalho global: {e}")

    def _prepare_keyboard(self) -> None:
        # Na primeira vez o GNOME pergunta se o Fala pode controlar o teclado (para colar o texto).
        try:
            inject.prepare()
        except Exception as e:
            notify(f"Sem permissão para digitar nas janelas; o texto só será copiado ({e}).")

    def _setup_background(self) -> None:
        try:
            if portal.IN_FLATPAK:
                portal.request_background("Para ditar com o atalho a qualquer momento.", ["fala", "--background"])
            elif self.config.autostart and not AUTOSTART_FILE.exists():
                AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
                AUTOSTART_FILE.write_text(
                    "[Desktop Entry]\nType=Application\nName=Fala\n"
                    f"Exec={Path(sys.argv[0]).resolve()} --background\n"
                    f"Icon={portal.APP_ID}\nX-GNOME-Autostart-enabled=true\n"
                )
            portal.set_background_status("Pronto para ditar")
        except Exception as e:
            print(f"fala: não foi possível configurar o segundo plano: {e}", file=sys.stderr)

    def _on_shortcut_pressed(self) -> None:
        if self._key_down:  # repetição da tecla segurada
            return
        self._key_down = True
        self._pressed_at = time.monotonic()
        if self.state == State.IDLE:
            self.start()
            self._started_by_press = self.state == State.RECORDING
        elif self.state == State.RECORDING:
            self.stop()

    def _on_shortcut_released(self) -> None:
        self._key_down = False
        held = time.monotonic() - self._pressed_at
        if self._started_by_press and held >= HOLD_SECONDS:
            self.stop()
        self._started_by_press = False

    def handle_command(self, cmd: str) -> None:
        actions = {
            "toggle": self.toggle,
            "start": self.start,
            "stop": self.stop,
            "cancel": self.cancel,
            "show": self.show_window,
            "quit": QApplication.quit,
        }
        if cmd in actions:
            actions[cmd]()

    def show_window(self) -> None:
        self.window.show_and_raise()

    def _on_recorded(self) -> None:
        if self.window.isVisible():
            self.window.refresh()

    def toggle(self) -> None:
        if self.state == State.IDLE:
            self.start()
        elif self.state == State.RECORDING:
            self.stop()

    def start(self) -> None:
        if self.state != State.IDLE:
            return
        try:
            self.recorder.start()
        except Exception as e:
            notify(f"Não foi possível abrir o microfone: {e}")
            return
        self._set_state(State.RECORDING)
        self.overlay.show_recording()
        self.max_timer.start(self.config.max_seconds * 1000)

    def stop(self) -> None:
        if self.state != State.RECORDING:
            return
        self.max_timer.stop()
        audio = self.recorder.stop()
        if len(audio) < SAMPLE_RATE * MIN_AUDIO_SECONDS:
            self.overlay.hide()
            self._set_state(State.IDLE)
            return
        self._set_state(State.PROCESSING)
        self.overlay.show_status("Transcrevendo…")
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def cancel(self) -> None:
        if self.state != State.RECORDING:
            return
        self.max_timer.stop()
        self.recorder.stop()
        self.overlay.hide()
        self._set_state(State.IDLE)

    def _process(self, audio: np.ndarray) -> None:
        try:
            raw = self.transcriber.transcribe(audio)
        except Exception as e:
            self.finished.emit("", f"Falha na transcrição: {e}")
            return
        text, category, message = raw, "outro", ""
        if raw and self.cleaner is not None:
            self.status.emit("Ajustando texto…")
            try:
                text, category = self.cleaner.clean(raw)
            except Exception as e:
                message = f"Ajuste com IA falhou, usei o texto bruto: {e}"
        if text:
            try:
                history.add(len(audio) / SAMPLE_RATE, raw, text, category)
                self.recorded.emit()
            except Exception as e:
                print(f"fala: não foi possível salvar no histórico: {e}", file=sys.stderr)
        self.finished.emit(text, message)

    def _on_finished(self, text: str, message: str) -> None:
        self.overlay.hide()
        self._set_state(State.IDLE)
        if message:
            notify(message)
        if text:
            # Dá tempo para o foco voltar ao app de origem depois que o overlay some.
            QTimer.singleShot(150, lambda: self._insert(text))

    def _insert(self, text: str) -> None:
        try:
            pasted = inject.insert(text, self.config.paste_keys)
        except Exception as e:
            notify(f"Não foi possível inserir o texto: {e}")
            return
        if not pasted:
            notify("Texto copiado. Cole com Ctrl+V.")

    def _set_state(self, state: State) -> None:
        self.state = state
        if self.tray:
            self.tray.setIcon(self._rec_icon if state == State.RECORDING else self._idle_icon)


def run(config: Config, background: bool = False) -> int:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    # Precisa vir antes da QApplication: o Qt registra o app ID no portal do desktop ao iniciar.
    QApplication.setApplicationName("Fala")
    QApplication.setDesktopFileName(portal.APP_ID)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    fala = Fala(config)
    if not background:
        fala.show_window()
    print("fala: pronto. Use o atalho (padrão Super+D) para ditar.", file=sys.stderr)
    return app.exec()
