#!/usr/bin/env python3
"""Create synthetic demo images for screenshots (no user folders)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo" / "assets"


def _draw_sample(draw: ImageDraw.ImageDraw, size: tuple[int, int], palette: list[tuple[int, int, int]], title: str) -> None:
    width, height = size
    block_w = width // 4
    block_h = height // 4
    for row in range(4):
        for col in range(4):
            color = palette[(row + col) % len(palette)]
            x0 = col * block_w
            y0 = row * block_h
            draw.rectangle([x0, y0, x0 + block_w, y0 + block_h], fill=color)

    draw.rectangle([40, 40, width - 40, height - 40], outline=(255, 255, 255), width=6)
    draw.line([(60, height // 2), (width - 60, height // 2)], fill=(255, 255, 255), width=4)
    draw.line([(width // 2, 60), (width // 2, height - 60)], fill=(255, 255, 255), width=4)
    draw.rectangle([width // 4, height // 4, 3 * width // 4, 3 * height // 4], outline=(255, 220, 80), width=5)
    draw.text((52, 52), title, fill=(255, 255, 255))


def main() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    samples = [
        ("landscape-color-grid.png", (960, 540), [(52, 120, 246), (16, 185, 129), (244, 114, 182), (251, 191, 36)], "DEMO LANDSCAPE"),
        ("portrait-sunset-blocks.png", (480, 720), [(249, 115, 22), (239, 68, 68), (99, 102, 241), (34, 197, 94)], "DEMO PORTRAIT"),
        ("square-preview-lab.png", (640, 640), [(14, 165, 233), (168, 85, 247), (20, 184, 166), (234, 179, 8)], "DEMO SQUARE"),
    ]

    for filename, size, palette, title in samples:
        image = Image.new("RGB", size, palette[0])
        draw = ImageDraw.Draw(image)
        _draw_sample(draw, size, palette, title)
        image.save(DEMO_DIR / filename)

    print(f"Generated {len(samples)} demo images in {DEMO_DIR}")


if __name__ == "__main__":
    main()