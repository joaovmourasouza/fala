"""Socket local para o comando `fala toggle` (chamado pelo atalho do GNOME) falar com o app."""

import os
import socket
import tempfile

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SOCKET_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()), "fala.sock")


class CommandServer(QObject):
    command = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        QLocalServer.removeServer(SOCKET_PATH)
        if not self._server.listen(SOCKET_PATH):
            raise RuntimeError(f"não foi possível abrir {SOCKET_PATH}: {self._server.errorString()}")
        self._server.newConnection.connect(self._on_connection)

    def _on_connection(self) -> None:
        while (conn := self._server.nextPendingConnection()) is not None:
            conn.readyRead.connect(lambda c=conn: self._read(c))
            conn.disconnected.connect(conn.deleteLater)
            if conn.bytesAvailable():
                self._read(conn)

    def _read(self, conn: QLocalSocket) -> None:
        for cmd in bytes(conn.readAll()).decode(errors="ignore").split():
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
