#!/usr/bin/env bash
# Para rodar fora do Flatpak (desenvolvimento): instala o .desktop e o ícone com o ID do app,
# para o GNOME reconhecer o Fala (portais de atalho/teclado/segundo plano, lista de apps).
set -euo pipefail

APP_ID=io.github.joaovmourasouza.Fala
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FALA_BIN="$(command -v fala || echo "$ROOT/.venv/bin/fala")"
[[ -x "$FALA_BIN" ]] || { echo "fala não encontrado; instale primeiro (veja o README)." >&2; exit 1; }

DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
install -Dm644 "$ROOT/data/$APP_ID.svg" "$DATA/icons/hicolor/scalable/apps/$APP_ID.svg"
sed "s|^Exec=fala|Exec=$FALA_BIN|" "$ROOT/data/$APP_ID.desktop" | install -Dm644 /dev/stdin "$DATA/applications/$APP_ID.desktop"
rm -f "$DATA/applications/fala.desktop"
update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "Instalado: $DATA/applications/$APP_ID.desktop"
