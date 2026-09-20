"""Workspace page layer. Each page is a QWidget. The shell owns navigation.

Pages build UI in ``__init__``, expose ``refresh(service)``, and emit user
actions. Mutations stay in review.py. No FaceKit.
"""

from __future__ import annotations

import threading
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

from semblon.desktop.service import PHOTO_SORTS, PHOTO_SORT_LABELS, LibraryService
from semblon.desktop.widgets import EmptyState, ThumbGrid, folder_empty_state


class HomePage(QWidget):
    add_folder = Signal()
    open_unknown = Signal()
    open_recent = Signal(object)
    open_run = Signal(object)
    refresh_failed = Signal(str)
    _summary_ready = Signal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        self._refresh_seq = 0
        self._summary_ready.connect(self._on_summary_ready)
        lay = QVBoxLayout(self)
        self.welcome = QLabel("SEMBLON")
        self.welcome.setAccessibleName("Welcome")
        self.stats = QLabel("")
        self.stats.setWordWrap(True)
        self.stats.setAccessibleName("Library stats")
        self.recent = QListWidget()
        self.recent.setAccessibleName("Recent activity")
        self.recent.itemActivated.connect(self._open_recent_item)
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
        self._apply_summary(rec)

    def refresh_async(self, service: LibraryService) -> None:
        """Load the Home summary off the UI thread."""
        self._service = service
        self._refresh_seq += 1
        seq = self._refresh_seq
        self.stats.setText("Loading library summary…")
        self.btn_unknown.setEnabled(False)

        def worker() -> None:
            try:
                rec = service.home_summary()
                err = None
            except Exception as e:  # noqa: BLE001 - surface refresh failure via signal
                rec = None
                err = e
            self._summary_ready.emit(seq, rec, err)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_summary(self, rec: dict[str, Any]) -> None:
        if not bool(rec.get("available", True)):
            self.stats.setText("Store unavailable. Pick or create a Semblon store to continue.")
            self.recent.clear()
            self.empty.setVisible(True)
            self.btn_unknown.setEnabled(False)
            return
        n_photos = int(rec.get("photos") or 0)
        n_videos = int(rec.get("videos") or 0)
        n_people = int(rec.get("people") or 0)
        n_unknown = int(rec.get("unknown") or 0)
        self.stats.setText(
            f"{n_photos} photos · {n_videos} videos · "
            f"{n_people} named people · {n_unknown} unknown groups"
        )
        self.recent.clear()
        for row in rec.get("recent") or []:
            item = QListWidgetItem(str(row.get("label") or row.get("run_id") or ""))
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.recent.addItem(item)
        has_media = n_photos > 0 or n_videos > 0
        self.empty.setVisible(not has_media)
        self.btn_unknown.setEnabled(n_unknown > 0)

    def _on_summary_ready(self, seq: int, rec: object, err: object) -> None:
        if seq != self._refresh_seq:
            return
        if err is not None:
            self.stats.setText("Could not refresh Home summary.")
            self.refresh_failed.emit(str(err))
            return
        if isinstance(rec, dict):
            self._apply_summary(rec)

    def _open_recent_item(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(row, dict):
            self.open_recent.emit(row)
            self.open_run.emit(row)


class _MediaPage(QWidget):
    add_folder = Signal()
    inspect = Signal(object)

    def __init__(self, title: str, empty_title: str, empty_body: str, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.heading = QLabel(title)
        self.heading.setAccessibleName(title)
        self.stack = QStackedWidget()
        self.empty = folder_empty_state(self, empty_title, empty_body, on_add=self.add_folder.emit)
        self.grid = ThumbGrid()
        self.grid.inspect.connect(self.inspect.emit)
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.grid)
        lay.addWidget(self.heading)
        lay.addWidget(self.stack)
        self._layout = lay

    def _show_rows(self, rows: list[dict[str, Any]]) -> None:
        self.grid.set_items(rows)
        self.stack.setCurrentWidget(self.grid if rows else self.empty)

    def refresh_async(self, service: LibraryService) -> None:
        """Default async contract: cheap pages can refresh synchronously."""
        self.refresh(service)

    def _insert_above_stack(self, widget: QWidget) -> None:
        idx = self._layout.indexOf(self.stack)
        if idx < 0:
            self._layout.addWidget(widget)
            return
        self._layout.insertWidget(idx, widget)


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
        for key, label in PHOTO_SORT_LABELS.items():
            self.sort.addItem(label, key)
        self.sort.currentIndexChanged.connect(self._on_sort_changed)
        sort_row = QWidget(self)
        bar = QHBoxLayout(sort_row)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(QLabel("Sort"))
        bar.addWidget(self.sort)
        bar.addStretch(1)
        self._insert_above_stack(sort_row)

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
    open_unknown = Signal()
    refresh_failed = Signal(str)
    _rows_ready = Signal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        self._refresh_seq = 0
        self._rows_ready.connect(self._on_rows_ready)
        lay = QVBoxLayout(self)
        self.heading = QLabel("People")
        self.heading.setAccessibleName("People")
        self.empty = EmptyState(
            "No named people",
            "Open Unknown and Name a group. A cluster is not a person until Name.",
            action_label="Open unknown",
        )
        self.empty.action.connect(self.open_unknown.emit)
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
        self._apply_rows(rows)

    def refresh_async(self, service: LibraryService) -> None:
        self._service = service
        self._refresh_seq += 1
        seq = self._refresh_seq

        def worker() -> None:
            try:
                rows = service.list_people()
                err = None
            except Exception as e:  # noqa: BLE001
                rows = []
                err = e
            self._rows_ready.emit(seq, rows, err)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_rows(self, rows: list[dict[str, Any]]) -> None:
        self.grid.set_items(rows)
        self.stack.setCurrentWidget(self.grid if rows else self.empty)

    def _on_rows_ready(self, seq: int, rows: object, err: object) -> None:
        if seq != self._refresh_seq:
            return
        if err is not None:
            self.refresh_failed.emit(str(err))
        if isinstance(rows, list):
            self._apply_rows(rows)


class UnknownPage(QWidget):
    inspect = Signal(object)
    name = Signal(object)
    ignore = Signal(object)
    refresh_failed = Signal(str)
    _rows_ready = Signal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        self._refresh_seq = 0
        self._rows_ready.connect(self._on_rows_ready)
        lay = QVBoxLayout(self)
        self.heading = QLabel("Unknown")
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
        self.grid.currentItemChanged.connect(self._sync_buttons)
        self.btn_name.setEnabled(False)
        self.btn_ignore.setEnabled(False)
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
        self._apply_rows(rows)

    def refresh_async(self, service: LibraryService) -> None:
        self._service = service
        self._refresh_seq += 1
        seq = self._refresh_seq

        def worker() -> None:
            try:
                rows = service.list_unknown()
                err = None
            except Exception as e:  # noqa: BLE001
                rows = []
                err = e
            self._rows_ready.emit(seq, rows, err)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_rows(self, rows: object) -> None:
        if not isinstance(rows, list):
            raise TypeError("list_unknown must return list[dict]")
        self.grid.set_items(rows)
        self.stack.setCurrentWidget(self.grid if rows else self.empty)
        self._sync_buttons()

    def _on_rows_ready(self, seq: int, rows: object, err: object) -> None:
        if seq != self._refresh_seq:
            return
        if err is not None:
            self.refresh_failed.emit(str(err))
        self._apply_rows(rows)

    def _sync_buttons(self, *_args) -> None:
        enabled = self.grid.current_payload() is not None
        self.btn_name.setEnabled(enabled)
        self.btn_ignore.setEnabled(enabled)


class ActivityPage(QWidget):
    open_run = Signal(object)
    refresh_failed = Signal(str)
    _rows_ready = Signal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        self._refresh_seq = 0
        self._rows_ready.connect(self._on_rows_ready)
        lay = QVBoxLayout(self)
        self.heading = QLabel("Activity")
        self.heading.setAccessibleName("Activity")
        self.list = QListWidget()
        self.list.setAccessibleName("Activity list")
        self.list.itemActivated.connect(self._open_selected_run)
        self.empty = EmptyState("No activity", "Process a folder to record a run.")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.list)
        lay.addWidget(self.heading)
        lay.addWidget(self.stack)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        rows = service.list_activity()
        self._apply_rows(rows)

    def refresh_async(self, service: LibraryService) -> None:
        self._service = service
        self._refresh_seq += 1
        seq = self._refresh_seq

        def worker() -> None:
            try:
                rows = service.list_activity()
                err = None
            except Exception as e:  # noqa: BLE001
                rows = []
                err = e
            self._rows_ready.emit(seq, rows, err)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_rows(self, rows: list[dict[str, Any]]) -> None:
        self.list.clear()
        for row in rows:
            item = QListWidgetItem(str(row.get("label") or row.get("run_id") or ""))
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.list.addItem(item)
        self.stack.setCurrentWidget(self.list if rows else self.empty)

    def _on_rows_ready(self, seq: int, rows: object, err: object) -> None:
        if seq != self._refresh_seq:
            return
        if err is not None:
            self.refresh_failed.emit(str(err))
        if isinstance(rows, list):
            self._apply_rows(rows)

    def _open_selected_run(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(row, dict):
            self.open_run.emit(row)


class SettingsPage(QWidget):
    refresh_failed = Signal(str)
    _lines_ready = Signal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        self._refresh_seq = 0
        self._lines_ready.connect(self._on_lines_ready)
        lay = QVBoxLayout(self)
        self.heading = QLabel("Settings")
        self.heading.setAccessibleName("Settings")
        self.body = QLabel("")
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.body.setAccessibleName("Settings status")
        lay.addWidget(self.heading)
        lay.addWidget(self.body)
        lay.addStretch(1)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        lines = service.settings_lines()
        self._apply_lines(lines)

    def refresh_async(self, service: LibraryService) -> None:
        self._service = service
        self._refresh_seq += 1
        seq = self._refresh_seq
        self.body.setText("Loading settings…")

        def worker() -> None:
            try:
                lines = service.settings_lines()
                err = None
            except Exception as e:  # noqa: BLE001
                lines = []
                err = e
            self._lines_ready.emit(seq, lines, err)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_lines(self, lines: list[str]) -> None:
        self.body.setText("\n".join(lines))

    def _on_lines_ready(self, seq: int, lines: object, err: object) -> None:
        if seq != self._refresh_seq:
            return
        if err is not None:
            self.refresh_failed.emit(str(err))
        if isinstance(lines, list):
            self._apply_lines(lines)
