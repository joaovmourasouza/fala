"""Coloca o texto no app em foco: copia para a área de transferência e simula o atalho de colar."""

import os
import shutil
import subprocess

# Códigos de tecla do Linux (linux/input-event-codes.h), usados pelo ydotool.
KEYCODES = {"ctrl": 29, "shift": 42, "alt": 56, "super": 125, "v": 47, "insert": 110}


def _wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or "WAYLAND_DISPLAY" in os.environ


def copy_to_clipboard(text: str) -> None:
    if _wayland():
        cmd = ["wl-copy"]
    else:
        cmd = ["xclip", "-selection", "clipboard"]
    subprocess.run(cmd, input=text.encode(), check=True, timeout=5)


def paste(keys: str) -> bool:
    """Simula o atalho de colar. Retorna False se não houver ferramenta disponível."""
    combo = keys.lower().split("+")
    if _wayland():
        if not shutil.which("ydotool"):
            return False
        codes = [KEYCODES[k] for k in combo]
        events = [f"{c}:1" for c in codes] + [f"{c}:0" for c in reversed(codes)]
        cmd = ["ydotool", "key", *events]
    else:
        if not shutil.which("xdotool"):
            return False
        cmd = ["xdotool", "key", "--clearmodifiers", keys]
    return subprocess.run(cmd, timeout=5).returncode == 0


def insert(text: str, paste_keys: str) -> bool:
    """Retorna True se colou; False se apenas copiou."""
    copy_to_clipboard(text)
    return paste(paste_keys)
