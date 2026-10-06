"""QML-facing session. Qt reports input. Application owns archive and jobs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from semblon.application import Application, JobBusy
from semblon.native_shell.model import ArchiveModel, SimilarStripModel


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
    resultChanged = Signal()
    similarChanged = Signal()

    def __init__(self, model: ArchiveModel, jobs: Application):
        super().__init__()
        self._jobs = jobs
        self._session = jobs.archive
        self._model = model
        self._job_active = False
        self._job_state = "idle"
        self._empty = self._jobs.archive_count() == 0
        self._reduced = reduced_motion()
        self._result_text = ""
        self._region_norm: tuple[float, float, float, float] | None = None
        self._similar = SimilarStripModel()
        self._similar_state = "idle"
        self._similar_note = ""
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
        item = self._jobs.media(self._session.focus_id or "")
        return item.source_type if item else ""

    @Property(str, notify=focusChanged)
    def focusName(self) -> str:
        item = self._jobs.media(self._session.focus_id or "")
        return item.name if item else ""

    @Property(str, notify=focusChanged)
    def focusUrl(self) -> str:
        item = self._jobs.media(self._session.focus_id or "")
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
        return self._jobs.archive_count()

    @Property(str, notify=resultChanged)
    def resultText(self) -> str:
        return self._result_text

    @Property(str, notify=similarChanged)
    def similarState(self) -> str:
        return self._similar_state

    @Property(str, notify=similarChanged)
    def similarNote(self) -> str:
        return self._similar_note

    @Property(int, notify=similarChanged)
    def similarCount(self) -> int:
        return self._similar.rowCount()

    @property
    def similar_model(self) -> SimilarStripModel:
        return self._similar

    def _set_result(self, text: str) -> None:
        self._result_text = text
        self.resultChanged.emit()

    def _clear_similar(self) -> None:
        self._similar.set_rows([])
        self._similar_state = "idle"
        self._similar_note = ""
        self.similarChanged.emit()

    def _publish_similar(self, state: str, note: str, rows: list[tuple[str, float]]) -> None:
        self._similar.set_rows(rows)
        self._similar_state = state
        self._similar_note = note
        self.similarChanged.emit()

    def _clear_query(self) -> None:
        self._region_norm = None
        self._set_result("")
        self._clear_similar()

    @Slot(str)
    def openFocus(self, media_id: str) -> None:
        self._session.open_focus(media_id)
        self._clear_query()
        self.focusChanged.emit()

    @Slot(int)
    def openIndex(self, index: int) -> None:
        rows = self._jobs.archive_window(index, 1)
        if not rows:
            return
        self._session.open_focus(rows[0].media_id)
        self._clear_query()
        self.focusChanged.emit()

    @Slot(float)
    def setScroll(self, y: float) -> None:
        if self._session.focus_id:
            return
        self._session.scroll = max(0.0, float(y))

    @Slot()
    def focusNext(self) -> None:
        self._session.move_focus(1)
        self._clear_query()
        self.focusChanged.emit()

    @Slot()
    def focusPrev(self) -> None:
        self._session.move_focus(-1)
        self._clear_query()
        self.focusChanged.emit()

    @Slot()
    def escape(self) -> None:
        self._session.escape()
        self._clear_query()
        self.focusChanged.emit()
        self.lensChanged.emit()

    @Slot()
    def wordmark(self) -> None:
        self._session.wordmark()
        self._clear_query()
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

    @Slot()
    def askPhoto(self) -> None:
        """Whole-frame Lens query for the open memory. Engine loads the file."""
        media_id = self._session.focus_id
        if not media_id:
            self._set_result("Open a photo first.\nNothing was searched.")
            return
        try:
            rec = self._jobs.query_media(media_id)
        except Exception as exc:  # noqa: BLE001 — show the failure, do not invent a match
            self._set_result(f"Semblon could not finish looking.\n{exc}")
            return
        lines = rec.get("lines") or [rec.get("reason") or "Nothing was searched."]
        self._set_result("\n".join(str(line) for line in lines))

    @Slot(float, float, float, float)
    def setRegion(self, nx: float, ny: float, nw: float, nh: float) -> None:
        """Normalized image-space rectangle from the focus view. Not a widget image."""
        self._region_norm = (
            max(0.0, min(1.0, float(nx))),
            max(0.0, min(1.0, float(ny))),
            max(0.0, min(1.0, float(nw))),
            max(0.0, min(1.0, float(nh))),
        )

    def _pixel_rect(self) -> tuple[int, int, int, int] | None:
        media_id = self._session.focus_id
        if not media_id or self._region_norm is None:
            return None
        item = self._jobs.media(media_id)
        if item is None:
            return None
        width = int(item.width or 0)
        height = int(item.height or 0)
        if width <= 0 or height <= 0:
            return None
        nx, ny, nw, nh = self._region_norm
        if nw <= 0 or nh <= 0:
            return None
        x = max(0, min(width - 1, int(round(nx * width))))
        y = max(0, min(height - 1, int(round(ny * height))))
        rw = max(1, int(round(nw * width)))
        rh = max(1, int(round(nh * height)))
        if x + rw > width:
            rw = width - x
        if y + rh > height:
            rh = height - y
        return x, y, rw, rh

    @Slot()
    def clearDrawnQuery(self) -> None:
        """Drop a drag that is not a query. Stale thumbnails must not survive it."""
        self._clear_query()

    @Slot(int, result=str)
    def similarId(self, row: int) -> str:
        return self._similar.media_id(int(row))

    @Slot(str, result=str)
    def thumbFor(self, media_id: str) -> str:
        if not media_id:
            return ""
        return f"image://archive/t/{media_id}"

    @Slot()
    def findSimilar(self) -> None:
        """Region search door for a drawn rect. The Focus strip calls this on release."""
        media_id = self._session.focus_id
        if not media_id:
            self._publish_similar("unavailable", "Open a photo first.", [])
            return
        rect = self._pixel_rect()
        if rect is None:
            self._publish_similar("unavailable", "Draw a region on the photo first.", [])
            return
        x, y, w, h = rect
        try:
            rec = self._jobs.remember_and_find_region(media_id, x, y, w, h)
        except Exception:  # noqa: BLE001 — honest failure, no invented matches
            self._set_result("")
            self._publish_similar("unavailable", "Similar search could not run.", [])
            return
        self._set_result("")
        self._publish_similar(*_strip_from(rec))

    @Slot()
    def pauseJob(self) -> None:
        self._jobs.pause_job()
        self._poll_job()

    @Slot()
    def cancelJob(self) -> None:
        self._jobs.cancel_job()
        self._poll_job()

    def path_for(self, media_id: str) -> str | None:
        return self._jobs.media_path(media_id)

    def _start_ingest(self, folder: Path) -> None:
        from semblon.home_ui import resolve_home_observers

        try:
            self._jobs.submit_ingest(
                folder,
                on_done=lambda _result: self.ingestFinished.emit(),
                open_review=False,
                observers=resolve_home_observers(),
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
        empty = self._jobs.archive_count() == 0
        self.libraryChanged.emit()
        if empty != self._empty:
            self._empty = empty
            self.emptyChanged.emit()


def _strip_from(rec: dict) -> tuple[str, str, list[tuple[str, float]]]:
    """Strip payload only. No provider, item id, or score text."""
    similar = rec.get("similar") or {}
    status = similar.get("status")
    items = list(similar.get("items") or [])
    if status == "SUCCESS" and items:
        rows: list[tuple[str, float]] = []
        for item in items[:8]:
            media_id = str(item.get("media_id") or "")
            if not media_id:
                continue
            try:
                score = float(item.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            rows.append((media_id, score))
        if rows:
            return "ready", "", rows
    if status == "UNAVAILABLE":
        return "unavailable", _unavailable_note(similar), []
    return "empty", "No similar images found yet.", []


def _unavailable_note(similar: dict) -> str:
    reason = str(similar.get("reason") or "")
    lowered = reason.lower()
    if "embedding" in lowered or "pack" in lowered or "space" in lowered:
        return "Similar search needs photos that have already been looked at."
    if reason and "sqlite" not in lowered and "traceback" not in lowered:
        return reason
    return "Similar search could not run."
