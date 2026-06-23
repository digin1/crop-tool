from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, QStringListModel, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from crop_tool.image_formats import IMAGE_SUFFIXES
from crop_tool.image_io import load_qimage

THUMB_SIZE = QSize(160, 160)
PREVIEW_MIN_SIZE = QSize(400, 400)


@dataclass
class OpenTarget:
    image: str = ""
    folder: str = ""

    @property
    def is_folder(self) -> bool:
        return bool(self.folder) and not self.image


class ImagePickerDialog(QDialog):
    """Custom image browser with thumbnail grid and large preview."""

    def __init__(self, parent: QWidget | None = None, directory: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Open Image")
        self.resize(1100, 720)

        start = self._resolve_start_dir(directory)
        self._current_dir = start
        self._selected_path: Path | None = None
        self._open_folder_only = False
        self._history: list[Path] = []
        self._history_index = -1

        root = QVBoxLayout(self)

        nav = QHBoxLayout()
        self._back_btn = QToolButton()
        self._back_btn.setText("←")
        self._back_btn.setFixedWidth(34)
        self._back_btn.setToolTip("Back")
        self._back_btn.clicked.connect(self._go_back)
        nav.addWidget(self._back_btn)

        self._forward_btn = QToolButton()
        self._forward_btn.setText("→")
        self._forward_btn.setFixedWidth(34)
        self._forward_btn.setToolTip("Forward")
        self._forward_btn.clicked.connect(self._go_forward)
        nav.addWidget(self._forward_btn)

        self._up_btn = QToolButton()
        self._up_btn.setText("Up")
        self._up_btn.setToolTip("Parent folder")
        self._up_btn.clicked.connect(self._go_up)
        nav.addWidget(self._up_btn)

        self._home_btn = QPushButton("Pictures")
        self._home_btn.clicked.connect(self._go_pictures)
        nav.addWidget(self._home_btn)

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.clicked.connect(self._browse_folder)
        nav.addWidget(self._browse_btn)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(0)

        self._path_edit = QLineEdit(str(start))
        self._path_edit.setPlaceholderText("Folder path")
        self._path_edit.returnPressed.connect(self._go_to_path)
        self._path_edit.textChanged.connect(self._on_path_text_changed)

        self._path_suggestion_model = QStringListModel(self)
        self._path_completer = QCompleter(self._path_suggestion_model, self)
        self._path_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._path_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._path_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._path_completer.setMaxVisibleItems(14)
        self._path_completer.activated.connect(self._on_path_suggestion_picked)
        self._path_edit.setCompleter(self._path_completer)

        self._path_dropdown_btn = QToolButton()
        self._path_dropdown_btn.setText("▼")
        self._path_dropdown_btn.setFixedWidth(30)
        self._path_dropdown_btn.setToolTip("Show folder suggestions")
        self._path_dropdown_btn.clicked.connect(self._show_path_dropdown)
        self._path_dropdown_btn.setStyleSheet(
            "QToolButton::menu-indicator { image: none; width: 0; height: 0; }"
        )

        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(self._path_dropdown_btn)
        nav.addLayout(path_row, stretch=1)
        root.addLayout(nav)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(THUMB_SIZE)
        self._list.setGridSize(QSize(THUMB_SIZE.width() + 24, THUMB_SIZE.height() + 36))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setSpacing(12)
        self._list.setUniformItemSizes(True)
        self._list.currentItemChanged.connect(self._on_item_changed)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        splitter.addWidget(self._list)

        self._preview = QLabel("Select an image")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(PREVIEW_MIN_SIZE)
        self._preview.setStyleSheet(
            "QLabel { background-color: #1e1e1e; color: #aaa; border: 1px solid #444; }"
        )
        splitter.addWidget(self._preview)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        self._info = QLabel()
        root.addWidget(self._info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        self._open_btn = buttons.button(QDialogButtonBox.StandardButton.Open)
        self._open_btn.setEnabled(False)

        self._open_folder_btn = buttons.addButton(
            "Open Folder",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self._open_folder_btn.clicked.connect(self._accept_folder)
        root.addWidget(buttons)

        self._image_count = 0
        self._navigate_to(start)

    @staticmethod
    def _resolve_start_dir(directory: str) -> Path:
        if directory:
            path = Path(directory).expanduser()
            if path.is_dir():
                return path.resolve()
            if path.parent.is_dir():
                return path.parent.resolve()

        pictures = Path.home() / "Pictures"
        if pictures.is_dir():
            return pictures.resolve()

        home = Path.home()
        return home.resolve()

    def selected_path(self) -> str:
        return str(self._selected_path) if self._selected_path else ""

    def selected_folder(self) -> str:
        if self._open_folder_only:
            return str(self._current_dir)
        return ""

    def _accept_folder(self) -> None:
        self._open_folder_only = True
        self._selected_path = None
        self.accept()

    def _navigate_to(self, directory: Path, *, record_history: bool = True) -> None:
        directory = directory.expanduser().resolve()
        if record_history:
            if self._history and self._history_index >= 0:
                if directory != self._history[self._history_index]:
                    self._history = self._history[: self._history_index + 1]
                    self._history.append(directory)
                    self._history_index = len(self._history) - 1
            else:
                self._history = [directory]
                self._history_index = 0

        self._load_directory(directory)
        self._update_nav_buttons()
        self._update_path_completions()

    def _update_nav_buttons(self) -> None:
        self._back_btn.setEnabled(self._history_index > 0)
        self._forward_btn.setEnabled(self._history_index < len(self._history) - 1)
        parent = self._current_dir.parent
        self._up_btn.setEnabled(parent != self._current_dir)

    def _suggestions_for_text(self, typed: str) -> list[str]:
        seen: set[str] = set()
        suggestions: list[str] = []

        def add(path: Path) -> None:
            text = str(path.expanduser().resolve()) if path.exists() else str(path.expanduser())
            key = text.lower()
            if key not in seen:
                seen.add(key)
                suggestions.append(text)

        for entry in self._history:
            add(entry)
        add(self._current_dir)

        folders_to_scan: list[Path] = []
        if self._current_dir.is_dir():
            folders_to_scan.append(self._current_dir)

        typed = typed.strip()
        if typed:
            expanded = Path(typed).expanduser()
            if typed.endswith("/") and expanded.is_dir():
                folders_to_scan.append(expanded.resolve())
            elif expanded.parent.is_dir():
                folders_to_scan.append(expanded.parent.resolve())

        for folder in folders_to_scan:
            try:
                for child in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
                    if child.is_dir():
                        add(child.resolve())
            except OSError:
                continue

        if typed:
            needle = typed.lower()
            name_prefix = Path(typed).name.lower()
            suggestions = [
                item
                for item in suggestions
                if needle in item.lower() or Path(item).name.lower().startswith(name_prefix)
            ]

        return sorted(suggestions, key=lambda value: value.lower())[:50]

    def _set_path_suggestions(self, typed: str) -> None:
        self._path_suggestion_model.setStringList(self._suggestions_for_text(typed))

    def _update_path_completions(self) -> None:
        self._set_path_suggestions(self._path_edit.text())

    def _on_path_text_changed(self, text: str) -> None:
        self._set_path_suggestions(text)
        if self._path_suggestion_model.rowCount():
            self._path_completer.setCompletionPrefix(text)

    def _show_path_dropdown(self) -> None:
        self._set_path_suggestions(self._path_edit.text())
        suggestions = self._path_suggestion_model.stringList()
        if not suggestions:
            return

        menu = QMenu(self)
        for suggestion in suggestions:
            action = menu.addAction(suggestion)
            action.triggered.connect(
                lambda _checked=False, value=suggestion: self._on_path_suggestion_picked(value)
            )
        anchor = self._path_edit.mapToGlobal(self._path_edit.rect().bottomLeft())
        menu.popup(anchor)

    def _on_path_suggestion_picked(self, text: str) -> None:
        self._path_edit.setText(text)

    def _load_directory(self, directory: Path) -> None:
        self._current_dir = directory.resolve()
        self._path_edit.blockSignals(True)
        self._path_edit.setText(str(self._current_dir))
        self._path_edit.blockSignals(False)
        self._update_path_completions()
        self._list.clear()
        self._selected_path = None
        self._open_btn.setEnabled(False)
        self._preview.setPixmap(QPixmap())
        self._preview.setText("Select an image")
        self._info.setText("")

        if not self._current_dir.is_dir():
            self._info.setText(f"Folder not found: {self._current_dir}")
            return

        try:
            entries = list(self._current_dir.iterdir())
        except OSError as exc:
            self._info.setText(f"Cannot read folder: {self._current_dir} ({exc})")
            return

        images = [
            entry
            for entry in entries
            if entry.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES
        ]
        images.sort(key=lambda p: p.name.lower())

        for image_path in images:
            item = QListWidgetItem(image_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(image_path))
            item.setToolTip(str(image_path))

            pixmap = QPixmap.fromImage(load_qimage(image_path))
            if not pixmap.isNull():
                thumb = pixmap.scaled(
                    THUMB_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item.setIcon(QIcon(thumb))
                item.setSizeHint(QSize(THUMB_SIZE.width() + 16, THUMB_SIZE.height() + 28))

            self._list.addItem(item)

        self._image_count = len(images)
        if self._image_count == 0:
            self._info.setText(f"No images found in {self._current_dir}")
        else:
            self._info.setText(f"{self._image_count} image(s) in {self._current_dir}")

    def _on_item_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._selected_path = None
            self._open_btn.setEnabled(False)
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Select an image")
            self._info.setText(f"{self._image_count} image(s) in {self._current_dir}")
            return

        path = Path(current.data(Qt.ItemDataRole.UserRole))
        self._selected_path = path
        self._open_btn.setEnabled(True)

        pixmap = QPixmap.fromImage(load_qimage(path))
        if pixmap.isNull():
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Could not load preview")
            self._info.setText(f"{path.name}  |  preview unavailable")
            return

        self._preview.setText("")
        self._preview.setPixmap(
            pixmap.scaled(
                self._preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._info.setText(f"{path.name}  |  {pixmap.width()} x {pixmap.height()} px")

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        self._selected_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self._open_folder_only = False
        self.accept()

    def _accept_selection(self) -> None:
        if self._selected_path is None:
            QMessageBox.information(self, "Open Image", "Select an image first.")
            return
        self._open_folder_only = False
        self.accept()

    def _go_back(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._load_directory(self._history[self._history_index])
        self._update_nav_buttons()
        self._update_path_completions()

    def _go_forward(self) -> None:
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._load_directory(self._history[self._history_index])
        self._update_nav_buttons()
        self._update_path_completions()

    def _go_up(self) -> None:
        parent = self._current_dir.parent
        if parent != self._current_dir:
            self._navigate_to(parent)

    def _go_pictures(self) -> None:
        pictures = Path.home() / "Pictures"
        if pictures.is_dir():
            self._navigate_to(pictures)
        else:
            self._navigate_to(Path.home())

    def _go_to_path(self) -> None:
        path = Path(self._path_edit.text().strip()).expanduser()
        if path.is_dir():
            self._navigate_to(path.resolve())
        else:
            QMessageBox.warning(self, "Open Image", f"Not a folder:\n{path}")

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Folder",
            str(self._current_dir),
        )
        if folder:
            self._navigate_to(Path(folder))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._selected_path is None:
            return
        pixmap = QPixmap.fromImage(load_qimage(self._selected_path))
        if pixmap.isNull():
            return
        self._preview.setPixmap(
            pixmap.scaled(
                self._preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


def pick_open_target(parent: QWidget | None = None, directory: str = "") -> OpenTarget:
    dialog = ImagePickerDialog(parent=parent, directory=directory)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return OpenTarget()
    if dialog.selected_folder():
        return OpenTarget(folder=dialog.selected_folder())
    return OpenTarget(image=dialog.selected_path())


def pick_image(parent: QWidget | None = None, directory: str = "") -> str:
    return pick_open_target(parent=parent, directory=directory).image