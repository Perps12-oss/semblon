"""QML-facing session. Qt reports input; ArchiveSession decides transitions."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from semblon.application import Application, JobBusy
from semblon.archive_session import ArchiveSession
from semblon.native_shell.model import ArchiveModel


def reduced_motion() -> bool:
    flag = os.environ.get("SEMBLON_REDUCE_MOTION", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        enabled = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
        return bool(ok) and enabled.value == 0
    except (AttributeError, OSError):
        return False


class ShellBridge(QObject):
    lensChanged = Signal()
    focusChanged = Signal()
    libraryChanged = Signal()
    jobChanged = Signal()
    emptyChanged = Signal()
    ingestFinished = Signal()

    def __init__(self, session: ArchiveSession, model: ArchiveModel, jobs: Application):
        super().__init__()
        self._session = session
        self._model = model
        self._jobs = jobs
        self._job_active = False
        self._job_state = "idle"
        self._empty = session.count() == 0
        self._reduced = reduced_motion()
        self.ingestFinished.connect(self._after_ingest)
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._poll_job)
        self._timer.start()
        model.reload()

    @Property(str, notify=lensChanged)
    def lensLabel(self) -> str:
        return self._session.lens.label

    @Property(str, notify=focusChanged)
    def focusId(self) -> str:
        return self._session.focus_id or ""

    @Property(str, notify=focusChanged)
    def focusKind(self) -> str:
        item = self._session.media(self._session.focus_id or "")
        return item.source_type if item else ""

    @Property(str, notify=focusChanged)
    def focusName(self) -> str:
        item = self._session.media(self._session.focus_id or "")
        return item.name if item else ""

    @Property(str, notify=focusChanged)
    def focusUrl(self) -> str:
        item = self._session.media(self._session.focus_id or "")
        if item is None or item.source_type != "video":
            return ""
        path = Path(item.path)
        if not path.is_file():
            return ""
        return QUrl.fromLocalFile(str(path)).toString()

    @Property(float, notify=focusChanged)
    def scrollY(self) -> float:
        return float(self._session.scroll)

    @Property(bool, notify=emptyChanged)
    def empty(self) -> bool:
        return self._empty

    @Property(bool, notify=jobChanged)
    def jobActive(self) -> bool:
        return self._job_active

    @Property(str, notify=jobChanged)
    def jobLabel(self) -> str:
        if not self._job_active:
            return ""
        if self._job_state == "paused":
            return "Paused"
        if self._job_state == "cancelling":
            return "Cancelling"
        return "Processing"

    @Property(bool, constant=True)
    def reducedMotion(self) -> bool:
        return self._reduced

    @Property(int, notify=libraryChanged)
    def count(self) -> int:
        return self._session.count()

    @Slot(str)
    def openFocus(self, media_id: str) -> None:
        self._session.open_focus(media_id)
        self.focusChanged.emit()

    @Slot(int)
    def openIndex(self, index: int) -> None:
        rows = self._session.window(index, 1)
        if not rows:
            return
        self._session.open_focus(rows[0].media_id)
        self.focusChanged.emit()

    @Slot(float)
    def setScroll(self, y: float) -> None:
        if self._session.focus_id:
            return
        self._session.scroll = max(0.0, float(y))

    @Slot()
    def focusNext(self) -> None:
        self._session.move_focus(1)
        self.focusChanged.emit()

    @Slot()
    def focusPrev(self) -> None:
        self._session.move_focus(-1)
        self.focusChanged.emit()

    @Slot()
    def escape(self) -> None:
        self._session.escape()
        self.focusChanged.emit()
        self.lensChanged.emit()

    @Slot()
    def wordmark(self) -> None:
        self._session.wordmark()
        self.focusChanged.emit()
        self.lensChanged.emit()

    @Slot(str)
    def submitCommand(self, text: str) -> None:
        """Command field hook. No lens is created until a real capability is wired."""
        del text

    @Slot()
    def addFolder(self) -> None:
        if self._jobs.busy:
            return
        folder = QFileDialog.getExistingDirectory(None, "Add a folder of photos")
        if not folder:
            return
        self._start_ingest(Path(folder))

    def path_for(self, media_id: str) -> str | None:
        item = self._session.media(media_id)
        if item is None:
            return None
        return item.path

    def _start_ingest(self, folder: Path) -> None:
        try:
            self._jobs.submit_ingest(
                folder,
                on_done=lambda _result: self.ingestFinished.emit(),
                open_review=False,
            )
        except JobBusy:
            return
        self._poll_job()

    def _after_ingest(self) -> None:
        self._refresh_library()
        self._poll_job()

    def _poll_job(self) -> None:
        active = self._session.job_active()
        state = self._session.job_state()
        if active != self._job_active or state != self._job_state:
            was = self._job_active
            self._job_active = active
            self._job_state = state
            self.jobChanged.emit()
            if was and not active:
                self._refresh_library()

    def _refresh_library(self) -> None:
        self._model.reload()
        empty = self._session.count() == 0
        self.libraryChanged.emit()
        if empty != self._empty:
            self._empty = empty
            self.emptyChanged.emit()
