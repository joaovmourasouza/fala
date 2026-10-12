"""Coloca o texto no app em foco: copia para a área de transferência e simula o atalho de colar."""

import os
import shutil
import subprocess

from .portal import RemoteKeyboard

# Códigos de tecla do Linux (linux/input-event-codes.h), usados pelo portal.
KEYCODES = {"ctrl": 29, "shift": 42, "alt": 56, "super": 125, "v": 47, "insert": 110}

_keyboard = RemoteKeyboard()


def _wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or "WAYLAND_DISPLAY" in os.environ


def prepare() -> None:
    """Abre a sessão do teclado virtual com antecedência (o primeiro uso mostra o diálogo de permissão)."""
    if _wayland():
        _keyboard.ensure_session()


def copy_to_clipboard(text: str) -> None:
    cmd = ["wl-copy"] if _wayland() else ["xclip", "-selection", "clipboard"]
    subprocess.run(cmd, input=text.encode(), check=True, timeout=5)


def paste(keys: str) -> bool:
    """Simula o atalho de colar. Retorna False se não for possível."""
    combo = keys.lower().split("+")
    if _wayland():
        _keyboard.press([KEYCODES[k] for k in combo])
        return True
    if not shutil.which("xdotool"):
        return False
    return subprocess.run(["xdotool", "key", "--clearmodifiers", keys], timeout=5).returncode == 0


def insert(text: str, paste_keys: str) -> bool:
    """Retorna True se colou; False se apenas copiou."""
    copy_to_clipboard(text)
    return paste(paste_keys)
