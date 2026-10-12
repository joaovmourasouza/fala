#!/usr/bin/env bash
# Cria um atalho de teclado no GNOME que roda `fala toggle`.
# Uso: scripts/setup-gnome-shortcut.sh ['<Super>d']
set -euo pipefail

BINDING="${1:-<Super>d}"
FALA_BIN="$(command -v fala || true)"
if [[ -z "$FALA_BIN" ]]; then
  FALA_BIN="$(cd "$(dirname "$0")/.." && pwd)/.venv/bin/fala"
fi
[[ -x "$FALA_BIN" ]] || { echo "fala não encontrado; instale primeiro (veja o README)." >&2; exit 1; }

SCHEMA=org.gnome.settings-daemon.plugins.media-keys
KEY_PATH=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/fala/

existing="$(gsettings get "$SCHEMA" custom-keybindings)"
if [[ "$existing" != *"$KEY_PATH"* ]]; then
  if [[ "$existing" == "@as []" || "$existing" == "[]" ]]; then
    updated="['$KEY_PATH']"
  else
    updated="${existing%]}, '$KEY_PATH']"
  fi
  gsettings set "$SCHEMA" custom-keybindings "$updated"
fi

gsettings set "$SCHEMA.custom-keybinding:$KEY_PATH" name "Fala: ditar"
gsettings set "$SCHEMA.custom-keybinding:$KEY_PATH" command "$FALA_BIN toggle"
gsettings set "$SCHEMA.custom-keybinding:$KEY_PATH" binding "$BINDING"
echo "Atalho $BINDING → $FALA_BIN toggle"
