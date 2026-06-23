from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from crop_tool.image_formats import EXPORT_JPEG, EXPORT_PNG, HEIC_SUFFIXES, is_heic_path

_HEIF_REGISTERED = False


def _ensure_heif_support() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    try:
        import pillow_heif
    except ImportError as exc:
        raise RuntimeError(
            "HEIC support requires pillow-heif. Reinstall crop-tool to add the dependency."
        ) from exc
    pillow_heif.register_heif_opener()
    _HEIF_REGISTERED = True


def _pil_to_qimage(pil_image) -> QImage:
    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")
    data = pil_image.tobytes("raw", "RGBA")
    qimage = QImage(
        data,
        pil_image.width,
        pil_image.height,
        QImage.Format.Format_RGBA8888,
    )
    return qimage.copy()


def _load_heic(path: Path) -> QImage:
    _ensure_heif_support()
    from PIL import Image

    with Image.open(path) as pil_image:
        return _pil_to_qimage(pil_image)


def load_qimage(path: Path) -> QImage:
    path = path.expanduser().resolve()
    if path.suffix.lower() in HEIC_SUFFIXES:
        try:
            return _load_heic(path)
        except RuntimeError:
            raise
        except Exception:
            return QImage()

    image = QImage(str(path))
    return image if not image.isNull() else QImage()


def _prepare_for_export(image: QImage, export_format: str) -> QImage:
    if export_format != EXPORT_JPEG:
        return image
    if image.hasAlphaChannel():
        flattened = QImage(image.size(), QImage.Format.Format_RGB32)
        flattened.fill(0xFFFFFFFF)
        from PySide6.QtGui import QPainter

        painter = QPainter(flattened)
        painter.drawImage(0, 0, image)
        painter.end()
        return flattened
    if image.format() != QImage.Format.Format_RGB32:
        return image.convertToFormat(QImage.Format.Format_RGB32)
    return image


def save_qimage(image: QImage, path: Path, export_format: str | None = None) -> bool:
    path = path.expanduser().resolve()
    suffix = path.suffix.lower()

    if export_format is None:
        if suffix in {".jpg", ".jpeg"}:
            export_format = EXPORT_JPEG
        else:
            export_format = EXPORT_PNG

    prepared = _prepare_for_export(image, export_format)
    if export_format == EXPORT_JPEG:
        return prepared.save(str(path), "JPEG", 92)
    return prepared.save(str(path), "PNG")


def heic_load_error_message() -> str:
    return (
        "Could not open HEIC image.\n"
        "The file may be corrupt, or HEIC support may not be installed."
    )