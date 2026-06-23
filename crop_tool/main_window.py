from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QAction, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from crop_tool.crop_canvas import CropCanvas
from crop_tool.file_utils import FileSnapshot, describe_os_error, has_changed, is_readable_file, snapshot
from crop_tool.folder_strip import FolderStrip, scan_folder_images
from crop_tool.image_dialog import pick_open_target
from crop_tool.image_formats import (
    EXPORT_JPEG,
    EXPORT_PNG,
    IMAGE_FILTER,
    export_path_for_format,
    is_heic_path,
)
from crop_tool.image_io import heic_load_error_message, load_qimage, save_qimage


class MainWindow(QMainWindow):
    def __init__(self, image_path: str | None = None) -> None:
        super().__init__()
        self._current_path: Path | None = None
        self._saved_crop_rect = QRect()
        self._source_snapshot: FileSnapshot | None = None

        self.setWindowTitle("Crop Tool")
        self.resize(960, 720)

        self._canvas = CropCanvas()
        self._canvas.crop_changed.connect(self._update_status)

        self._folder_strip = FolderStrip()
        self._folder_strip.image_selected.connect(self._switch_to_image)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._canvas, stretch=1)
        layout.addWidget(self._folder_strip)
        self.setCentralWidget(container)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Open an image to start")

        self._build_menu()
        self._build_toolbar()

        if image_path:
            self._open_path(Path(image_path))

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_image_action = QAction("Open &Image...", self)
        open_image_action.setShortcut(QKeySequence.StandardKey.Open)
        open_image_action.triggered.connect(self.open_image)
        file_menu.addAction(open_image_action)

        open_folder_action = QAction("Open Fo&lder...", self)
        open_folder_action.setShortcut("Ctrl+Shift+O")
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        self._save_action = QAction("&Save", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self.save)
        self._save_action.setEnabled(False)
        file_menu.addAction(self._save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        reset_action = QAction("&Reset Crop", self)
        reset_action.setShortcut("Ctrl+R")
        reset_action.triggered.connect(self._canvas.reset_crop)
        edit_menu.addAction(reset_action)

    def _make_open_button(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        main_btn = QToolButton()
        main_btn.setText("Open")
        main_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        main_btn.clicked.connect(self.open_image)

        menu_btn = QToolButton()
        menu_btn.setText("▼")
        menu_btn.setFixedWidth(34)
        menu_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        open_menu = QMenu(self)
        open_menu.addAction("Open Image...", self.open_image)
        open_menu.addAction("Open Folder...", self.open_folder)
        menu_btn.setMenu(open_menu)

        main_btn.setObjectName("openMainBtn")
        menu_btn.setObjectName("openMenuBtn")
        container.setStyleSheet(
            """
            QToolButton#openMainBtn {
                padding: 6px 14px;
                border: 1px solid palette(mid);
                border-right: none;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
            }
            QToolButton#openMenuBtn {
                padding: 6px 0;
                font-size: 13px;
                border: 1px solid palette(mid);
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QToolButton#openMenuBtn::menu-indicator {
                image: none;
                width: 0;
                height: 0;
            }
            QToolButton#openMainBtn:hover,
            QToolButton#openMenuBtn:hover {
                background: palette(button);
            }
            QToolButton#openMainBtn:pressed,
            QToolButton#openMenuBtn:pressed {
                background: palette(mid);
            }
            """
        )

        layout.addWidget(main_btn)
        layout.addWidget(menu_btn)
        return container

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Tools")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(self._make_open_button())

        self._save_btn = QAction("Save", self)
        self._save_btn.triggered.connect(self.save)
        self._save_btn.setEnabled(False)
        toolbar.addAction(self._save_btn)

        save_as_btn = QAction("Save As", self)
        save_as_btn.triggered.connect(self.save_as)
        toolbar.addAction(save_as_btn)

        reset_btn = QAction("Reset", self)
        reset_btn.triggered.connect(self._canvas.reset_crop)
        toolbar.addAction(reset_btn)

        toolbar.addSeparator()

        ratio_label = QLabel(" Aspect ratio: ")
        toolbar.addWidget(ratio_label)

        self._ratio_combo = QComboBox()
        self._ratio_combo.addItem("Free", None)
        self._ratio_combo.addItem("1:1", 1.0)
        self._ratio_combo.addItem("4:3", 4 / 3)
        self._ratio_combo.addItem("3:2", 3 / 2)
        self._ratio_combo.addItem("16:9", 16 / 9)
        self._ratio_combo.addItem("9:16", 9 / 16)
        self._ratio_combo.currentIndexChanged.connect(self._on_ratio_changed)
        toolbar.addWidget(self._ratio_combo)

        toolbar.addSeparator()

        self._export_label = QLabel(" Export: ")
        toolbar.addWidget(self._export_label)

        self._export_combo = QComboBox()
        self._export_combo.addItem("PNG", EXPORT_PNG)
        self._export_combo.addItem("JPEG", EXPORT_JPEG)
        toolbar.addWidget(self._export_combo)
        self._export_label.hide()
        self._export_combo.hide()

    def _on_ratio_changed(self, _index: int) -> None:
        ratio = self._ratio_combo.currentData()
        self._canvas.set_aspect_ratio(ratio)

    def _export_format(self) -> str:
        return self._export_combo.currentData() or EXPORT_PNG

    def _update_export_controls(self) -> None:
        show = self._current_path is not None and is_heic_path(self._current_path)
        self._export_label.setVisible(show)
        self._export_combo.setVisible(show)

    def _update_status(self, crop_rect) -> None:
        if not self._canvas.has_image:
            self._status.showMessage("Open an image to start")
            return
        source_note = ""
        if self._current_path:
            source_note = f"  |  Source: {self._current_path.name}"
            if not self._current_path.is_file():
                source_note += " (file missing on disk)"
            elif has_changed(self._current_path, self._source_snapshot):
                source_note += " (modified externally)"

        self._status.showMessage(
            f"Crop: {crop_rect.width()} x {crop_rect.height()} px{source_note}"
        )

    def _start_directory(self) -> str:
        return str(self._current_path.parent) if self._current_path else ""

    def open_image(self) -> None:
        target = pick_open_target(self, directory=self._start_directory())
        if target.image:
            self._switch_to_image(target.image)
        elif target.folder:
            self._open_folder(Path(target.folder))

    def open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
            self._start_directory(),
        )
        if folder:
            self._open_folder(Path(folder))

    def _open_folder(self, folder: Path) -> None:
        folder = folder.expanduser().resolve()
        if not folder.is_dir():
            QMessageBox.warning(self, "Open Folder", f"Not a folder:\n{folder}")
            return
        if not self._confirm_discard_changes("Open folder"):
            return

        scan = scan_folder_images(folder)
        if scan.error:
            QMessageBox.warning(self, "Open Folder", f"{scan.error}\n\n{folder}")
            return
        if not scan.images:
            note = f"No supported images found in:\n{folder}"
            if scan.skipped_unreadable:
                note += f"\n\n({scan.skipped_unreadable} unreadable file(s) skipped)"
            QMessageBox.information(self, "Open Folder", note)
            return

        if not self._open_path(scan.images[0]):
            return

        skipped = (
            f"  |  {scan.skipped_unreadable} unreadable skipped"
            if scan.skipped_unreadable
            else ""
        )
        self._status.showMessage(
            f"Opened folder: {folder.name}  |  {len(scan.images)} image(s){skipped}"
        )

    def _confirm_discard_changes(self, action: str) -> bool:
        if not self._has_unsaved_changes():
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"You have an unsaved crop.\n{action} without saving?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _switch_to_image(self, path: str | Path) -> None:
        target = Path(path).expanduser().resolve()
        if self._current_path and target == self._current_path.resolve():
            return
        if not self._confirm_discard_changes("Switch images"):
            self._refresh_folder_strip()
            return
        if not target.is_file():
            QMessageBox.warning(
                self,
                "Open Image",
                f"File not found:\n{target}",
            )
            self._refresh_folder_strip()
            return
        if not self._open_path(target):
            self._refresh_folder_strip()

    def _refresh_folder_strip(self) -> None:
        folder = self._current_path.parent if self._current_path else None
        self._folder_strip.load_folder(folder, self._current_path)

    def _open_path(self, path: Path) -> bool:
        path = path.expanduser().resolve()
        if not path.is_file():
            QMessageBox.warning(
                self,
                "Open Image",
                f"File not found:\n{path}",
            )
            return False
        if not is_readable_file(path):
            QMessageBox.warning(
                self,
                "Open Image",
                f"No permission to read:\n{path}",
            )
            return False

        try:
            image = load_qimage(path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Open Image", str(exc))
            return False

        if image.isNull():
            message = heic_load_error_message() if is_heic_path(path) else (
                f"Could not open image (file may be corrupt or unsupported):\n{path}"
            )
            QMessageBox.warning(self, "Open Image", message)
            return False

        self._current_path = path
        self._source_snapshot = snapshot(path) if path.is_file() else None
        self._canvas.load_image(image)
        self._mark_clean()
        self.setWindowTitle(f"Crop Tool — {path.name}")
        self._update_status(self._canvas.crop_rect)
        self._update_save_state()
        self._update_export_controls()
        self._refresh_folder_strip()
        return True

    def _update_save_state(self) -> None:
        can_save = self._canvas.has_image and self._current_path is not None
        self._save_action.setEnabled(can_save)
        self._save_btn.setEnabled(can_save)

    def _mark_clean(self) -> None:
        self._saved_crop_rect = self._canvas.crop_rect

    def _has_unsaved_changes(self) -> bool:
        return self._canvas.has_image and self._canvas.crop_rect != self._saved_crop_rect

    def _confirm_overwrite(self, path: Path, title: str) -> bool:
        reply = QMessageBox.question(
            self,
            title,
            f"Replace the existing file with the cropped image?\n\n{path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _confirm_uncropped_save(self) -> bool:
        if not self._canvas.is_full_crop():
            return True
        reply = QMessageBox.question(
            self,
            "Save Image",
            "The image has not been cropped.\nSave anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _normalize_save_path(self, path: Path) -> Path:
        if path.suffix:
            return path
        if self._current_path and is_heic_path(self._current_path):
            return export_path_for_format(path, self._export_format())
        return path.with_suffix(".png")

    def _save_target_path(self) -> Path | None:
        if self._current_path is None:
            return None
        if is_heic_path(self._current_path):
            return export_path_for_format(self._current_path, self._export_format())
        return self._current_path

    def _export_format_for_path(self, path: Path) -> str | None:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return EXPORT_JPEG
        if suffix == ".png":
            return EXPORT_PNG
        if self._current_path and is_heic_path(self._current_path):
            return self._export_format()
        return None

    def _write_cropped_to(self, path: Path) -> bool:
        cropped = self._canvas.crop_image()
        if cropped.isNull():
            QMessageBox.warning(self, "Save Image", "Nothing to save.")
            return False

        path = self._normalize_save_path(path.resolve())
        parent = path.parent
        if not parent.is_dir():
            QMessageBox.warning(self, "Save Image", f"Folder does not exist:\n{parent}")
            return False
        if not os.access(parent, os.W_OK):
            QMessageBox.warning(self, "Save Image", f"No permission to write to:\n{parent}")
            return False
        if path.exists() and not os.access(path, os.W_OK):
            QMessageBox.warning(self, "Save Image", f"No permission to overwrite:\n{path}")
            return False

        suffix = path.suffix or ".png"
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(suffix=suffix, dir=parent)
            os.close(fd)
            tmp_path = Path(tmp_name)
            export_format = self._export_format_for_path(path)
            if not save_qimage(cropped, tmp_path, export_format):
                QMessageBox.warning(
                    self,
                    "Save Image",
                    f"Could not write image. The original file was not changed.\n\n{path}",
                )
                return False
            tmp_path.replace(path)
            return True
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Save Image",
                "Could not save image. The original file was not changed.\n\n"
                f"{path}\n\n{describe_os_error(exc)}",
            )
            return False
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _offer_delete_heic(self, heic_path: Path) -> None:
        reply = QMessageBox.question(
            self,
            "Remove HEIC Original",
            f"Exported successfully.\n\nDelete the original HEIC file?\n{heic_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            heic_path.unlink()
            self._status.showMessage(f"Deleted original HEIC: {heic_path.name}")
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Remove HEIC Original",
                f"Could not delete:\n{heic_path}\n\n{describe_os_error(exc)}",
            )

    def _finalize_save(self, path: Path, *, heic_source: Path | None = None) -> None:
        path = self._normalize_save_path(path.resolve())
        self._current_path = path
        image = load_qimage(path)
        if image.isNull():
            QMessageBox.warning(
                self,
                "Save Image",
                f"File was saved, but it could not be reloaded:\n{path}",
            )
            self._status.showMessage(f"Saved {path} (reload failed)")
            self._update_save_state()
            self._refresh_folder_strip()
            return

        self._canvas.load_image(image)
        self._source_snapshot = snapshot(path)
        self._mark_clean()
        self.setWindowTitle(f"Crop Tool — {path.name}")
        self._status.showMessage(f"Saved {path}")
        self._update_status(self._canvas.crop_rect)
        self._update_save_state()
        self._update_export_controls()
        self._refresh_folder_strip()

        if heic_source and is_heic_path(heic_source) and heic_source.resolve() != path.resolve():
            self._offer_delete_heic(heic_source)

    def _confirm_recreate_missing(self, path: Path) -> bool:
        reply = QMessageBox.question(
            self,
            "File Missing",
            f"The original file no longer exists:\n\n{path}\n\nSave and recreate it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _confirm_external_changes(self, path: Path) -> bool:
        reply = QMessageBox.question(
            self,
            "File Modified",
            f"This file was changed outside Crop Tool:\n\n{path}\n\nOverwrite it anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _prepare_save_to(self, path: Path, *, recreate_missing: bool = False) -> Path | None:
        path = self._normalize_save_path(path.resolve())

        if not path.parent.is_dir():
            QMessageBox.warning(self, "Save Image", f"Folder does not exist:\n{path.parent}")
            return None

        if not path.is_file():
            if recreate_missing:
                if not self._confirm_recreate_missing(path):
                    return None
            return path

        if has_changed(path, self._source_snapshot) and not self._confirm_external_changes(path):
            return None
        if not self._confirm_overwrite(path, "Overwrite Image"):
            return None
        return path

    def save(self) -> None:
        if not self._canvas.has_image or self._current_path is None:
            QMessageBox.information(self, "Save Image", "Open an image before saving.")
            return
        if not self._confirm_uncropped_save():
            return

        heic_source = self._current_path if is_heic_path(self._current_path) else None
        target = self._save_target_path()
        if target is None:
            return

        if is_heic_path(self._current_path):
            if target.is_file() and not self._confirm_overwrite(target, "Overwrite File"):
                return
        else:
            target = self._prepare_save_to(target, recreate_missing=True)
            if target is None:
                return

        if self._write_cropped_to(target):
            self._finalize_save(target, heic_source=heic_source)

    def save_as(self) -> None:
        if not self._canvas.has_image:
            QMessageBox.information(self, "Save Image", "Open an image before saving.")
            return
        if not self._confirm_uncropped_save():
            return

        default_name = "cropped.png"
        if self._current_path:
            if is_heic_path(self._current_path):
                default_name = export_path_for_format(
                    self._current_path.with_name(f"{self._current_path.stem}_cropped"),
                    self._export_format(),
                ).name
            else:
                default_name = f"{self._current_path.stem}_cropped{self._current_path.suffix}"

        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Cropped Image",
            default_name,
            IMAGE_FILTER,
        )
        if not path:
            return

        target = self._normalize_save_path(Path(path))
        if target.is_file():
            same_source = (
                self._current_path is not None
                and target.resolve() == self._current_path.resolve()
            )
            if same_source and has_changed(target, self._source_snapshot):
                if not self._confirm_external_changes(target):
                    return
            if not self._confirm_overwrite(target, "Overwrite File"):
                return

        heic_source = self._current_path if is_heic_path(self._current_path) else None
        if self._write_cropped_to(target):
            self._finalize_save(target, heic_source=heic_source)

    def closeEvent(self, event) -> None:
        if not self._confirm_discard_changes("Quit"):
            event.ignore()
            return
        event.accept()


def run_app(image_path: str | None = None) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Crop Tool")
    app.setOrganizationName("crop-tool")
    app.setStyle("Fusion")

    window = MainWindow(image_path=image_path)
    window.show()
    return app.exec()