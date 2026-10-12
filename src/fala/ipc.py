"""Socket local para comandos como `fala show` e `fala quit` falarem com o app em execução."""

import os
import socket
import tempfile

from PyQt6.QtCore import QObject, QSocketNotifier, pyqtSignal

_RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())
if "FLATPAK_ID" in os.environ:
    # Pasta compartilhada entre todas as instâncias do mesmo Flatpak.
    _RUNTIME_DIR = os.path.join(_RUNTIME_DIR, "app", os.environ["FLATPAK_ID"])
SOCKET_PATH = os.path.join(_RUNTIME_DIR, "fala.sock")


class CommandServer(QObject):
    """Servidor no socket Unix, integrado ao loop do Qt (sem QtNetwork, que puxa libs a mais)."""

    command = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(SOCKET_PATH)
        self._sock.listen()
        self._sock.setblocking(False)
        self._notifier = QSocketNotifier(self._sock.fileno(), QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._accept)

    def _accept(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except BlockingIOError:
                return
            with conn:
                # Os clientes mandam um comando curto e fecham a conexão.
                conn.settimeout(1)
                try:
                    data = conn.recv(1024)
                except OSError:
                    continue
            for cmd in data.decode(errors="ignore").split():
                self.command.emit(cmd)


def send(cmd: str) -> bool:
    """Envia um comando para a instância em execução. Retorna False se ela não estiver rodando."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(SOCKET_PATH)
            s.sendall(cmd.encode() + b"\n")
        return True
    except (FileNotFoundError, ConnectionRefusedError):
        return False
