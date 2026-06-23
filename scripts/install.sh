#!/usr/bin/env bash
# Install crop-tool with all Python dependencies.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required (3.10+)" >&2
  exit 1
fi

if command -v pipx >/dev/null 2>&1; then
  echo "Installing with pipx..."
  pipx install --force "$ROOT"
  echo
  echo "Registering Nautilus / Open With integration..."
  "$ROOT/scripts/install-file-manager.sh"
  echo
  echo "Done. Run: crop-tool"
  exit 0
fi

INSTALL_DIR="${CROP_TOOL_HOME:-$HOME/.local/share/crop-tool}"
VENV="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"

echo "pipx not found; installing into $VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install "$ROOT"

mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/crop-tool" "$BIN_DIR/crop-tool"

echo
echo "Registering Nautilus / Open With integration..."
"$ROOT/scripts/install-file-manager.sh"

echo
echo "Done. Ensure this is on your PATH:"
echo "  $BIN_DIR"
echo "Then run: crop-tool"