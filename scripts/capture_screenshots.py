#!/usr/bin/env python3
"""Capture README screenshots using demo assets only."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QRect, Qt
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo" / "assets"
OUTPUT_DIR = ROOT / "docs" / "screenshots"


def _save(widget, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    if pixmap.isNull():
        raise RuntimeError(f"Failed to capture screenshot: {path}")
    if not pixmap.save(str(path)):
        raise RuntimeError(f"Failed to write screenshot: {path}")
    print(f"Saved {path}")


def main() -> int:
    demo_image = DEMO_DIR / "landscape-color-grid.png"
    if not demo_image.is_file():
        raise SystemExit(f"Demo image missing: {demo_image}. Run scripts/generate_demo_assets.py first.")

    from crop_tool.image_dialog import ImagePickerDialog
    from crop_tool.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    window = MainWindow(image_path=str(demo_image))
    window.resize(1120, 780)
    window.show()
    app.processEvents()

    window._ratio_combo.setCurrentIndex(4)  # 16:9
    window._canvas._crop_rect = QRect(180, 90, 520, 292)
    window._canvas.update()
    window._update_status(window._canvas.crop_rect)
    app.processEvents()
    _save(window, OUTPUT_DIR / "main-window.png")

    picker = ImagePickerDialog(directory=str(DEMO_DIR))
    picker.resize(1120, 760)
    picker.show()
    app.processEvents()
    if picker._list.count() > 0:
        picker._list.setCurrentRow(0)
    app.processEvents()
    _save(picker, OUTPUT_DIR / "open-dialog.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())