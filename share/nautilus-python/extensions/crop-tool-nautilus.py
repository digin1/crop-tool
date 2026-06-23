"""Nautilus context menu: Open with Crop Tool."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import List
from urllib.parse import unquote

from gi.repository import Nautilus, GObject

IMAGE_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".gif",
    ".webp",
    ".tiff",
    ".tif",
    ".heic",
    ".heif",
)


def _crop_tool_executable() -> str | None:
    for candidate in (
        shutil.which("crop-tool"),
        os.path.expanduser("~/.local/bin/crop-tool"),
        "/usr/local/bin/crop-tool",
    ):
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    return None


def _is_image(file: Nautilus.FileInfo) -> bool:
    if file.is_directory() or file.get_uri_scheme() != "file":
        return False

    mime = file.get_mime_type() or ""
    if mime.startswith("image/"):
        return True

    name = file.get_name().lower()
    return name.endswith(IMAGE_SUFFIXES)


class CropToolExtension(GObject.GObject, Nautilus.MenuProvider):
    def menu_activate_cb(
        self,
        menu: Nautilus.MenuItem,
        file: Nautilus.FileInfo,
    ) -> None:
        executable = _crop_tool_executable()
        if not executable:
            return

        path = unquote(file.get_uri()[7:])
        subprocess.Popen(
            [executable, path],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def get_file_items(
        self,
        files: List[Nautilus.FileInfo],
    ) -> List[Nautilus.MenuItem]:
        if len(files) != 1 or _crop_tool_executable() is None:
            return []

        file = files[0]
        if not _is_image(file):
            return []

        item = Nautilus.MenuItem(
            name="CropToolExtension::open",
            label="Open with Crop Tool",
            tip="Open this image in Crop Tool",
        )
        item.connect("activate", self.menu_activate_cb, file)
        return [item]

    def get_background_items(
        self,
        current_folder: Nautilus.FileInfo,
    ) -> List[Nautilus.MenuItem]:
        return []