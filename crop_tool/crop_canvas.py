from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget


class Handle(Enum):
    NONE = auto()
    TOP_LEFT = auto()
    TOP = auto()
    TOP_RIGHT = auto()
    RIGHT = auto()
    BOTTOM_RIGHT = auto()
    BOTTOM = auto()
    BOTTOM_LEFT = auto()
    LEFT = auto()
    MOVE = auto()


HANDLE_SIZE = 8
MIN_CROP_SIZE = 10


class CropCanvas(QWidget):
    """Interactive image viewer with draggable crop selection."""

    crop_changed = Signal(QRect)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image = QImage()
        self._crop_rect = QRect()
        self._aspect_ratio: float | None = None
        self._active_handle = Handle.NONE
        self._drag_start = QPoint()
        self._crop_at_drag_start = QRect()
        self._creating_selection = False

        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def has_image(self) -> bool:
        return not self._image.isNull()

    @property
    def crop_rect(self) -> QRect:
        return QRect(self._crop_rect)

    @property
    def aspect_ratio(self) -> float | None:
        return self._aspect_ratio

    def set_aspect_ratio(self, ratio: float | None) -> None:
        self._aspect_ratio = ratio
        if self._crop_rect.isValid() and ratio is not None:
            self._crop_rect = self._apply_aspect_ratio(self._crop_rect, Handle.BOTTOM_LEFT)
            self._emit_crop_changed()
        self.update()

    def load_image(self, image: QImage) -> None:
        self._image = image
        self._crop_rect = image.rect() if not image.isNull() else QRect()
        self._emit_crop_changed()
        self.update()

    def clear(self) -> None:
        self._image = QImage()
        self._crop_rect = QRect()
        self._emit_crop_changed()
        self.update()

    def reset_crop(self) -> None:
        if self.has_image:
            self._crop_rect = self._image.rect()
            self._emit_crop_changed()
            self.update()

    def is_full_crop(self) -> bool:
        return self.has_image and self._crop_rect == self._image.rect()

    def crop_image(self) -> QImage:
        if not self.has_image or not self._crop_rect.isValid():
            return QImage()
        rect = self._crop_rect.intersected(self._image.rect())
        return self._image.copy(rect)

    def _emit_crop_changed(self) -> None:
        self.crop_changed.emit(QRect(self._crop_rect))

    def _image_rect(self) -> QRectF:
        if not self.has_image:
            return QRectF()
        return self._fit_rect(self._image.size(), self.rect())

    def _fit_rect(self, source_size, target_rect: QRect) -> QRectF:
        if source_size.width() <= 0 or source_size.height() <= 0:
            return QRectF()
        scale = min(
            target_rect.width() / source_size.width(),
            target_rect.height() / source_size.height(),
        )
        width = source_size.width() * scale
        height = source_size.height() * scale
        x = target_rect.x() + (target_rect.width() - width) / 2
        y = target_rect.y() + (target_rect.height() - height) / 2
        return QRectF(x, y, width, height)

    def _widget_to_image(self, point: QPoint) -> QPoint:
        image_rect = self._image_rect()
        if image_rect.isEmpty():
            return QPoint()
        x = (point.x() - image_rect.x()) / image_rect.width() * self._image.width()
        y = (point.y() - image_rect.y()) / image_rect.height() * self._image.height()
        return QPoint(int(x), int(y))

    def _image_to_widget(self, rect: QRect) -> QRectF:
        image_rect = self._image_rect()
        if image_rect.isEmpty() or not rect.isValid():
            return QRectF()
        x = image_rect.x() + rect.x() / self._image.width() * image_rect.width()
        y = image_rect.y() + rect.y() / self._image.height() * image_rect.height()
        w = rect.width() / self._image.width() * image_rect.width()
        h = rect.height() / self._image.height() * image_rect.height()
        return QRectF(x, y, w, h)

    def _clamp_crop_rect(self, rect: QRect) -> QRect:
        bounds = self._image.rect()
        if not bounds.isValid():
            return QRect()
        rect = rect.normalized()
        if rect.width() < MIN_CROP_SIZE:
            rect.setWidth(MIN_CROP_SIZE)
        if rect.height() < MIN_CROP_SIZE:
            rect.setHeight(MIN_CROP_SIZE)
        if rect.left() < bounds.left():
            rect.moveLeft(bounds.left())
        if rect.top() < bounds.top():
            rect.moveTop(bounds.top())
        if rect.right() > bounds.right():
            rect.moveRight(bounds.right())
        if rect.bottom() > bounds.bottom():
            rect.moveBottom(bounds.bottom())
        return rect.intersected(bounds)

    def _ratio_close(self, rect: QRect) -> bool:
        if self._aspect_ratio is None or rect.height() <= 0:
            return True
        actual = rect.width() / rect.height()
        return abs(actual - self._aspect_ratio) < 0.02

    def _size_for_aspect(self, width: int, height: int) -> tuple[int, int]:
        ratio = self._aspect_ratio
        if ratio is None:
            return max(width, MIN_CROP_SIZE), max(height, MIN_CROP_SIZE)

        width = max(width, 1)
        height = max(height, 1)
        if width / height > ratio:
            width = max(MIN_CROP_SIZE, int(round(height * ratio)))
        else:
            height = max(MIN_CROP_SIZE, int(round(width / ratio)))
        return width, height

    def _rect_from_anchor(self, anchor: Handle, fixed_x: int, fixed_y: int, width: int, height: int) -> QRect:
        if anchor in {Handle.TOP_LEFT, Handle.LEFT, Handle.BOTTOM_LEFT}:
            left = fixed_x - width + 1
        else:
            left = fixed_x

        if anchor in {Handle.TOP_LEFT, Handle.TOP, Handle.TOP_RIGHT}:
            top = fixed_y - height + 1
        else:
            top = fixed_y

        return QRect(left, top, width, height).normalized()

    def _apply_aspect_ratio(self, rect: QRect, anchor: Handle) -> QRect:
        if self._aspect_ratio is None or not rect.isValid():
            return rect

        rect = rect.normalized()

        if anchor == Handle.MOVE:
            return rect

        if anchor in {Handle.TOP, Handle.BOTTOM}:
            height = max(rect.height(), MIN_CROP_SIZE)
            width = max(MIN_CROP_SIZE, int(round(height * self._aspect_ratio)))
            center_x = rect.center().x()
            top = rect.top() if anchor == Handle.BOTTOM else rect.bottom() - height + 1
            left = center_x - width // 2
            rect = QRect(left, top, width, height).normalized()
        elif anchor in {Handle.LEFT, Handle.RIGHT}:
            width = max(rect.width(), MIN_CROP_SIZE)
            height = max(MIN_CROP_SIZE, int(round(width / self._aspect_ratio)))
            center_y = rect.center().y()
            left = rect.left() if anchor == Handle.RIGHT else rect.right() - width + 1
            top = center_y - height // 2
            rect = QRect(left, top, width, height).normalized()
        else:
            if anchor == Handle.TOP_LEFT:
                fixed_x, fixed_y = rect.right(), rect.bottom()
            elif anchor == Handle.TOP_RIGHT:
                fixed_x, fixed_y = rect.left(), rect.bottom()
            elif anchor == Handle.BOTTOM_LEFT:
                fixed_x, fixed_y = rect.right(), rect.top()
            else:  # BOTTOM_RIGHT and new selections
                fixed_x, fixed_y = rect.left(), rect.top()

            width, height = self._size_for_aspect(rect.width(), rect.height())
            rect = self._rect_from_anchor(anchor, fixed_x, fixed_y, width, height)

        return self._constrain_crop_rect(rect, anchor)

    def _constrain_crop_rect(self, rect: QRect, anchor: Handle) -> QRect:
        bounds = self._image.rect()
        if not bounds.isValid():
            return QRect()

        rect = rect.normalized()
        if self._aspect_ratio is None:
            return self._clamp_crop_rect(rect)

        ratio = self._aspect_ratio
        width = rect.width()
        height = rect.height()

        max_width = bounds.width()
        max_height = bounds.height()
        if width > max_width:
            width = max_width
            height = max(MIN_CROP_SIZE, int(round(width / ratio)))
        if height > max_height:
            height = max_height
            width = max(MIN_CROP_SIZE, int(round(height * ratio)))

        width = max(width, MIN_CROP_SIZE)
        height = max(height, MIN_CROP_SIZE)
        width = max(width, int(round(height * ratio)))
        height = max(MIN_CROP_SIZE, int(round(width / ratio)))

        if anchor in {Handle.TOP, Handle.BOTTOM}:
            center_x = rect.center().x()
            top = rect.top() if anchor == Handle.BOTTOM else rect.bottom() - height + 1
            left = center_x - width // 2
            rect = QRect(left, top, width, height).normalized()
        elif anchor in {Handle.LEFT, Handle.RIGHT}:
            center_y = rect.center().y()
            left = rect.left() if anchor == Handle.RIGHT else rect.right() - width + 1
            top = center_y - height // 2
            rect = QRect(left, top, width, height).normalized()
        elif anchor == Handle.TOP_LEFT:
            rect = QRect(rect.right() - width + 1, rect.bottom() - height + 1, width, height)
        elif anchor == Handle.TOP_RIGHT:
            rect = QRect(rect.left(), rect.bottom() - height + 1, width, height)
        elif anchor == Handle.BOTTOM_LEFT:
            rect = QRect(rect.right() - width + 1, rect.top(), width, height)
        else:
            rect = QRect(rect.left(), rect.top(), width, height)

        rect = rect.normalized()
        if rect.left() < bounds.left():
            rect.moveLeft(bounds.left())
        if rect.top() < bounds.top():
            rect.moveTop(bounds.top())
        if rect.right() > bounds.right():
            rect.moveRight(bounds.right())
        if rect.bottom() > bounds.bottom():
            rect.moveBottom(bounds.bottom())

        if (
            rect.left() < bounds.left()
            or rect.top() < bounds.top()
            or rect.right() > bounds.right()
            or rect.bottom() > bounds.bottom()
        ):
            width = min(rect.width(), bounds.width())
            height = min(rect.height(), bounds.height())
            if width / max(height, 1) > ratio:
                width = max(MIN_CROP_SIZE, int(round(height * ratio)))
            else:
                height = max(MIN_CROP_SIZE, int(round(width / ratio)))
            width = min(width, bounds.width())
            height = min(height, bounds.height())
            rect = QRect(bounds.left(), bounds.top(), width, height).normalized()

        return rect.intersected(bounds)

    def _handle_at(self, point: QPoint) -> Handle:
        if not self._crop_rect.isValid():
            return Handle.NONE
        widget_rect = self._image_to_widget(self._crop_rect)
        margin = HANDLE_SIZE + 2
        checks = [
            (Handle.TOP_LEFT, QRectF(widget_rect.topLeft().x(), widget_rect.topLeft().y(), margin, margin)),
            (Handle.TOP_RIGHT, QRectF(widget_rect.topRight().x() - margin, widget_rect.topRight().y(), margin, margin)),
            (Handle.BOTTOM_LEFT, QRectF(widget_rect.bottomLeft().x(), widget_rect.bottomLeft().y() - margin, margin, margin)),
            (Handle.BOTTOM_RIGHT, QRectF(widget_rect.bottomRight().x() - margin, widget_rect.bottomRight().y() - margin, margin, margin)),
            (Handle.TOP, QRectF(widget_rect.center().x() - margin / 2, widget_rect.top(), margin, margin)),
            (Handle.BOTTOM, QRectF(widget_rect.center().x() - margin / 2, widget_rect.bottom() - margin, margin, margin)),
            (Handle.LEFT, QRectF(widget_rect.left(), widget_rect.center().y() - margin / 2, margin, margin)),
            (Handle.RIGHT, QRectF(widget_rect.right() - margin, widget_rect.center().y() - margin / 2, margin, margin)),
        ]
        for handle, area in checks:
            if area.contains(point):
                return handle
        if widget_rect.contains(point):
            return Handle.MOVE
        return Handle.NONE

    def _cursor_for_handle(self, handle: Handle):
        mapping = {
            Handle.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
            Handle.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            Handle.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
            Handle.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
            Handle.LEFT: Qt.CursorShape.SizeHorCursor,
            Handle.RIGHT: Qt.CursorShape.SizeHorCursor,
            Handle.TOP: Qt.CursorShape.SizeVerCursor,
            Handle.BOTTOM: Qt.CursorShape.SizeVerCursor,
            Handle.MOVE: Qt.CursorShape.SizeAllCursor,
        }
        return mapping.get(handle, Qt.CursorShape.CrossCursor)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if not self.has_image:
            painter.setPen(QColor(180, 180, 180))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Open an image to begin cropping")
            return

        image_rect = self._image_rect()
        pixmap = QPixmap.fromImage(self._image).scaled(
            int(image_rect.width()),
            int(image_rect.height()),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(int(image_rect.x()), int(image_rect.y()), pixmap)

        if not self._crop_rect.isValid():
            return

        crop_widget_rect = self._image_to_widget(self._crop_rect)

        overlay = QColor(0, 0, 0, 120)
        full = QRectF(self.rect())
        painter.fillRect(QRectF(full.left(), full.top(), full.width(), crop_widget_rect.top()), overlay)
        painter.fillRect(
            QRectF(full.left(), crop_widget_rect.bottom(), full.width(), full.bottom() - crop_widget_rect.bottom()),
            overlay,
        )
        painter.fillRect(
            QRectF(full.left(), crop_widget_rect.top(), crop_widget_rect.left() - full.left(), crop_widget_rect.height()),
            overlay,
        )
        painter.fillRect(
            QRectF(crop_widget_rect.right(), crop_widget_rect.top(), full.right() - crop_widget_rect.right(), crop_widget_rect.height()),
            overlay,
        )

        pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawRect(crop_widget_rect)

        grid_pen = QPen(QColor(255, 255, 255, 90), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        third_w = crop_widget_rect.width() / 3
        third_h = crop_widget_rect.height() / 3
        for i in range(1, 3):
            x = crop_widget_rect.left() + third_w * i
            y = crop_widget_rect.top() + third_h * i
            painter.drawLine(int(x), int(crop_widget_rect.top()), int(x), int(crop_widget_rect.bottom()))
            painter.drawLine(int(crop_widget_rect.left()), int(y), int(crop_widget_rect.right()), int(y))

        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QPen(QColor(40, 40, 40), 1))
        handle_points = [
            crop_widget_rect.topLeft(),
            QPointF(crop_widget_rect.center().x(), crop_widget_rect.top()),
            crop_widget_rect.topRight(),
            QPointF(crop_widget_rect.right(), crop_widget_rect.center().y()),
            crop_widget_rect.bottomRight(),
            QPointF(crop_widget_rect.center().x(), crop_widget_rect.bottom()),
            crop_widget_rect.bottomLeft(),
            QPointF(crop_widget_rect.left(), crop_widget_rect.center().y()),
        ]
        half = HANDLE_SIZE / 2
        for point in handle_points:
            painter.drawRect(QRectF(point.x() - half, point.y() - half, HANDLE_SIZE, HANDLE_SIZE))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.has_image or event.button() != Qt.MouseButton.LeftButton:
            return
        image_rect = self._image_rect()
        if not image_rect.contains(event.position()):
            return

        self._active_handle = self._handle_at(event.position().toPoint())
        self._drag_start = event.position().toPoint()
        self._crop_at_drag_start = QRect(self._crop_rect)

        if self._active_handle == Handle.NONE:
            self._creating_selection = True
            origin = self._widget_to_image(event.position().toPoint())
            self._crop_rect = QRect(origin, origin)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.has_image:
            return

        if self._active_handle == Handle.NONE and not self._creating_selection:
            handle = self._handle_at(event.position().toPoint())
            self.setCursor(self._cursor_for_handle(handle))
            return

        if self._active_handle == Handle.NONE and not self._creating_selection:
            return

        current_image = self._widget_to_image(event.position().toPoint())
        start_image = self._widget_to_image(self._drag_start)

        if self._creating_selection:
            rect = QRect(start_image, current_image).normalized()
            if self._aspect_ratio is not None and rect.width() > 0 and rect.height() > 0:
                rect = self._apply_aspect_ratio(rect, Handle.BOTTOM_RIGHT)
            else:
                rect = self._clamp_crop_rect(rect)
            self._crop_rect = rect
        else:
            rect = QRect(self._crop_at_drag_start)
            dx = current_image.x() - start_image.x()
            dy = current_image.y() - start_image.y()

            if self._active_handle == Handle.MOVE:
                rect.translate(dx, dy)
                self._crop_rect = self._clamp_crop_rect(rect)
            elif self._aspect_ratio is not None:
                if self._active_handle in {Handle.LEFT, Handle.TOP_LEFT, Handle.BOTTOM_LEFT}:
                    rect.setLeft(rect.left() + dx)
                if self._active_handle in {Handle.RIGHT, Handle.TOP_RIGHT, Handle.BOTTOM_RIGHT}:
                    rect.setRight(rect.right() + dx)
                if self._active_handle in {Handle.TOP, Handle.TOP_LEFT, Handle.TOP_RIGHT}:
                    rect.setTop(rect.top() + dy)
                if self._active_handle in {Handle.BOTTOM, Handle.BOTTOM_LEFT, Handle.BOTTOM_RIGHT}:
                    rect.setBottom(rect.bottom() + dy)
                self._crop_rect = self._apply_aspect_ratio(rect.normalized(), self._active_handle)
            else:
                if self._active_handle in {Handle.LEFT, Handle.TOP_LEFT, Handle.BOTTOM_LEFT}:
                    rect.setLeft(rect.left() + dx)
                if self._active_handle in {Handle.RIGHT, Handle.TOP_RIGHT, Handle.BOTTOM_RIGHT}:
                    rect.setRight(rect.right() + dx)
                if self._active_handle in {Handle.TOP, Handle.TOP_LEFT, Handle.TOP_RIGHT}:
                    rect.setTop(rect.top() + dy)
                if self._active_handle in {Handle.BOTTOM, Handle.BOTTOM_LEFT, Handle.BOTTOM_RIGHT}:
                    rect.setBottom(rect.bottom() + dy)
                self._crop_rect = self._clamp_crop_rect(rect.normalized())

        self._emit_crop_changed()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._active_handle = Handle.NONE
        self._creating_selection = False
        if self._crop_rect.width() < MIN_CROP_SIZE or self._crop_rect.height() < MIN_CROP_SIZE:
            self.reset_crop()