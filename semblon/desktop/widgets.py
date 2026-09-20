"""Shared desktop widgets. Presentation only. No FaceKit. No identity."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class EmptyState(QFrame):
    """Consistent empty/error panel. Optional primary action."""

    action = Signal()

    def __init__(self, title: str, body: str, action_label: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setAccessibleName(title)
        lay = QVBoxLayout(self)
        self._title = QLabel(title)
        self._title.setObjectName("emptyTitle")
        self._body = QLabel(body)
        self._body.setWordWrap(True)
        self._body.setObjectName("emptyBody")
        lay.addWidget(self._title)
        lay.addWidget(self._body)
        self._button: QPushButton | None = None
        if action_label:
            self._button = QPushButton(action_label)
            self._button.setAccessibleName(action_label)
            self._button.clicked.connect(self.action.emit)
            lay.addWidget(self._button, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)

    def set_copy(self, title: str, body: str) -> None:
        self._title.setText(title)
        self._body.setText(body)
        self.setAccessibleName(title)


def folder_empty_state(
    parent: QWidget,
    title: str,
    body: str,
    *,
    on_add: Callable[[], None],
) -> EmptyState:
    """Home / Photos / Videos share the same add-folder empty panel."""
    panel = EmptyState(title, body, "Add folder", parent)
    panel.action.connect(on_add)
    return panel


class ThumbGrid(QListWidget):
    """Icon grid: selection, activation, and optional context actions."""

    inspect = Signal(object)
    context_action = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.itemActivated.connect(self._activate)
        self.itemDoubleClicked.connect(self._activate)
        self.customContextMenuRequested.connect(self._menu)
        self.setAccessibleName("Thumbnail grid")
        self._actions: list[tuple[str, str]] = [("inspect", "Inspect")]
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_context_actions(self, actions: list[tuple[str, str]]) -> None:
        self._actions = list(actions)

    def set_items(self, rows: list[dict[str, Any]]) -> None:
        self.clear()
        for row in rows:
            label = str(row.get("label") or row.get("path") or row.get("id") or "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setToolTip(str(row.get("path") or label))
            self.addItem(item)

    def current_payload(self) -> dict[str, Any] | None:
        item = self.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else None

    def _activate(self, item: QListWidgetItem | None = None) -> None:
        if item is None:
            item = self.currentItem()
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            self.inspect.emit(data)

    def _menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        self.setCurrentItem(item)
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return
        menu = QMenu(self)
        for key, label in self._actions:
            act = QAction(label, menu)
            act.setData((key, payload))
            menu.addAction(act)
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is None:
            return
        key, data = chosen.data()
        if key == "inspect":
            self.inspect.emit(data)
        else:
            self.context_action.emit(str(key), data)
