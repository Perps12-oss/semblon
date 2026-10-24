"""Transient desktop selection overlay for screen query.

The overlay spans the virtual desktop so selection works on multi-monitor
Windows setups. It returns global desktop pixels for downstream query.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog


class ScreenSelectionUnavailable(RuntimeError):
    """Raised when screen selection cannot run on this runtime."""


def _union_bounds(bounds: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    if not bounds:
        raise ValueError("no screen bounds")
    left = min(x for x, _y, _w, _h in bounds)
    top = min(y for _x, y, _w, _h in bounds)
    right = max(x + w for x, _y, w, _h in bounds)
    bottom = max(y + h for _x, y, _w, h in bounds)
    return left, top, right - left, bottom - top


def _screen_bounds(screen) -> tuple[int, int, int, int]:
    geom = screen.geometry()
    return int(geom.x()), int(geom.y()), int(geom.width()), int(geom.height())


class _ScreenSelectionDialog(QDialog):
    def __init__(self, screens, parent=None):
        super().__init__(parent)
        self._screens = list(screens)
        if not self._screens:
            raise ScreenSelectionUnavailable("No active screen was found.")
        vx, vy, vw, vh = _union_bounds([_screen_bounds(screen) for screen in self._screens])
        self._virtual_geom = QRect(vx, vy, vw, vh)
        self._grabs: list[tuple[QRect, object]] = []
        for screen in self._screens:
            self._grabs.append((screen.geometry(), screen.grabWindow(0)))
        self._origin = QPoint()
        self._rect = QRect()
        self._dragging = False
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setModal(True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(self._virtual_geom)

    def _selected_rect(self) -> QRect:
        rect = self._rect.normalized()
        if rect.width() < 2 or rect.height() < 2:
            return QRect()
        return rect

    def selected_global_rect(self) -> tuple[int, int, int, int] | None:
        rect = self._selected_rect()
        if rect.isNull():
            return None
        return (
            int(self._virtual_geom.x() + rect.x()),
            int(self._virtual_geom.y() + rect.y()),
            int(rect.width()),
            int(rect.height()),
        )

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt paintEvent signature
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 10, 10, 255))
        for screen_geom, pixmap in self._grabs:
            target = QRect(
                int(screen_geom.x() - self._virtual_geom.x()),
                int(screen_geom.y() - self._virtual_geom.y()),
                int(screen_geom.width()),
                int(screen_geom.height()),
            )
            if target.width() <= 0 or target.height() <= 0:
                continue
            painter.drawPixmap(target, pixmap, pixmap.rect())
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        rect = self._selected_rect()
        if not rect.isNull():
            painter.fillRect(rect, QColor(255, 255, 255, 24))
            pen = QPen(QColor(255, 255, 255, 220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt mousePressEvent signature
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._origin = event.position().toPoint()
        self._rect = QRect(self._origin, self._origin)
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt mouseMoveEvent signature
        if not self._dragging:
            return
        self._rect = QRect(self._origin, event.position().toPoint())
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt mouseReleaseEvent signature
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = False
        self._rect = QRect(self._origin, event.position().toPoint())
        self.update()
        if self._selected_rect().isNull():
            self.reject()
            return
        self.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt keyPressEvent signature
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)


def select_screen_region(parent=None) -> tuple[int, int, int, int] | None:
    """Return a global screen rectangle selected by the user."""
    if sys.platform != "win32":
        raise ScreenSelectionUnavailable("Picking on screen is only available on Windows.")
    app = QApplication.instance()
    if app is None:
        raise ScreenSelectionUnavailable("Picking on screen is unavailable without a Qt app.")
    screens = list(QGuiApplication.screens())
    if not screens:
        raise ScreenSelectionUnavailable("No active screen was found.")
    # Keep cursor hinting on the current screen by preserving z-order and focus.
    _focused = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    dialog = _ScreenSelectionDialog(screens, parent=parent)
    dialog.show()
    if _focused is not None:
        handle = dialog.windowHandle()
        if handle is not None:
            handle.setScreen(_focused)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dialog.selected_global_rect()

