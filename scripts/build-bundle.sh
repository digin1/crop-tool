#!/usr/bin/env bash
# Build a standalone crop-tool bundle (no separate pip install needed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUILD_VENV="$ROOT/.build-venv"
if [[ ! -d "$BUILD_VENV" ]]; then
  python3 -m venv "$BUILD_VENV"
fi

"$BUILD_VENV/bin/pip" install --upgrade pip
"$BUILD_VENV/bin/pip" install ".[bundle]"
"$BUILD_VENV/bin/pyinstaller" --noconfirm --clean crop-tool.spec

echo
echo "Bundle created at: $ROOT/dist/crop-tool/"
echo "Run: $ROOT/dist/crop-tool/crop-tool"
echo
echo "Optional: add to PATH"
echo "  ln -sf \"$ROOT/dist/crop-tool/crop-tool\" \"\$HOME/.local/bin/crop-tool\""