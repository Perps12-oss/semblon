"""Workspace page layer. Each page is a QWidget. The shell owns navigation.

Pages build UI in ``__init__``, expose ``refresh(service)``, and emit user
actions. Mutations stay in review.py. No FaceKit.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
        self.btn_unknown = QPushButton("Open Review")
        self.btn_unknown.setAccessibleName("Open Review")
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
    merge = Signal(object)
    note = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service: LibraryService | None = None
        lay = QVBoxLayout(self)
        self.heading = QLabel("Review")
        self.heading.setObjectName("title")
        self.heading.setAccessibleName("Review")
        blurb = QLabel("Unknown groups in this window. A cluster is not a person until Name.")
        blurb.setObjectName("subtitle")
        blurb.setWordWrap(True)
        self.empty = EmptyState(
            "Nothing to review",
            "Unknown is valid. Process a folder, then Name groups you know.",
        )
        self.grid = ThumbGrid()
        self.grid.setSelectionMode(self.grid.SelectionMode.ExtendedSelection)
        self.grid.set_context_actions(
            [
                ("inspect", "Inspect"),
                ("name", "Name"),
                ("ignore", "Ignore"),
                ("note", "Note"),
            ]
        )
        self.grid.inspect.connect(self.inspect.emit)
        self.grid.context_action.connect(self._on_context)
        bar = QHBoxLayout()
        self.btn_name = QPushButton("Name")
        self.btn_name.setObjectName("primary")
        self.btn_name.setAccessibleName("Name unknown group")
        self.btn_ignore = QPushButton("Ignore")
        self.btn_ignore.setAccessibleName("Ignore unknown group")
        self.btn_merge = QPushButton("Merge")
        self.btn_merge.setAccessibleName("Merge selected groups")
        self.btn_note = QPushButton("Note")
        self.btn_note.setAccessibleName("Note unknown group")
        self.btn_name.clicked.connect(self._emit_name)
        self.btn_ignore.clicked.connect(self._emit_ignore)
        self.btn_merge.clicked.connect(self._emit_merge)
        self.btn_note.clicked.connect(self._emit_note)
        bar.addWidget(self.btn_name)
        bar.addWidget(self.btn_ignore)
        bar.addWidget(self.btn_merge)
        bar.addWidget(self.btn_note)
        bar.addStretch(1)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.grid)
        lay.addWidget(self.heading)
        lay.addWidget(blurb)
        lay.addLayout(bar)
        lay.addWidget(self.stack)

    def _on_context(self, key: str, payload: object) -> None:
        if key == "name":
            self.name.emit(payload)
        elif key == "ignore":
            self.ignore.emit(payload)
        elif key == "note":
            self.note.emit(payload)

    def _emit_name(self) -> None:
        payload = self.grid.current_payload()
        if payload is not None:
            self.name.emit(payload)

    def _emit_ignore(self) -> None:
        payload = self.grid.current_payload()
        if payload is not None:
            self.ignore.emit(payload)

    def _emit_note(self) -> None:
        payload = self.grid.current_payload()
        if payload is not None:
            self.note.emit(payload)

    def _emit_merge(self) -> None:
        payloads = self.grid.selected_payloads()
        ids = [p.get("cluster_id") for p in payloads if p.get("kind") == "cluster" and p.get("cluster_id")]
        if len(ids) >= 2:
            self.merge.emit(ids)

    def refresh(self, service: LibraryService) -> None:
        self._service = service
        rows = service.list_unknown()
        self.grid.set_items(rows)
        self.stack.setCurrentWidget(self.grid if rows else self.empty)
        enabled = bool(rows)
        self.btn_name.setEnabled(enabled)
        self.btn_ignore.setEnabled(enabled)
        self.btn_note.setEnabled(enabled)
        self.btn_merge.setEnabled(enabled)


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


class LivePage(QWidget):
    """Webcam/RTSP product surface. Shows per-face overlays. Track ≠ Person."""

    start_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_overlays: list[dict] = []
        lay = QVBoxLayout(self)
        self.heading = QLabel("Live")
        self.heading.setObjectName("title")
        self.heading.setAccessibleName("Live")
        blurb = QLabel(
            "Camera or RTSP → detect → track → identify evidence. "
            "Track ≠ Person. UNKNOWN is valid. Live never creates a Person."
        )
        blurb.setObjectName("subtitle")
        blurb.setWordWrap(True)
        row = QHBoxLayout()
        self.source = QLineEdit("0")
        self.source.setPlaceholderText("Camera index or RTSP URL")
        self.source.setAccessibleName("Live source")
        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("primary")
        self.btn_start.setAccessibleName("Start live")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setAccessibleName("Stop live")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._emit_start)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        row.addWidget(QLabel("Source"))
        row.addWidget(self.source, 1)
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        self.viewport = QLabel()
        self.viewport.setObjectName("liveViewport")
        self.viewport.setMinimumHeight(320)
        self.viewport.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewport.setText("Live is idle.")
        self.viewport.setAccessibleName("Live viewport")
        self.status = QLabel("Idle · track ≠ person")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Live status")
        lay.addWidget(self.heading)
        lay.addWidget(blurb)
        lay.addLayout(row)
        lay.addWidget(self.viewport, 1)
        lay.addWidget(self.status)

    def _emit_start(self) -> None:
        self.start_requested.emit(self.source.text().strip() or "0")

    def set_running(self, running: bool) -> None:
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.source.setEnabled(not running)
        if not running and not self._last_overlays:
            self.viewport.setText("Live is idle.")

    def clear_overlays(self) -> None:
        self._last_overlays = []
        self.viewport.setPixmap(QPixmap())
        self.viewport.setText("Live is idle.")
        self.status.setText("Idle · track ≠ person")

    def apply_frame(self, snapshot: dict) -> None:
        """Paint preview (if any) and independent boxes from runtime overlays."""
        overlays = list(snapshot.get("overlays") or [])
        self._last_overlays = overlays
        counts = snapshot.get("counts") or {}
        parts = [
            f"frame {snapshot.get('frame_index') or 0}",
            f"faces {counts.get('detected', len(overlays))}",
            f"tracks {counts.get('tracks', 0)}",
            "UNKNOWN valid",
            "track ≠ person",
        ]
        self.status.setText(" · ".join(str(p) for p in parts))
        preview = snapshot.get("preview_bgr")
        pix = None
        if preview is not None:
            try:
                import numpy as np

                arr = np.asarray(preview)
                if arr.ndim == 3 and arr.shape[2] == 3:
                    h, w, _ = arr.shape
                    rgb = arr[:, :, ::-1].copy()
                    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
                    pix = QPixmap.fromImage(qimg)
            except Exception:
                pix = None
        if pix is None or pix.isNull():
            # Synthetic canvas so overlays remain visible without a camera frame.
            w = h = 480
            pix = QPixmap(w, h)
            pix.fill(QColor("#1a1d21"))
        else:
            w = pix.width()
            h = pix.height()
        painter = QPainter(pix)
        try:
            for ov in overlays:
                bbox = ov.get("bbox") or (0, 0, 0, 0)
                x1, y1, x2, y2 = [int(round(float(v))) for v in bbox]
                label = str(ov.get("label") or "UNKNOWN")
                track = str(ov.get("track_id") or "?")
                pen = QPen(QColor("#7dd3a0" if label != "UNKNOWN" else "#e2b15c"))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))
                painter.drawText(x1 + 4, max(14, y1 - 6), f"{label}  Track {track}")
        finally:
            painter.end()
        scaled = pix.scaled(
            self.viewport.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.viewport.setPixmap(scaled)

    def refresh(self, service: LibraryService) -> None:  # noqa: ARG002 — shell contract
        return
