"""Transient desktop selection overlay for screen query."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog


class ScreenSelectionUnavailable(RuntimeError):
    """Raised when screen selection cannot run on this runtime."""


class _ScreenSelectionDialog(QDialog):
    def __init__(self, screen, parent=None):
        super().__init__(parent)
        self._screen = screen
        self._screen_geom = screen.geometry()
        self._grab = screen.grabWindow(0)
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
        self.setGeometry(self._screen_geom)

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
            int(self._screen_geom.x() + rect.x()),
            int(self._screen_geom.y() + rect.y()),
            int(rect.width()),
            int(rect.height()),
        )

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt paintEvent signature
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._grab)
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
        raise ScreenSelectionUnavailable("Screen query is only available on Windows.")
    app = QApplication.instance()
    if app is None:
        raise ScreenSelectionUnavailable("Screen query is unavailable without a Qt app.")
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    if screen is None:
        raise ScreenSelectionUnavailable("No active screen was found.")
    dialog = _ScreenSelectionDialog(screen, parent=parent)
    dialog.showFullScreen()
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dialog.selected_global_rect()

