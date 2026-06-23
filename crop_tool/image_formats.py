from __future__ import annotations

from pathlib import Path

HEIC_SUFFIXES = {".heic", ".heif"}

STANDARD_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".gif",
    ".webp",
    ".tiff",
    ".tif",
}

IMAGE_SUFFIXES = STANDARD_SUFFIXES | HEIC_SUFFIXES

IMAGE_FILTER = (
    "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif *.heic *.heif);;"
    "All Files (*)"
)

EXPORT_PNG = "PNG"
EXPORT_JPEG = "JPEG"
EXPORT_SUFFIXES = {
    EXPORT_PNG: ".png",
    EXPORT_JPEG: ".jpg",
}


def is_heic_path(path: Path) -> bool:
    return path.suffix.lower() in HEIC_SUFFIXES


def export_path_for_format(source: Path, export_format: str) -> Path:
    suffix = EXPORT_SUFFIXES.get(export_format, ".png")
    return source.with_suffix(suffix)