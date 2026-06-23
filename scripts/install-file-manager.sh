#!/usr/bin/env bash
# Register Crop Tool with the desktop "Open With" menu and Nautilus right-click.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
NAUTILUS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nautilus-python/extensions"

CROP_TOOL=""
for candidate in "$(command -v crop-tool 2>/dev/null || true)" "$HOME/.local/bin/crop-tool"; do
  if [[ -n "$candidate" && -x "$candidate" ]]; then
    CROP_TOOL="$candidate"
    break
  fi
done

if [[ -z "$CROP_TOOL" ]]; then
  echo "error: crop-tool is not installed or not on PATH" >&2
  echo "Run ./scripts/install.sh first." >&2
  exit 1
fi

mkdir -p "$APPS_DIR" "$NAUTILUS_DIR"

sed "s|@EXEC@|$CROP_TOOL|g" "$ROOT/share/applications/crop-tool.desktop.in" \
  >"$APPS_DIR/crop-tool.desktop"
chmod 644 "$APPS_DIR/crop-tool.desktop"

cp "$ROOT/share/nautilus-python/extensions/crop-tool-nautilus.py" \
  "$NAUTILUS_DIR/crop-tool-nautilus.py"
chmod 644 "$NAUTILUS_DIR/crop-tool-nautilus.py"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi

echo "File manager integration installed."
echo "  Desktop entry: $APPS_DIR/crop-tool.desktop"
echo "  Nautilus menu: $NAUTILUS_DIR/crop-tool-nautilus.py"
echo
echo "Restart Nautilus if it is already open:"
echo "  nautilus -q"