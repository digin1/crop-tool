from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crop_tool.image_formats import IMAGE_SUFFIXES
from crop_tool.image_io import load_qimage

THUMB_SIZE = QSize(96, 96)
STRIP_HEIGHT = 132


@dataclass
class FolderScanResult:
    images: list[Path]
    skipped_unreadable: int = 0
    error: str | None = None


def scan_folder_images(folder: Path, *, include: Path | None = None) -> FolderScanResult:
    if not folder.is_dir():
        return FolderScanResult(images=[], error="Folder not found")

    try:
        entries = list(folder.iterdir())
    except OSError as exc:
        return FolderScanResult(images=[], error=f"Cannot read folder ({exc})")

    images: list[Path] = []
    skipped = 0
    for entry in entries:
        if not entry.is_file() or entry.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        resolved = entry.resolve()
        if not os.access(resolved, os.R_OK):
            skipped += 1
            continue
        images.append(resolved)

    images.sort(key=lambda p: p.name.lower())

    if include is not None:
        include = include.resolve()
        if include.parent.resolve() == folder.resolve() and include not in images:
            images.append(include)
            images.sort(key=lambda p: p.name.lower())

    return FolderScanResult(images=images, skipped_unreadable=skipped)


def list_folder_images(folder: Path) -> list[Path]:
    return scan_folder_images(folder).images


class FolderStrip(QWidget):
    """Horizontal thumbnail strip for images in the current folder."""

    image_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None
        self._current: Path | None = None
        self._loading_selection = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(4)

        self._title = QLabel("Folder images")
        self._title.setStyleSheet("color: #bbb; font-size: 11px;")
        root.addWidget(self._title)

        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setFlow(QListWidget.Flow.LeftToRight)
        self._list.setWrapping(False)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setIconSize(THUMB_SIZE)
        self._list.setGridSize(QSize(THUMB_SIZE.width() + 16, THUMB_SIZE.height() + 28))
        self._list.setSpacing(8)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setFixedHeight(STRIP_HEIGHT)
        self._list.setStyleSheet(
            "QListWidget { background: #242424; border: 1px solid #3a3a3a; border-radius: 4px; }"
            "QListWidget::item:selected { background: #3d5a80; border-radius: 4px; }"
        )
        self._list.currentItemChanged.connect(self._on_item_changed)
        root.addWidget(self._list)

        self.hide()

    def load_folder(self, folder: Path | None, current: Path | None = None) -> None:
        self._loading_selection = True
        self._list.clear()
        self._folder = folder.resolve() if folder else None
        self._current = current.resolve() if current else None

        if self._folder is None or not self._folder.is_dir():
            self._title.setText("Folder images")
            self.hide()
            self._loading_selection = False
            return

        scan = scan_folder_images(self._folder, include=self._current)
        if scan.error:
            self._title.setText(f"{scan.error}: {self._folder.name}")
            self.show()
            self._loading_selection = False
            return

        if not scan.images:
            note = f"No images in {self._folder.name}"
            if scan.skipped_unreadable:
                note += f" ({scan.skipped_unreadable} unreadable skipped)"
            self._title.setText(note)
            self.hide()
            self._loading_selection = False
            return

        title = f"{len(scan.images)} image(s) in {self._folder.name}"
        if scan.skipped_unreadable:
            title += f"  |  {scan.skipped_unreadable} unreadable skipped"
        self._title.setText(title)

        current_row = -1
        for index, image_path in enumerate(scan.images):
            missing = not image_path.is_file()
            label = image_path.name
            if missing:
                label = f"{image_path.name} (missing)"

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(image_path))
            item.setToolTip(str(image_path))
            if missing:
                item.setForeground(Qt.GlobalColor.gray)

            if not missing:
                pixmap = QPixmap.fromImage(load_qimage(image_path))
                if not pixmap.isNull():
                    thumb = pixmap.scaled(
                        THUMB_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    item.setIcon(QIcon(thumb))

            self._list.addItem(item)
            if self._current and image_path == self._current:
                current_row = index

        if current_row >= 0:
            self._list.setCurrentRow(current_row)
            item = self._list.item(current_row)
            if item is not None:
                self._list.scrollToItem(item)
        else:
            self._list.clearSelection()

        self.show()
        self._loading_selection = False

    def _on_item_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if self._loading_selection or current is None:
            return

        path = Path(current.data(Qt.ItemDataRole.UserRole))
        if self._current and path.resolve() == self._current.resolve():
            return

        self.image_selected.emit(str(path))