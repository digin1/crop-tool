import os
import stat
import sys
import tempfile
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from crop_tool.folder_strip import FolderStrip, scan_folder_images

app = QApplication(sys.argv)


def _make_image(path: Path) -> None:
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(0xFF00FF)
    image.save(str(path))


def test_scan_sorts_and_filters() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "notes.txt").write_text("x")
        _make_image(folder / "b.jpg")
        _make_image(folder / "a.png")

        result = scan_folder_images(folder)
        assert result.error is None
        assert [p.name for p in result.images] == ["a.png", "b.jpg"]


def test_scan_includes_missing_current_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        _make_image(folder / "keep.png")
        missing = folder / "gone.jpg"

        result = scan_folder_images(folder, include=missing)
        assert [p.name for p in result.images] == ["gone.jpg", "keep.png"]


def test_scan_skips_unreadable_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        locked = folder / "locked.png"
        _make_image(locked)
        _make_image(folder / "open.png")
        os.chmod(locked, stat.S_IWUSR)

        result = scan_folder_images(folder)
        assert result.skipped_unreadable == 1
        assert [p.name for p in result.images] == ["open.png"]

        os.chmod(locked, stat.S_IWUSR | stat.S_IRUSR)


def test_strip_keeps_selection_on_missing_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        first = folder / "first.png"
        second = folder / "second.png"
        _make_image(first)
        _make_image(second)

        strip = FolderStrip()
        strip.load_folder(folder, first)
        assert strip._list.currentRow() == 0

        second.unlink()
        strip.load_folder(folder, first)
        assert strip._list.currentRow() == 0


if __name__ == "__main__":
    test_scan_sorts_and_filters()
    test_scan_includes_missing_current_file()
    test_scan_skips_unreadable_files()
    test_strip_keeps_selection_on_missing_target()
    print("all folder_strip edge-case tests passed")