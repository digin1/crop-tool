"""Command-line entry point for the crop tool."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crop-tool",
        description="Desktop image crop tool — open, select a region, and save.",
    )
    parser.add_argument(
        "image",
        nargs="?",
        help="Optional image file to open on launch",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    image_path: str | None = None
    if args.image:
        path = Path(args.image).expanduser().resolve()
        if path.is_dir():
            print(f"error: expected a file, got a directory: {path}", file=sys.stderr)
            return 1
        if not path.is_file():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 1
        if not os.access(path, os.R_OK):
            print(f"error: no permission to read: {path}", file=sys.stderr)
            return 1
        image_path = str(path)

    from crop_tool.main_window import run_app

    return run_app(image_path=image_path)


if __name__ == "__main__":
    raise SystemExit(main())