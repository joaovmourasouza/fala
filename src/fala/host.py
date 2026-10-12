"""Diferenças entre rodar direto no sistema e dentro do Flatpak."""

import os
import shutil
import subprocess

from jeepney import DBusAddress, new_method_call
from jeepney.io.blocking import open_dbus_connection

IN_FLATPAK = os.path.exists("/.flatpak-info")

NOTIFICATIONS = DBusAddress(
    "/org/freedesktop/Notifications",
    bus_name="org.freedesktop.Notifications",
    interface="org.freedesktop.Notifications",
)


def host_command(args: list[str]) -> list[str]:
    """Comando que precisa rodar no sistema (fora do sandbox), como o `claude` do usuário."""
    if not IN_FLATPAK:
        return args
    # Shell de login para pegar o PATH do usuário (ex.: ~/.local/bin, onde o claude costuma ficar).
    # Roda em /tmp do sistema: as pastas do sandbox não existem lá, e /tmp não tem CLAUDE.md.
    return ["flatpak-spawn", "--host", "--directory=/tmp", "bash", "-lc", 'exec "$@"', "fala", *args]


def host_has(program: str) -> bool:
    if not IN_FLATPAK:
        return shutil.which(program) is not None
    result = subprocess.run(host_command(["sh", "-c", f"command -v {program}"]), capture_output=True, timeout=10)
    return result.returncode == 0


def notify(summary: str, body: str = "") -> None:
    with open_dbus_connection(bus="SESSION") as conn:
        msg = new_method_call(
            NOTIFICATIONS, "Notify", "susssasa{sv}i",
            ("Fala", 0, "audio-input-microphone", summary, body, [], {}, 5000),
        )
        conn.send_and_get_reply(msg, timeout=5)
