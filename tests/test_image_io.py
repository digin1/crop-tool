import sys
import tempfile
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from crop_tool.image_formats import EXPORT_JPEG, EXPORT_PNG, export_path_for_format, is_heic_path
from crop_tool.image_io import save_qimage

app = QApplication(sys.argv)


def test_heic_path_detection() -> None:
    assert is_heic_path(Path("photo.HEIC"))
    assert not is_heic_path(Path("photo.png"))


def test_export_path_for_format() -> None:
    source = Path("/tmp/photo.heic")
    assert export_path_for_format(source, EXPORT_PNG) == Path("/tmp/photo.png")
    assert export_path_for_format(source, EXPORT_JPEG) == Path("/tmp/photo.jpg")


def test_save_png_and_jpeg() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        image = QImage(32, 32, QImage.Format.Format_RGBA8888)
        image.fill(0x80FF0000)

        png_path = folder / "out.png"
        jpg_path = folder / "out.jpg"
        assert save_qimage(image, png_path, EXPORT_PNG)
        assert save_qimage(image, jpg_path, EXPORT_JPEG)
        assert png_path.stat().st_size > 0
        assert jpg_path.stat().st_size > 0


if __name__ == "__main__":
    test_heic_path_detection()
    test_export_path_for_format()
    test_save_png_and_jpeg()
    print("all image_io tests passed")