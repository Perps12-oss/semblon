"""Shared desktop widgets. Presentation only. No FaceKit. No identity."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
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


class ProgressBanner(QFrame):
    cancel_requested = Signal()
    review_requested = Signal()
    dismissed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        self.headline = QLabel("Processing library…")
        self.headline.setObjectName("title")
        self.detail = QLabel("")
        self.detail.setObjectName("subtitle")
        self.detail.setWordWrap(True)
        self.current = QLabel("")
        self.current.setObjectName("muted")
        self.stopping = QLabel("")
        self.stopping.setObjectName("muted")
        self.stopping.setWordWrap(True)
        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setAccessibleName("Cancel import")
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.review_btn = QPushButton("Review results")
        self.review_btn.clicked.connect(self.review_requested.emit)
        self.done_btn = QPushButton("Done")
        self.done_btn.clicked.connect(self.dismissed.emit)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.review_btn)
        btn_row.addWidget(self.done_btn)
        btn_row.addStretch(1)
        lay.addWidget(self.headline)
        lay.addWidget(self.detail)
        lay.addWidget(self.current)
        lay.addWidget(self.stopping)
        lay.addLayout(btn_row)
        self._stopping = False
        self.hide()
        self.reset_busy()

    def reset_busy(self) -> None:
        self._stopping = False
        self.cancel_btn.show()
        self.cancel_btn.setEnabled(True)
        self.review_btn.hide()
        self.done_btn.hide()
        self.stopping.hide()
        self.stopping.clear()

    def show_busy(self, snap: dict) -> None:
        self.show()
        lines = snap.get("lines") or []
        detail = "\n".join(lines[1:2])
        extra = lines[2:] if len(lines) > 2 else []
        current = "\n".join(extra) if extra else snap.get("counts") or ""
        if self._stopping:
            self.detail.setText(detail)
            self.current.setText(current)
            return
        self.reset_busy()
        self.headline.setText(snap.get("headline") or "Processing library…")
        self.detail.setText(detail)
        self.current.setText(current)

    def show_stopping(self) -> None:
        self.show()
        self._stopping = True
        self.cancel_btn.setEnabled(False)
        self.stopping.setText("Stopping after the current operation…\nDo not close Semblon.")
        self.stopping.show()
        self.headline.setText("Stopping…")

    def show_cancelled(self, processed_line: str) -> None:
        self.show()
        self._stopping = False
        self.cancel_btn.hide()
        self.review_btn.show()
        self.done_btn.show()
        self.stopping.hide()
        self.headline.setText("Import cancelled")
        self.detail.setText(processed_line)
        self.current.setText("Partial results have been retained.")

    def show_complete(self, summary: str) -> None:
        self.show()
        self._stopping = False
        self.cancel_btn.hide()
        self.review_btn.show()
        self.done_btn.show()
        self.stopping.hide()
        self.headline.setText("Import complete")
        self.detail.setText(summary)
        self.current.clear()

    def show_failed(self, user: str) -> None:
        self.show()
        self._stopping = False
        self.cancel_btn.hide()
        self.review_btn.hide()
        self.done_btn.show()
        self.stopping.hide()
        self.headline.setText("Semblon couldn't complete this operation.")
        self.detail.setText(user)
        self.current.clear()


class InspectorPanel(QWidget):
    name_requested = Signal()
    ignore_requested = Signal()
    open_folder_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        lay = QVBoxLayout(self)
        self.preview = QLabel("Select an item to inspect")
        self.preview.setObjectName("muted")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(160)
        self.preview.setWordWrap(True)
        self.title = QLabel("")
        self.title.setObjectName("title")
        self.title.setWordWrap(True)
        self.body = QLabel("")
        self.body.setObjectName("subtitle")
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_btn = QPushButton("Show containing folder")
        self.open_btn.clicked.connect(self.open_folder_requested.emit)
        self.name_btn = QPushButton("Name person")
        self.name_btn.setObjectName("primary")
        self.name_btn.clicked.connect(self.name_requested.emit)
        self.ignore_btn = QPushButton("Ignore")
        self.ignore_btn.clicked.connect(self.ignore_requested.emit)
        lay.addWidget(self.preview)
        lay.addWidget(self.title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        inner = QVBoxLayout(holder)
        inner.addWidget(self.body)
        inner.addStretch(1)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        lay.addWidget(self.open_btn)
        lay.addWidget(self.name_btn)
        lay.addWidget(self.ignore_btn)
        self.clear()

    def clear(self) -> None:
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Select an item to inspect")
        self.title.clear()
        self.body.clear()
        self.open_btn.hide()
        self.name_btn.hide()
        self.ignore_btn.hide()
        self._path = None

    def show_media(self, rec: dict, pix: QPixmap | None = None) -> None:
        self._path = rec.get("path")
        self.title.setText(rec.get("label") or rec.get("title") or "Media")
        if pix is not None and not pix.isNull():
            self.preview.setPixmap(
                pix.scaled(
                    240,
                    180,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.preview.setText("")
        else:
            self.preview.setText(rec.get("label") or "")
        lines = [
            rec.get("path") or "",
            f"Source: {rec.get('source') or rec.get('source_type') or rec.get('kind') or ''}",
        ]
        if rec.get("note"):
            lines.append(rec["note"])
        self.body.setText("\n".join(ln for ln in lines if ln))
        self.open_btn.setVisible(bool(self._path))
        self.name_btn.hide()
        self.ignore_btn.hide()

    def show_unknown(self, rec: dict, pix: QPixmap | None = None) -> None:
        self._path = rec.get("path")
        self.title.setText(rec.get("title") or rec.get("label") or "Unknown")
        if pix is not None and not pix.isNull():
            self.preview.setPixmap(
                pix.scaled(
                    160,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.preview.setText("")
        self.body.setText("\n".join(x for x in [rec.get("subtitle"), rec.get("hint")] if x))
        self.open_btn.setVisible(bool(self._path))
        self.name_btn.setText("Name person")
        self.name_btn.show()
        self.ignore_btn.show()

    def show_person(self, rec: dict, pix: QPixmap | None = None) -> None:
        self._path = None
        self.title.setText(rec.get("display_name") or rec.get("label") or "Person")
        if pix is not None and not pix.isNull():
            self.preview.setPixmap(
                pix.scaled(
                    160,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.preview.setText("")
        lines = [f"{int(rec.get('faces') or 0)} associated observations"]
        if rec.get("why"):
            lines.append(rec["why"])
        lines.append("A person is not a cluster or a track.")
        self.body.setText("\n".join(lines))
        self.open_btn.hide()
        self.name_btn.setText("Rename")
        self.name_btn.show()
        self.ignore_btn.hide()

    def path(self) -> str | None:
        return self._path


def load_still_thumb(path: str, max_side: int = 160) -> QPixmap:
    p = Path(path)
    if not p.is_file():
        return QPixmap()
    img = QImage(str(p))
    if img.isNull():
        return QPixmap()
    pix = QPixmap.fromImage(img)
    return pix.scaled(
        max_side,
        max_side,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def open_containing_folder(path: str) -> None:
    p = Path(path)
    target = p.parent if p.exists() else p.parent
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
