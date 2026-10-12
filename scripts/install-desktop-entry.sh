#!/usr/bin/env bash
# Instala ~/.local/share/applications/fala.desktop: o GNOME passa a reconhecer o app
# (portal, notificações) e o Fala aparece na lista de aplicativos.
set -euo pipefail

FALA_BIN="$(command -v fala || true)"
if [[ -z "$FALA_BIN" ]]; then
  FALA_BIN="$(cd "$(dirname "$0")/.." && pwd)/.venv/bin/fala"
fi
[[ -x "$FALA_BIN" ]] || { echo "fala não encontrado; instale primeiro (veja o README)." >&2; exit 1; }

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/fala.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Fala
Comment=Ditado por voz em qualquer app
Exec=$FALA_BIN
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
DESKTOP
update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "Instalado: $APPS_DIR/fala.desktop"
