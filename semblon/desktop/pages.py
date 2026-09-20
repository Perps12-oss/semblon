"""Workspace page layer. Each page is a QWidget. The shell owns navigation.

Pages build UI in ``__init__``, expose ``refresh(service)``, and emit user
actions. Mutations stay in review.py. No FaceKit.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from semblon.desktop.service import PHOTO_SORTS, LibraryService
from semblon.desktop.widgets import EmptyState, ThumbGrid, folder_empty_state


class HomePage(QWidget):
    add_folder = Signal()
    open_unknown = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.welcome = QLabel("SEMBLON")
        self.welcome.setObjectName("title")
        self.welcome.setAccessibleName("Welcome")
        self.stats = QLabel("")
        self.stats.setObjectName("subtitle")
        self.stats.setWordWrap(True)
        self.stats.setAccessibleName("Library stats")
        self.recent = QListWidget()
        self.recent.setAccessibleName("Recent activity")
        self.empty = folder_empty_state(
            self,
            "No photos yet",
            "Add a folder of stills. Files stay where they are.",
            on_add=self.add_folder.emit,
        )
        self.btn_unknown = QPushButton("Open unknown")
        self.btn_unknown.setAccessibleName("Open unknown")
        self.btn_unknown.clicked.connect(self.open_unknown.emit)
        lay.addWidget(self.welcome)
        lay.addWidget(self.stats)
        lay.addWidget(QLabel("Recent"))
        lay.addWidget(self.recent)
        lay.addWidget(self.btn_unknown)
        lay.addWidget(self.empty)
        lay.addStretch(1)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        rec = service.home_summary()
        n_photos = int(rec.get("photos") or 0)
        n_people = int(rec.get("people") or 0)
        n_unknown = int(rec.get("unknown") or 0)
        self.stats.setText(
            f"{n_photos} photos · {rec.get('videos') or 0} videos · "
            f"{n_people} named people · {n_unknown} unknown groups"
        )
        self.recent.clear()
        for row in rec.get("recent") or []:
            item = QListWidgetItem(str(row.get("label") or row.get("run_id") or ""))
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.recent.addItem(item)
        has_media = n_photos > 0 or int(rec.get("videos") or 0) > 0
        self.empty.setVisible(not has_media)
        self.btn_unknown.setEnabled(n_unknown > 0)


class _MediaPage(QWidget):
    add_folder = Signal()
    inspect = Signal(object)

    def __init__(self, title: str, empty_title: str, empty_body: str, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.heading = QLabel(title)
        self.heading.setObjectName("title")
        self.heading.setAccessibleName(title)
        self.stack = QStackedWidget()
        self.empty = folder_empty_state(self, empty_title, empty_body, on_add=self.add_folder.emit)
        self.grid = ThumbGrid()
        self.grid.inspect.connect(self.inspect.emit)
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.grid)
        lay.addWidget(self.heading)
        lay.addWidget(self.stack)

    def _show_rows(self, rows: list[dict[str, Any]]) -> None:
        self.grid.set_items(rows)
        self.stack.setCurrentWidget(self.grid if rows else self.empty)


class PhotosPage(_MediaPage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            "Photos",
            "No photos yet",
            "Add a folder of still photographs.",
            parent,
        )
        self.sort = QComboBox()
        self.sort.setAccessibleName("Photos sort")
        for key, label in (("newest", "Newest"), ("oldest", "Oldest"), ("name", "Name")):
            self.sort.addItem(label, key)
        self.sort.currentIndexChanged.connect(self._on_sort_changed)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Sort"))
        bar.addWidget(self.sort)
        bar.addStretch(1)
        self.layout().insertLayout(1, bar)

    def sort_key(self) -> str:
        data = self.sort.currentData()
        return data if data in PHOTO_SORTS else "newest"

    def _on_sort_changed(self, _index: int = 0) -> None:
        if self._service is not None:
            self.refresh(self._service)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        self._show_rows(service.list_photos(sort=self.sort_key()))


class VideosPage(_MediaPage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            "Videos",
            "No videos yet",
            "Add a folder that contains sampled video. Tracks are not persons.",
            parent,
        )

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        self._show_rows(service.list_videos())


class PeoplePage(QWidget):
    inspect = Signal(object)
    rename = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.heading = QLabel("People")
        self.heading.setObjectName("title")
        self.heading.setAccessibleName("People")
        self.empty = EmptyState(
            "No named people",
            "Open Unknown and Name a group. A cluster is not a person until Name.",
        )
        self.grid = ThumbGrid()
        self.grid.set_context_actions([("inspect", "Inspect"), ("rename", "Rename")])
        self.grid.inspect.connect(self.inspect.emit)
        self.grid.context_action.connect(self._on_context)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.grid)
        lay.addWidget(self.heading)
        lay.addWidget(self.stack)

    def _on_context(self, key: str, payload: object) -> None:
        if key == "rename":
            self.rename.emit(payload)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        rows = service.list_people()
        self.grid.set_items(rows)
        self.stack.setCurrentWidget(self.grid if rows else self.empty)


class UnknownPage(QWidget):
    inspect = Signal(object)
    name = Signal(object)
    ignore = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.heading = QLabel("Unknown")
        self.heading.setObjectName("title")
        self.heading.setAccessibleName("Unknown")
        self.empty = EmptyState(
            "Nothing to review",
            "Unknown is valid. Process a folder, then Name groups you know.",
        )
        self.grid = ThumbGrid()
        self.grid.set_context_actions(
            [("inspect", "Inspect"), ("name", "Name"), ("ignore", "Ignore")]
        )
        self.grid.inspect.connect(self.inspect.emit)
        self.grid.context_action.connect(self._on_context)
        bar = QHBoxLayout()
        self.btn_name = QPushButton("Name")
        self.btn_name.setAccessibleName("Name unknown group")
        self.btn_ignore = QPushButton("Ignore")
        self.btn_ignore.setAccessibleName("Ignore unknown group")
        self.btn_name.clicked.connect(self._emit_name)
        self.btn_ignore.clicked.connect(self._emit_ignore)
        bar.addWidget(self.btn_name)
        bar.addWidget(self.btn_ignore)
        bar.addStretch(1)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.grid)
        lay.addWidget(self.heading)
        lay.addLayout(bar)
        lay.addWidget(self.stack)

    def _on_context(self, key: str, payload: object) -> None:
        if key == "name":
            self.name.emit(payload)
        elif key == "ignore":
            self.ignore.emit(payload)

    def _emit_name(self) -> None:
        payload = self.grid.current_payload()
        if payload is not None:
            self.name.emit(payload)

    def _emit_ignore(self) -> None:
        payload = self.grid.current_payload()
        if payload is not None:
            self.ignore.emit(payload)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        rows = service.list_unknown()
        self.grid.set_items(rows)
        self.stack.setCurrentWidget(self.grid if rows else self.empty)
        enabled = bool(rows)
        self.btn_name.setEnabled(enabled)
        self.btn_ignore.setEnabled(enabled)


class ActivityPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.heading = QLabel("Activity")
        self.heading.setObjectName("title")
        self.heading.setAccessibleName("Activity")
        self.list = QListWidget()
        self.list.setAccessibleName("Activity list")
        self.empty = EmptyState("No activity", "Process a folder to record a run.")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.list)
        lay.addWidget(self.heading)
        lay.addWidget(self.stack)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        rows = service.list_activity()
        self.list.clear()
        for row in rows:
            self.list.addItem(str(row.get("label") or row.get("run_id") or ""))
        self.stack.setCurrentWidget(self.list if rows else self.empty)


class SettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.heading = QLabel("Settings")
        self.heading.setObjectName("title")
        self.heading.setAccessibleName("Settings")
        self.body = QLabel("")
        self.body.setWordWrap(True)
        self.body.setAccessibleName("Settings status")
        lay.addWidget(self.heading)
        lay.addWidget(self.body)
        lay.addStretch(1)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        lines = service.settings_lines()
        self.body.setText("\n".join(ln for ln in lines if ln))
