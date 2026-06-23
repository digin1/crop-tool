from __future__ import annotations

import errno
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileSnapshot:
    mtime_ns: int
    size: int


def snapshot(path: Path) -> FileSnapshot | None:
    try:
        stat = path.stat()
        return FileSnapshot(stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None


def has_changed(path: Path, before: FileSnapshot | None) -> bool:
    if before is None:
        return False
    current = snapshot(path)
    return current is None or current != before


def is_readable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.R_OK)


def describe_os_error(exc: OSError) -> str:
    messages = {
        errno.ENOSPC: "Disk is full. Free some space and try again.",
        errno.EACCES: "Permission denied.",
        errno.EROFS: "The filesystem is read-only.",
        errno.ENAMETOOLONG: "The file path is too long.",
        errno.ENOENT: "The folder or file no longer exists.",
    }
    return messages.get(exc.errno, str(exc))