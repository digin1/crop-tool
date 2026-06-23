import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from crop_tool.crop_canvas import CropCanvas, Handle

app = QApplication(sys.argv)


def _canvas_with_image(width: int, height: int) -> CropCanvas:
    canvas = CropCanvas()
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFF)
    canvas.load_image(image)
    canvas._crop_rect = QRect(0, 0, width - 1, height - 1)
    return canvas


def _assert_ratio(canvas: CropCanvas, rect: QRect, expected: float) -> None:
    actual = rect.width() / rect.height()
    assert abs(actual - expected) < 0.03, (actual, expected, rect)


def test_corner_resize_keeps_ratio() -> None:
    canvas = _canvas_with_image(400, 300)
    canvas.set_aspect_ratio(1.0)
    rect = QRect(100, 80, 199, 149)
    locked = canvas._apply_aspect_ratio(rect, Handle.BOTTOM_RIGHT)
    _assert_ratio(canvas, locked, 1.0)
    assert locked.left() == rect.left()
    assert locked.top() == rect.top()


def test_top_handle_keeps_ratio_and_bottom_edge() -> None:
    canvas = _canvas_with_image(400, 300)
    canvas.set_aspect_ratio(16 / 9)
    rect = QRect(50, 40, 249, 199)
    locked = canvas._apply_aspect_ratio(rect, Handle.TOP)
    _assert_ratio(canvas, locked, 16 / 9)
    assert locked.bottom() == rect.bottom()


def test_left_handle_keeps_ratio_and_right_edge() -> None:
    canvas = _canvas_with_image(400, 300)
    canvas.set_aspect_ratio(4 / 3)
    rect = QRect(20, 30, 219, 189)
    locked = canvas._apply_aspect_ratio(rect, Handle.LEFT)
    _assert_ratio(canvas, locked, 4 / 3)
    assert locked.right() == rect.right()


def test_constrain_does_not_break_ratio() -> None:
    canvas = _canvas_with_image(200, 200)
    canvas.set_aspect_ratio(1.0)
    rect = QRect(-20, -20, 239, 239)
    constrained = canvas._constrain_crop_rect(rect.normalized(), Handle.BOTTOM_RIGHT)
    _assert_ratio(canvas, constrained, 1.0)
    assert constrained.left() >= 0
    assert constrained.top() >= 0


if __name__ == "__main__":
    test_corner_resize_keeps_ratio()
    test_top_handle_keeps_ratio_and_bottom_edge()
    test_left_handle_keeps_ratio_and_right_edge()
    test_constrain_does_not_break_ratio()
    print("all aspect ratio tests passed")