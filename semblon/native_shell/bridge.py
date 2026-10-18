"""QML-facing session. Qt reports input. Application owns archive and jobs."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEventLoop,
    QMetaObject,
    QObject,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from semblon.atmosphere import ATMOSPHERE_LABELS, ATMOSPHERE_IDS
from semblon.application import Application, JobBusy
from semblon.focus_gesture import adjust_box, clamp_view, zoom_about
from semblon.native_shell.adapter import AdapterError, ArchiveAdapter, Result
from semblon.native_shell.events import (
    IDENTITY_CHANGED,
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_PAUSED,
    JOB_PROGRESS,
    JOB_STARTED,
    LIBRARY_CHANGED,
    ShellEvents,
)
from semblon.native_shell.model import ArchiveModel, PeopleModel, SimilarStripModel
from semblon.native_shell.tokens import cell_size, tokens_for
from semblon.native_shell.presentation import (
    ADVANCED,
    PRIMARY,
    decision_success,
    normalize_mode,
    present_message,
    summarize_people_results,
)
from semblon.native_shell.editorial import (
    SAVED_VIEWS_NOTE,
    SPATIAL_NOTE,
    VIDEO_NOTE,
    YEAR_NOTE,
    MEDIA_KINDS,
    calendar_month_cells,
    default_calendar_month,
    field_sections,
    format_count,
    format_count_exact,
    month_end_day,
    month_heading,
    range_media_ids,
    rows_from_scope,
    scope_ids,
    shift_month,
    sort_ids_newest_first,
    source_counts,
    timeline_density,
)
from semblon.ui_prefs import load_prefer_gpu, load_prefs, save_theme_mode, update_prefs


KEY_SHELL_MODE = "shell_mode"


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


class _VisualSearchThread(QThread):
    """Region and similar lookups off the UI thread. The slot applies the result."""

    succeeded = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, generation: int, fn, parent=None):
        super().__init__(parent)
        self._generation = generation
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._generation, self._fn())
        except Exception as exc:  # noqa: BLE001 — the UI slot turns this into search failed
            self.failed.emit(self._generation, str(exc) or "search failed")


class ShellBridge(QObject):
    lensChanged = Signal()
    focusChanged = Signal()
    diagnosticsChanged = Signal()
    libraryChanged = Signal()
    jobChanged = Signal()
    emptyChanged = Signal()
    ingestFinished = Signal()
    resultChanged = Signal()
    similarChanged = Signal()
    selectionChanged = Signal()
    searchBusyChanged = Signal()
    indexChanged = Signal()
    keepsChanged = Signal()
    peopleChanged = Signal()
    surfaceChanged = Signal()
    editorialChanged = Signal()

    def __init__(self, model: ArchiveModel, jobs: Application):
        super().__init__()
        self._jobs = jobs
        self._session = jobs.archive
        self._model = model
        self._job_active = False
        self._job_state = "idle"
        self._last_folder: Path | None = None
        self._resume_ready = False
        self._cancel_requested = False
        self._empty = self._jobs.archive_count() == 0
        self._stage = "home"
        self._reduced = reduced_motion()
        self._result_text = ""
        self._region_norm: tuple[float, float, float, float] | None = None
        self._similar = SimilarStripModel()
        self._similar_state = "idle"
        self._similar_note = ""
        self._similar_basis = ""
        self._similar_basis_label = ""
        self._selection_note = ""
        self._selection_kind = ""
        self._similar_cancel = False
        self._search_generation = 0
        self._search_busy = False
        self._search_thread: _VisualSearchThread | None = None
        self._cancel_flag: list[bool] | None = None
        self._search_failure = ""
        self._index_state = ""
        self._index_note = ""
        self._progress_seen: int | None = None
        self._progress_current = 0
        self._progress_total = 0
        self._discovery_trail: list[dict] = []
        self._query_focus_id = ""
        self._point_source = ""
        self._people = PeopleModel()
        self._people_open = False
        self._people_note = ""
        self._selected_subject = ""
        self._evidence_id = ""
        self._merge_target_subject = ""
        self._split_faces: list[str] = []
        self._person_days: list[dict] = []
        self._focus_boxes: list[dict] = []
        self._selected_observation = ""
        self._activity_rows: list[dict] = []
        self._activity_open = False
        self._mode = self._load_shell_mode()
        self._atmosphere_id = self._load_atmosphere_id()
        self._adapter = ArchiveAdapter(jobs)
        self._events = ShellEvents()
        self._buckets: list[dict] = []
        self._facet = "memory"
        self._settings_open = False
        self._named_items_open = False
        self._named_items: list[dict] = []
        self._named_item_id = ""
        self._surface_state = "empty" if self._empty else "ready"
        self._notice = ""
        self._progress_label = ""
        self._last_job_failed = False
        self._terminal_status = ""
        self._review_text = ""
        self._unresolved_text = ""
        self._photo_count = 0
        self._video_count = 0
        self._years: list[dict] = []
        self._days: list[dict] = []
        self._folders: list[dict] = []
        self._timeline_density: list[dict] = []
        self._timeline_loading = False
        self._sticky_heading = ""
        self._calendar_month = ""
        self._calendar_cells: list[dict] = []
        self._field_sections: list[dict] = []
        self._scope_ids: dict[str, dict[str, list[str]]] = {
            "year": {},
            "month": {},
            "day": {},
            "folder": {},
            "range": {},
            "everything": {"": []},
        }
        self._media_kind = "all"
        self._scope_kind = ""
        self._scope_label = ""
        self._person_field_filter = False
        self._person_field_ids: list[str] = []
        self._person_field_label = ""
        self.ingestFinished.connect(self._after_ingest)
        self.focusChanged.connect(self._refresh_index_note)
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._poll_job)
        self._timer.start()
        model.reload()
        self._reload_editorial()
        QTimer.singleShot(0, self._sync_windows_caption)

    def _sync_windows_caption(self) -> None:
        """Match the native Windows caption to the shell background when supported."""
        try:
            from semblon.native_shell.windows_caption import apply_dark_caption
        except Exception:  # noqa: BLE001 — caption is cosmetic
            return
        tokens = tokens_for(self._atmosphere_id)
        apply_dark_caption(tokens.get("bg0", "#0a0b10"), tokens.get("text1", "#f2f3f5"))

    def shutdown(self) -> None:
        if self._cancel_flag is not None:
            self._cancel_flag[0] = True
        self._search_generation += 1
        thread = self._search_thread
        if thread is not None and thread.isRunning():
            thread.wait(2000)
        jobs = getattr(self, "_jobs", None)
        engine = getattr(jobs, "engine", None) if jobs is not None else None
        if engine is not None and hasattr(engine, "shutdown"):
            engine.shutdown()
        timer = getattr(self, "_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:  # pragma: no cover - Qt teardown guard
                pass
            try:
                self._timer.timeout.disconnect(self._poll_job)
            except Exception:  # pragma: no cover - Qt disconnect guard
                pass
            try:
                self._timer.deleteLater()
            except Exception:  # pragma: no cover - Qt teardown guard
                pass
            self._timer = None

    def _prefs_store(self) -> Path:
        return self._jobs.store

    def _load_shell_mode(self) -> str:
        prefs = load_prefs(self._prefs_store())
        return normalize_mode(prefs.get(KEY_SHELL_MODE))

    def _save_shell_mode(self, mode: str) -> None:
        update_prefs(self._prefs_store(), **{KEY_SHELL_MODE: normalize_mode(mode)})

    def _load_atmosphere_id(self) -> str:
        prefs = load_prefs(self._prefs_store())
        chosen = str(prefs.get("theme") or "").strip().lower()
        if chosen in ATMOSPHERE_IDS:
            return chosen
        return "mica_dark"

    @Property(str, notify=lensChanged)
    def mode(self) -> str:
        return self._mode

    @Property(bool, notify=lensChanged)
    def primaryMode(self) -> bool:
        return self._mode == PRIMARY

    @Property(bool, notify=lensChanged)
    def advancedMode(self) -> bool:
        return self._mode == ADVANCED

    @Property(str, notify=lensChanged)
    def modeLabel(self) -> str:
        return "Primary" if self._mode == PRIMARY else "Advanced"

    @Property(str, notify=lensChanged)
    def modeHint(self) -> str:
        if self._mode == PRIMARY:
            return "Simple product language"
        return "Diagnostics and technical detail"

    @Property(str, notify=diagnosticsChanged)
    def diagnosticsText(self) -> str:
        if self._mode != ADVANCED:
            return ""
        focus = self._session.focus_id or "(none)"
        last = self._events.last()
        event_name = last["name"] if last else "(none)"
        return "\n".join(
            [
                f"mode={self._mode}",
                f"focus_id={focus}",
                f"job_state={self._job_state}",
                f"similar_state={self._similar_state}",
                f"selected_subject={self._selected_subject or '(none)'}",
                f"facet={self._facet}",
                f"surface={self._surface_state}",
                f"last_event={event_name}",
            ]
        )

    @Property(str, notify=lensChanged)
    def atmosphereId(self) -> str:
        return self._atmosphere_id

    @Property("QVariantList", notify=lensChanged)
    def atmosphereChoices(self):
        rows = []
        for atmosphere_id in ATMOSPHERE_IDS:
            rows.append({
                "id": atmosphere_id,
                "label": ATMOSPHERE_LABELS.get(atmosphere_id, atmosphere_id),
            })
        return rows

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

    @Property("QVariantList", notify=focusChanged)
    def focusObservationBoxes(self):
        return list(self._focus_boxes)

    @Property(str, notify=focusChanged)
    def selectedObservationId(self) -> str:
        return self._selected_observation

    @Slot(str)
    def selectObservation(self, observation_id: str) -> None:
        wanted = str(observation_id or "").strip()
        if not wanted:
            self._selected_observation = ""
            self.focusChanged.emit()
            return
        for box in self._focus_boxes:
            if str(box.get("id") or "") == wanted:
                self._selected_observation = wanted
                kind = str(box.get("kind") or "")
                self.focusChanged.emit()
                if kind == "face":
                    self._selection_kind = "face"
                    self._selection_note = ""
                    self.findSimilarFaces(wanted)
                    return
                if kind in {"object", "text", "clip", "appearance"}:
                    from semblon.selection import click_adopts_box

                    if not click_adopts_box(kind, str(box.get("source") or "")):
                        return
                    self.setRegion(
                        float(box.get("nx") or 0),
                        float(box.get("ny") or 0),
                        float(box.get("nw") or 0),
                        float(box.get("nh") or 0),
                    )
                    self._selection_kind = "text" if kind == "text" else "object"
                    self._selection_note = (
                        "Text in the selection."
                        if kind == "text"
                        else "Selected region."
                    )
                    self.similarChanged.emit()
                    self.findSimilar()
                return

    @Property(float, notify=focusChanged)
    def scrollY(self) -> float:
        return float(self._session.scroll)

    @Property(bool, notify=emptyChanged)
    def empty(self) -> bool:
        return self._empty

    @Property(str, notify=surfaceChanged)
    def stage(self) -> str:
        """Product stage: home launchpad or library field."""
        return self._stage

    @Property(bool, notify=surfaceChanged)
    def homeOpen(self) -> bool:
        return self._stage == "home"

    @Property(str, notify=libraryChanged)
    def archiveSummary(self) -> str:
        """One-line library status for the Home state band."""
        photos = int(self._photo_count or 0)
        total = int(self._jobs.archive_count())
        if total <= 0 and photos <= 0:
            return ""
        count = photos if photos > 0 else total
        noun = "photo" if count == 1 else "photos"
        return f"{count} {noun}. Originals stay where they are."

    @Property(str, notify=surfaceChanged)
    def searchModeShort(self) -> str:
        mode = str(self._adapter.search_mode().data.get("mode") or "people")
        return {
            "people": "Names",
            "text": "Text in photos",
            "object": "Objects",
            "whole": "Whole photo",
            "region": "Region",
        }.get(mode, "Names")

    @Property(bool, notify=jobChanged)
    def jobActive(self) -> bool:
        return self._job_active

    @Property(str, notify=jobChanged)
    def jobState(self) -> str:
        return self._job_state

    @Property(bool, notify=jobChanged)
    def canResume(self) -> bool:
        return self._resume_ready and self._last_folder is not None and not self._jobs.busy

    @Property(str, notify=jobChanged)
    def jobLabel(self) -> str:
        if self._last_job_failed and not self._job_active:
            return "Last add failed"
        if not self._job_active:
            return ""
        if self._job_state == "paused":
            return "Paused"
        if self._job_state == "cancelling":
            return "Cancelling"
        return self._progress_label or "Processing"

    @Property(int, notify=jobChanged)
    def jobCurrent(self) -> int:
        return int(self._progress_current)

    @Property(int, notify=jobChanged)
    def jobTotal(self) -> int:
        return int(self._progress_total)

    @Property(bool, constant=True)
    def reducedMotion(self) -> bool:
        return self._reduced

    @Property(str, notify=surfaceChanged)
    def surfaceState(self) -> str:
        return self._surface_state

    @Property(str, notify=surfaceChanged)
    def noticeText(self) -> str:
        return self._notice

    @Property(int, notify=editorialChanged)
    def photoCount(self) -> int:
        return self._photo_count

    @Property(int, notify=editorialChanged)
    def videoCount(self) -> int:
        return self._video_count

    @Property("QVariantList", notify=editorialChanged)
    def yearRows(self):
        return list(self._years)

    @Property("QVariantList", notify=editorialChanged)
    def dayRows(self):
        rows = list(self._days)
        prefix = ""
        if self._scope_kind == "year":
            prefix = self._scope_label
        elif self._scope_kind == "month":
            prefix = self._scope_label
        elif self._scope_kind == "range" and ":" in self._scope_label:
            prefix = self._scope_label.split(":", 1)[0][:4]
        elif self._scope_kind == "day" and len(self._scope_label) >= 4 and self._scope_label[:4].isdigit():
            prefix = self._scope_label[:4]
        if prefix:
            rows = [row for row in rows if str(row.get("label") or "").startswith(prefix)]
        return rows

    @Property("QVariantList", notify=editorialChanged)
    def folderRows(self):
        return list(self._folders)

    @Property("QVariantList", notify=editorialChanged)
    def timelineDensity(self):
        return list(self._timeline_density)

    @Property(bool, notify=editorialChanged)
    def timelineLoading(self) -> bool:
        return self._timeline_loading

    @Property(str, notify=editorialChanged)
    def stickyHeading(self) -> str:
        return self._sticky_heading

    @Property(bool, notify=editorialChanged)
    def timeScopeActive(self) -> bool:
        return self._scope_kind in ("year", "month", "day", "range")

    @Property(str, notify=editorialChanged)
    def calendarMonth(self) -> str:
        return self._calendar_month

    @Property(str, notify=editorialChanged)
    def calendarTitle(self) -> str:
        return month_heading(self._calendar_month + "-01") if self._calendar_month else ""

    @Property("QVariantList", notify=editorialChanged)
    def calendarCells(self):
        return list(self._calendar_cells)

    @Property("QVariantList", notify=editorialChanged)
    def fieldSections(self):
        return list(self._field_sections)

    @Property(bool, notify=editorialChanged)
    def fieldSectionsActive(self) -> bool:
        return bool(self._field_sections)

    @Property(str, notify=editorialChanged)
    def savedViewsNote(self) -> str:
        return SAVED_VIEWS_NOTE

    @Property(str, notify=editorialChanged)
    def spatialNote(self) -> str:
        return SPATIAL_NOTE

    @Property(str, notify=editorialChanged)
    def videoNote(self) -> str:
        return VIDEO_NOTE

    @Property(str, notify=editorialChanged)
    def yearNote(self) -> str:
        return YEAR_NOTE

    def _reload_editorial(self) -> None:
        store = self._jobs.store
        self._timeline_loading = True
        self.editorialChanged.emit()
        counts = source_counts(store)
        self._photo_count = int(counts.get("folder") or 0)
        self._video_count = int(counts.get("video") or 0)
        previous_range = None
        if self._scope_kind == "range" and ":" in self._scope_label:
            previous_range = self._scope_label
        self._scope_ids = scope_ids(store, self._media_kind)
        if previous_range:
            start, end = previous_range.split(":", 1)
            ids = range_media_ids(self._scope_ids.get("day", {}), start, end)
            self._scope_ids.setdefault("range", {})[previous_range] = ids
        self._years = rows_from_scope(self._scope_ids["year"], newest_first=True)
        self._days = rows_from_scope(self._scope_ids["day"], newest_first=True)
        self._folders = rows_from_scope(self._scope_ids["folder"])
        self._timeline_density = timeline_density(store, self._media_kind)
        if self._scope_kind and self._scope_label not in self._scope_ids.get(self._scope_kind, {}):
            self._scope_kind = ""
            self._scope_label = ""
        day_map = self._scope_ids.get("day", {})
        if not self._calendar_month:
            self._calendar_month = default_calendar_month(day_map)
        self._calendar_cells = calendar_month_cells(self._calendar_month, day_map)
        self._apply_scope_view()
        self._timeline_loading = False
        self.editorialChanged.emit()

    def _sync_calendar_month(self, month_label: str, *, rebuild: bool = True) -> None:
        label = str(month_label or "").strip()[:7]
        if len(label) < 7:
            return
        if label == self._calendar_month and not rebuild:
            return
        self._calendar_month = label
        if rebuild:
            self._calendar_cells = calendar_month_cells(
                self._calendar_month, self._scope_ids.get("day", {})
            )
        self.editorialChanged.emit()

    def _ordered_ids(self, ids: list[str]) -> list[str]:
        return sort_ids_newest_first(self._scope_ids.get("day", {}), list(ids))

    def _refresh_field_sections(self, ordered_ids: list[str] | None) -> None:
        """Day-grouped Field rows for year/month/range only."""
        if self._scope_kind in ("year", "month", "range") and ordered_ids:
            self._field_sections = field_sections(
                self._scope_ids.get("day", {}), list(ordered_ids)
            )
        else:
            self._field_sections = []

    def _apply_scope_view(self) -> None:
        """Point the grid at the current scope, narrowed by the photo/video choice."""
        day_map = self._scope_ids.get("day", {})
        ordered: list[str] | None = None
        # Explicit person-scoped Field (user opt-in). Day neighbours stay archive-wide
        # unless this filter is on — see showSelectedPersonOnly / clearPersonFieldFilter.
        if self._person_field_filter and self._person_field_ids:
            if self._scope_kind == "day":
                day_ids = set(self._scope_ids.get("day", {}).get(self._scope_label, []))
                ids = [m for m in self._person_field_ids if m in day_ids]
            else:
                ids = list(self._person_field_ids)
            ordered = self._ordered_ids(ids)
            self._model.set_media_ids(ordered)
        elif self._scope_kind:
            ids = list(self._scope_ids[self._scope_kind][self._scope_label])
            ordered = self._ordered_ids(ids)
            self._model.set_media_ids(ordered)
        elif self._media_kind != "all" or self._video_count:
            ordered = self._ordered_ids(list(self._scope_ids["everything"][""]))
            self._model.set_media_ids(ordered)
        else:
            # Still newest-first when the full archive is shown via explicit ids.
            everything = list(self._scope_ids.get("everything", {}).get("", []))
            if everything:
                ordered = self._ordered_ids(everything)
                self._model.set_media_ids(ordered)
            else:
                self._model.set_media_ids(None)
        self._refresh_field_sections(ordered)
        self._sticky_heading = ""

    @Property(str, notify=editorialChanged)
    def mediaKind(self) -> str:
        return self._media_kind

    @Slot(str)
    def setMediaKind(self, kind: str) -> None:
        kind = str(kind or "").strip().lower()
        if kind not in MEDIA_KINDS or kind == self._media_kind:
            return
        self._media_kind = kind
        self._facet = "memory"
        self._buckets = []
        self._reload_editorial()
        label = {"all": "everything", "photo": "photos", "video": "videos"}[kind]
        self._apply_result(Result("ready", f"Showing {label}."))

    @Property(str, notify=editorialChanged)
    def scopeLabel(self) -> str:
        return self._scope_label

    @Property(str, notify=editorialChanged)
    def scopeKind(self) -> str:
        return self._scope_kind

    def _select_scope(self, kind: str, label: str) -> None:
        ids = self._scope_ids.get(kind, {}).get(str(label or ""))
        if ids is None:
            return
        self._scope_kind = kind
        self._scope_label = str(label)
        self._facet = "memory"
        self._buckets = []
        ordered = self._ordered_ids(list(ids))
        self._model.set_media_ids(ordered)
        self._refresh_field_sections(ordered)
        self._sticky_heading = ""
        self.editorialChanged.emit()
        self._apply_result(Result("ready", f"Showing {label}."))

    def _newest_month_in_year(self, year: str) -> str:
        months = [
            m
            for m in self._scope_ids.get("month", {})
            if str(m).startswith(f"{year}-")
        ]
        if months:
            return max(months)
        return f"{year}-01"

    @Slot(str)
    def selectYear(self, label: str) -> None:
        year = str(label or "").strip()[:4]
        if year.isdigit():
            self._sync_calendar_month(self._newest_month_in_year(year))
        self._select_scope("year", year)

    @Slot(str)
    def selectMonth(self, label: str) -> None:
        month = str(label or "").strip()[:7]
        self._sync_calendar_month(month)
        self._select_scope("month", month)

    @Slot(str)
    def selectFolder(self, label: str) -> None:
        self._select_scope("folder", label)

    @Slot(str)
    def selectDay(self, label: str) -> None:
        day = str(label or "").strip()[:10]
        if (
            self._scope_kind == "day"
            and self._scope_label == day
        ):
            self.clearScope()
            return
        if len(day) >= 7:
            self._sync_calendar_month(day[:7])
        self._select_scope("day", day)

    @Slot(str, str)
    def selectRange(self, start: str, end: str) -> None:
        ids = range_media_ids(self._scope_ids.get("day", {}), start, end)
        a = str(start or "").strip()[:10]
        b = str(end or "").strip()[:10]
        if a > b:
            a, b = b, a
        key = f"{a}:{b}"
        self._scope_ids.setdefault("range", {})[key] = ids
        if len(a) >= 7:
            self._sync_calendar_month(a[:7])
        self._select_scope("range", key)

    @Slot()
    def calendarPrevMonth(self) -> None:
        """Browse previous month without changing the media scope."""
        self._sync_calendar_month(shift_month(self._calendar_month, -1))

    @Slot()
    def calendarNextMonth(self) -> None:
        """Browse next month without changing the media scope."""
        self._sync_calendar_month(shift_month(self._calendar_month, 1))

    @Slot(str)
    def setCalendarMonth(self, label: str) -> None:
        """Browse a month without changing the media scope."""
        self._sync_calendar_month(str(label or "").strip()[:7])

    @Slot()
    def calendarGoHome(self) -> None:
        """Jump the displayed calendar to the newest month with media (or today)."""
        self._sync_calendar_month(default_calendar_month(self._scope_ids.get("day", {})))

    @Slot(str, result=str)
    def monthEndDay(self, month_label: str) -> str:
        return month_end_day(str(month_label or ""))

    @Slot(int, result=str)
    def formatCount(self, value: int) -> str:
        return format_count(value)

    @Slot(int, result=str)
    def formatCountExact(self, value: int) -> str:
        return format_count_exact(value)

    @Property(bool, notify=surfaceChanged)
    def similarActionReady(self) -> bool:
        return bool(self._session.focus_id)

    @Property(str, notify=surfaceChanged)
    def similarActionHint(self) -> str:
        if self._session.focus_id:
            return "Find visually similar memories from the open photo."
        return "Open a photo first, then find similar memories."

    @Slot(str, result="QVariantList")
    def timelinePreviewIds(self, label: str):
        """Up to three media ids for a year, month, or day label (hover popover)."""
        text = str(label or "").strip()
        if not text:
            return []
        if len(text) == 4 and text.isdigit():
            ids = self._scope_ids.get("year", {}).get(text, [])
        elif len(text) == 7 and text[4:5] == "-":
            ids = self._scope_ids.get("month", {}).get(text, [])
        else:
            ids = self._scope_ids.get("day", {}).get(text, [])
        return list(ids[:3])

    @Slot(str)
    def setStickyDay(self, day: str) -> None:
        heading = month_heading(str(day or ""))
        if heading == self._sticky_heading:
            return
        self._sticky_heading = heading
        self.editorialChanged.emit()

    @Slot(int, result=str)
    def dayAt(self, index: int) -> str:
        """Day key for a Field row (sticky header)."""
        idx = self._model.index(int(index), 0)
        if not idx.isValid():
            return ""
        role = int(Qt.ItemDataRole.UserRole) + 3
        value = self._model.data(idx, role)
        return str(value or "")

    def _library_root_message(self) -> str:
        if self._media_kind == "photo":
            return "Showing photos."
        if self._media_kind == "video":
            return "Showing videos."
        return "Showing everything."

    def _reset_library_scope(self) -> None:
        """Clear year, day, folder, and moment buckets. Keep the photo/video choice."""
        self._scope_kind = ""
        self._scope_label = ""
        self._facet = "memory"
        self._buckets = []
        self._person_field_filter = False
        self._person_field_ids = []
        self._person_field_label = ""
        self._apply_scope_view()
        self.editorialChanged.emit()
        self._apply_result(Result("ready", self._library_root_message()))

    def _active_field_media_ids(self) -> list[str] | None:
        """Media ids for the current Field scope, or None for archive-wide search."""
        if self._person_field_filter and self._person_field_ids:
            return list(self._person_field_ids)
        if self._scope_kind and self._scope_label:
            ids = self._scope_ids.get(self._scope_kind, {}).get(self._scope_label)
            if ids:
                return list(ids)
        current = self._model.media_ids()
        if current is not None:
            return list(current)
        return None

    def _apply_discovery_search(self, result: Result) -> None:
        """Apply text/object search hits to Field with an honest basis note."""
        media_ids = [str(m) for m in (result.data.get("media_ids") or []) if m]
        basis = str(result.data.get("basis") or "")
        basis_label = str(result.data.get("basis_label") or "")
        if result.state == "ready" and media_ids:
            self._person_field_filter = False
            self._person_field_ids = []
            self._person_field_label = ""
            self._scope_kind = ""
            self._scope_label = ""
            self._facet = "memory"
            self._buckets = []
            ordered = self._ordered_ids(media_ids)
            self._model.set_media_ids(ordered)
            self._refresh_field_sections(None)
            self._sticky_heading = ""
            self.editorialChanged.emit()
            if basis:
                self._publish_similar(
                    "ready",
                    result.message,
                    [(mid, 0.0) for mid in ordered[:8]],
                    basis=basis,
                    basis_label=basis_label or basis,
                )
        elif basis:
            self._publish_similar(
                "unavailable" if result.state == "unavailable" else "empty",
                result.message,
                [],
                basis=basis,
                basis_label=basis_label or basis,
            )
        self._apply_result(result)

    @Slot()
    def clearScope(self) -> None:
        if not self._scope_kind and not self._buckets and self._facet == "memory":
            return
        self._reset_library_scope()

    @Property(str, notify=surfaceChanged)
    def facet(self) -> str:
        return self._facet

    @Property(bool, notify=surfaceChanged)
    def settingsOpen(self) -> bool:
        return self._settings_open

    @Property(bool, notify=surfaceChanged)
    def namedItemsOpen(self) -> bool:
        return self._named_items_open

    @Property("QVariantList", notify=surfaceChanged)
    def namedItems(self):
        return list(self._named_items)

    @Property(int, notify=surfaceChanged)
    def namedItemCount(self) -> int:
        return len(self._named_items)

    @Slot(int, result=str)
    def namedItemId(self, index: int) -> str:
        rows = self._named_items
        if index < 0 or index >= len(rows):
            return ""
        return str(rows[index].get("item_id") or "")

    @Slot(int, result=str)
    def namedItemLabel(self, index: int) -> str:
        rows = self._named_items
        if index < 0 or index >= len(rows):
            return ""
        return str(rows[index].get("label") or "")

    @Property("QVariantList", notify=surfaceChanged)
    def buckets(self):
        return list(self._buckets)

    @Property(int, notify=surfaceChanged)
    def cellSize(self) -> int:
        return cell_size(self._adapter.density().data.get("density"))

    @Property(str, notify=lensChanged)
    def bg0(self) -> str:
        return tokens_for(self._atmosphere_id)["bg0"]

    @Property(str, notify=lensChanged)
    def bg1(self) -> str:
        return tokens_for(self._atmosphere_id)["bg1"]

    @Property(str, notify=lensChanged)
    def accent(self) -> str:
        return tokens_for(self._atmosphere_id)["accent"]

    @Property(str, notify=lensChanged)
    def text1(self) -> str:
        return tokens_for(self._atmosphere_id)["text1"]

    @Property(str, notify=lensChanged)
    def text2(self) -> str:
        return tokens_for(self._atmosphere_id)["text2"]

    @Property(str, notify=lensChanged)
    def reviewColor(self) -> str:
        return tokens_for(self._atmosphere_id)["review"]

    @Property(bool, notify=lensChanged)
    def lightPalette(self) -> bool:
        return self._atmosphere_id == "light"

    @Property(str, notify=lensChanged)
    def bg2(self) -> str:
        return tokens_for(self._atmosphere_id)["bg2"]

    @Property(str, notify=lensChanged)
    def bg3(self) -> str:
        return tokens_for(self._atmosphere_id)["bg3"]

    @Property(str, notify=lensChanged)
    def border1(self) -> str:
        return tokens_for(self._atmosphere_id)["border1"]

    @Property(str, notify=lensChanged)
    def text3(self) -> str:
        return tokens_for(self._atmosphere_id)["text3"]

    @Property(str, notify=lensChanged)
    def accentDim(self) -> str:
        return tokens_for(self._atmosphere_id)["accentDim"]

    @Property(str, notify=lensChanged)
    def dangerColor(self) -> str:
        return tokens_for(self._atmosphere_id)["danger"]

    @Property(str, notify=peopleChanged)
    def reviewCountText(self) -> str:
        return self._review_text

    @Property(str, notify=peopleChanged)
    def unresolvedText(self) -> str:
        return self._unresolved_text

    @Property(str, notify=surfaceChanged)
    def searchModeLabel(self) -> str:
        return self._adapter.search_mode().message

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

    @Property(str, notify=similarChanged)
    def similarBasis(self) -> str:
        """Door key: whole | region | face. Empty when idle."""
        return self._similar_basis

    @Property(str, notify=similarChanged)
    def similarBasisLabel(self) -> str:
        """User-facing basis for the open results strip (distinct per door)."""
        return self._similar_basis_label

    @Property(str, notify=similarChanged)
    def selectionNote(self) -> str:
        """How the current box was chosen. Plain language, not a model id."""
        return self._selection_note

    @Property(bool, notify=similarChanged)
    def canBackDiscovery(self) -> bool:
        return bool(self._discovery_trail)

    def _discovery_file(self) -> Path:
        store = Path(self._jobs.store)
        return store.with_name(store.stem + ".visual-discovery.json")

    def _persist_discovery(self) -> None:
        if self._similar_state not in {"ready", "empty"}:
            return
        payload = {
            "query_media_id": self._query_focus_id or self._session.focus_id or "",
            "basis": self._similar_basis,
            "basis_label": self._similar_basis_label,
            "note": self._similar_note,
            "state": self._similar_state,
            "region": list(self._region_norm) if self._region_norm else None,
            "understanding": self._selection_note,
            "items": [
                {
                    "media_id": row[0],
                    "score": row[1],
                    "match_norm": [row[2], row[3], row[4], row[5]] if len(row) >= 6 else [0, 0, 0, 0],
                }
                for row in self._similar._rows
            ],
        }
        try:
            self._discovery_file().write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            return

    def _push_discovery(self) -> None:
        if self._similar_state not in {"ready", "empty"} or not self._session.focus_id:
            return
        self._discovery_trail.append(
            {
                "focus_id": self._session.focus_id,
                "rows": list(self._similar._rows),
                "state": self._similar_state,
                "note": self._similar_note,
                "basis": self._similar_basis,
                "basis_label": self._similar_basis_label,
                "region": self._region_norm,
            }
        )
        if len(self._discovery_trail) > 8:
            self._discovery_trail = self._discovery_trail[-8:]

    def _open_focus_keep_results(self, media_id: str) -> None:
        item = self._jobs.media(media_id)
        if item is None or item.source_type not in {"folder", "video"}:
            return
        rows = list(self._similar._rows)
        state = self._similar_state
        note = self._similar_note
        basis = self._similar_basis
        label = self._similar_basis_label
        self._session.open_focus(media_id)
        self._load_focus_boxes(media_id)
        self._similar.set_rows(rows)
        self._similar_state = state
        self._similar_note = note
        self._similar_basis = basis
        self._similar_basis_label = label
        try:
            missing = not item.path or not Path(item.path).is_file()
        except OSError:
            missing = True
        if missing:
            self._report_missing_original()
        self.focusChanged.emit()
        self.similarChanged.emit()
        self.diagnosticsChanged.emit()

    @Slot(str)
    def openDiscoveryHit(self, media_id: str) -> None:
        """Open a visual result without replacing the result set or the day scope."""
        if not media_id:
            return
        self._push_discovery()
        self._open_focus_keep_results(media_id)

    @Slot()
    def backToDiscovery(self) -> None:
        if not self._discovery_trail:
            return
        frame = self._discovery_trail.pop()
        focus_id = str(frame.get("focus_id") or "")
        if focus_id:
            item = self._jobs.media(focus_id)
            if item is not None and item.source_type in {"folder", "video"}:
                self._session.open_focus(focus_id)
                self._load_focus_boxes(focus_id)
        region = frame.get("region")
        self._region_norm = tuple(region) if region else None
        self._query_focus_id = focus_id
        self.selectionChanged.emit()
        self._similar.set_rows(list(frame.get("rows") or []))
        self._similar_state = str(frame.get("state") or "idle")
        self._similar_note = str(frame.get("note") or "")
        self._similar_basis = str(frame.get("basis") or "")
        self._similar_basis_label = str(frame.get("basis_label") or "")
        self.focusChanged.emit()
        self.similarChanged.emit()
        self.diagnosticsChanged.emit()

    @Slot()
    def showDayAroundFocus(self) -> None:
        """Day neighbours stay available. They do not clear the visual result set."""
        item = self._jobs.media(self._session.focus_id or "")
        if item is None or not item.day:
            self._set_result("Opened photo. No date on file — time context unavailable.")
            return
        day = item.day
        if len(day) >= 7:
            self._sync_calendar_month(day[:7])
        self._select_scope("day", day)

    @Slot()
    def reopenLastVisualSearch(self) -> None:
        path = self._discovery_file()
        if not path.is_file():
            self._publish_similar(
                "empty",
                "Similar (Similar look): no saved search yet.",
                [],
                basis="region",
                basis_label="Similar look",
            )
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._publish_similar(
                "unavailable",
                "Similar (Similar look): the saved search could not be read.",
                [],
                basis="region",
                basis_label="Similar look",
            )
            return
        query = str(payload.get("query_media_id") or "")
        if query:
            self._open_focus_keep_results(query)
        region = payload.get("region")
        if isinstance(region, list) and len(region) == 4:
            self._region_norm = tuple(float(v) for v in region)
        rows = []
        for item in payload.get("items") or []:
            if not item.get("media_id"):
                continue
            norm = item.get("match_norm") or [0, 0, 0, 0]
            rows.append(
                (
                    str(item.get("media_id") or ""),
                    float(item.get("score") or 0.0),
                    float(norm[0]),
                    float(norm[1]),
                    float(norm[2]),
                    float(norm[3]),
                )
            )
        self._publish_similar(
            str(payload.get("state") or ("ready" if rows else "empty")),
            str(payload.get("note") or "Similar (Similar look): restored."),
            rows,
            basis=str(payload.get("basis") or "region"),
            basis_label=str(payload.get("basis_label") or "Similar look"),
        )

    @Slot()
    def cancelSimilar(self) -> None:
        self._stop_search(publish=True)

    def _stop_search(self, *, publish: bool) -> None:
        self._search_generation += 1
        if self._cancel_flag is not None:
            self._cancel_flag[0] = True
        self._similar_cancel = True
        was_busy = self._search_busy
        self._search_busy = False
        if was_busy:
            self.searchBusyChanged.emit()
        if not publish:
            return
        label = self._similar_basis_label or "Similar look"
        self._publish_similar(
            "empty",
            f"Similar ({label}): cancelled.",
            [],
            basis=self._similar_basis or "region",
            basis_label=label,
            persist=False,
        )

    def _start_visual_search(self, *, basis: str, label: str, build) -> None:
        """Publish looking immediately, then run build(cancel_flag) off the UI thread."""
        if self._cancel_flag is not None:
            self._cancel_flag[0] = True
        self._search_generation += 1
        generation = self._search_generation
        flag = [False]
        self._cancel_flag = flag
        self._similar_cancel = False
        self._search_failure = ""
        self._search_busy = True
        self.searchBusyChanged.emit()
        self._publish_similar(
            "loading",
            f"Similar ({label}): looking through photos already indexed.",
            [],
            basis=basis,
            basis_label=label,
            persist=False,
        )
        thread = _VisualSearchThread(generation, lambda: build(flag), self)
        thread.succeeded.connect(self._on_visual_search)
        thread.failed.connect(self._on_visual_search_failed)
        self._search_thread = thread
        thread.start()
        if os.environ.get("SEMBLON_SEARCH_SYNC") == "1":
            self._settle_search()

    def _settle_search(self) -> None:
        """Wait until the worker finishes. Connect before the running check so a fast result is not missed."""
        thread = self._search_thread
        if thread is not None and thread.isRunning():
            loop = QEventLoop()

            def _stop() -> None:
                if loop.isRunning():
                    loop.quit()

            thread.finished.connect(_stop)
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(_stop)
            timer.start(8000)
            if thread.isRunning():
                loop.exec()
            timer.stop()
            try:
                thread.finished.disconnect(_stop)
            except RuntimeError:
                pass
        app = QApplication.instance()
        if app is None:
            return
        for _ in range(8):
            app.processEvents()
            if not self._search_busy:
                break

    @Slot(int, object)
    def _on_visual_search(self, generation: int, payload) -> None:
        if generation != self._search_generation:
            return
        self._search_busy = False
        self.searchBusyChanged.emit()
        if payload is None or self._similar_cancel:
            self._publish_similar(
                "empty",
                f"Similar ({self._similar_basis_label or 'Similar look'}): cancelled.",
                [],
                basis=self._similar_basis or "region",
                basis_label=self._similar_basis_label or "Similar look",
                persist=False,
            )
            return
        if isinstance(payload, Result):
            result = payload
        else:
            result = self._safe_call(lambda: self._adapter.similar_region(payload))
        self._publish_similar_result(result)

    @Slot(int, str)
    def _on_visual_search_failed(self, generation: int, message: str) -> None:
        if generation != self._search_generation:
            return
        self._search_busy = False
        self._search_failure = str(message or "search failed")
        self.searchBusyChanged.emit()
        label = self._similar_basis_label or "Similar look"
        self._publish_similar(
            "error",
            f"Similar ({label}): search failed.",
            [],
            basis=self._similar_basis or "region",
            basis_label=label,
            persist=False,
        )

    def _refresh_index_note(self) -> None:
        state, note = self._index_for_focus()
        if state == self._index_state and note == self._index_note:
            return
        self._index_state = state
        self._index_note = note
        self.indexChanged.emit()
        self.similarChanged.emit()

    def _index_for_focus(self) -> tuple[str, str]:
        media_id = self._session.focus_id or ""
        if not media_id:
            return "", ""
        patch = 0
        coarse = 0
        try:
            store = Path(self._jobs.store)
            conn = sqlite3.connect(f"file:{store.resolve()}?mode=ro", uri=True)
            try:
                row = conn.execute(
                    """SELECT
                         SUM(CASE WHEN e.modality='region_patch' THEN 1 ELSE 0 END),
                         SUM(CASE WHEN e.modality='region' THEN 1 ELSE 0 END)
                       FROM embeddings e
                       JOIN observation_items i ON i.item_id = e.item_id
                       JOIN observations o ON o.observation_id = i.observation_id
                       WHERE o.media_id=?""",
                    (media_id,),
                ).fetchone()
            finally:
                conn.close()
            patch = int((row[0] if row else 0) or 0)
            coarse = int((row[1] if row else 0) or 0)
        except sqlite3.Error:
            return "unknown", ""
        if patch > 0 and self._job_active:
            return "patch", "Still indexing. This photo can already be searched."
        if patch > 0:
            return "patch", ""
        if self._job_active:
            return "indexing", "Still indexing. Photos already added can be opened."
        if coarse > 0:
            return "fallback", (
                "This photo has a coarse index only. Matches may miss the area you point at."
            )
        return "unindexed", (
            "This photo is not indexed yet. Add its folder so search can see inside it."
        )

    @Property(int, notify=similarChanged)
    def similarCount(self) -> int:
        return self._similar.rowCount()

    @property
    def similar_model(self) -> SimilarStripModel:
        return self._similar

    def _set_result(self, text: str) -> None:
        self._result_text = present_message(self._mode, text, fallback="Nothing was searched.")
        self.resultChanged.emit()

    def _clear_similar(self) -> None:
        self._similar.set_rows([])
        self._similar_state = "idle"
        self._similar_note = ""
        self._similar_basis = ""
        self._similar_basis_label = ""
        self.similarChanged.emit()

    def _publish_similar(
        self,
        state: str,
        note: str,
        rows: list[tuple[str, float]],
        *,
        basis: str = "",
        basis_label: str = "",
        persist: bool = True,
    ) -> None:
        self._similar.set_rows(rows)
        self._similar_state = state
        self._similar_note = present_message(self._mode, note, fallback="Similar search could not run.")
        self._similar_basis = str(basis or "")
        self._similar_basis_label = str(basis_label or "")
        self.similarChanged.emit()
        if persist and state in {"ready", "empty"}:
            self._persist_discovery()

    def _match_for_focus(self) -> tuple[float, float, float, float]:
        focus = self._session.focus_id or ""
        for row in self._similar._rows:
            if str(row[0]) != focus or len(row) < 6:
                continue
            if float(row[4]) > 0 and float(row[5]) > 0:
                return float(row[2]), float(row[3]), float(row[4]), float(row[5])
        return 0.0, 0.0, 0.0, 0.0

    @Property(float, notify=similarChanged)
    def matchX(self) -> float:
        return self._match_for_focus()[0]

    @Property(float, notify=similarChanged)
    def matchY(self) -> float:
        return self._match_for_focus()[1]

    @Property(float, notify=similarChanged)
    def matchW(self) -> float:
        return self._match_for_focus()[2]

    @Property(float, notify=similarChanged)
    def matchH(self) -> float:
        return self._match_for_focus()[3]

    @Property(float, notify=selectionChanged)
    def selectionX(self) -> float:
        return float(self._region_norm[0]) if self._region_norm else 0.0

    @Property(float, notify=selectionChanged)
    def selectionY(self) -> float:
        return float(self._region_norm[1]) if self._region_norm else 0.0

    @Property(float, notify=selectionChanged)
    def selectionW(self) -> float:
        return float(self._region_norm[2]) if self._region_norm else 0.0

    @Property(float, notify=selectionChanged)
    def selectionH(self) -> float:
        return float(self._region_norm[3]) if self._region_norm else 0.0

    @Property(bool, notify=selectionChanged)
    def selectionOnFocus(self) -> bool:
        """The drawn box belongs to this photo. A match photo shows its match box instead."""
        if not self._region_norm or self._region_norm[2] <= 0 or self._region_norm[3] <= 0:
            return False
        return (self._query_focus_id or "") == (self._session.focus_id or "")

    @Property(str, notify=selectionChanged)
    def queryFocusId(self) -> str:
        return self._query_focus_id or ""

    @Property(bool, notify=searchBusyChanged)
    def searchBusy(self) -> bool:
        return self._search_busy

    @Property(str, notify=indexChanged)
    def indexState(self) -> str:
        return self._index_state

    @Property(str, notify=indexChanged)
    def indexNote(self) -> str:
        if not self._index_note:
            return ""
        return present_message(self._mode, self._index_note, fallback="")

    @Property(str, notify=similarChanged)
    def similarCaution(self) -> str:
        if self._similar_state != "ready" or self._similar_basis == "face":
            return ""
        return "A match is a similar region, not proof it is the same object."

    @Property(str, notify=similarChanged)
    def retrievalDetail(self) -> str:
        parts: list[str] = []
        if self._similar_basis_label:
            parts.append(self._similar_basis_label)
        if self._index_state:
            parts.append(self._index_state)
        if self._similar._rows:
            parts.append(f"top {float(self._similar._rows[0][1]):.2f}")
        if self._mode == ADVANCED and self._search_failure:
            parts.append(self._search_failure)
        return " · ".join(parts)

    def _keeps_file(self) -> Path:
        store = Path(self._jobs.store)
        return store.with_name(store.stem + ".discoveries.json")

    def _read_keeps(self) -> list[dict]:
        path = self._keeps_file()
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _recent_keeps(self) -> list[dict]:
        return list(reversed(self._read_keeps()[-8:]))

    @Property(int, notify=keepsChanged)
    def keptCount(self) -> int:
        return len(self._recent_keeps())

    @Slot(int, result=str)
    def keptLabel(self, index: int) -> str:
        rows = self._recent_keeps()
        if index < 0 or index >= len(rows):
            return ""
        item = rows[index]
        label = str(item.get("understanding") or "Kept find")
        count = len(item.get("items") or [])
        noun = "match" if count == 1 else "matches"
        return f"{label} · {count} {noun}"

    @Slot(result=str)
    def keepDiscovery(self) -> str:
        """Remember the open visual search beside the library. No new table."""
        if self._similar_state != "ready" or not self._similar._rows or not self._region_norm:
            return "Search a region before keeping a find."
        entry = {
            "query_media_id": self._query_focus_id or self._session.focus_id or "",
            "basis": self._similar_basis,
            "basis_label": self._similar_basis_label,
            "understanding": self._selection_note,
            "note": self._similar_note,
            "region": list(self._region_norm),
            "items": [
                {
                    "media_id": row[0],
                    "score": row[1],
                    "match_norm": [row[2], row[3], row[4], row[5]] if len(row) >= 6 else [0, 0, 0, 0],
                }
                for row in self._similar._rows
            ],
        }
        rows = self._read_keeps()
        rows.append(entry)
        rows = rows[-50:]
        try:
            self._keeps_file().write_text(json.dumps(rows), encoding="utf-8")
        except OSError:
            return "This find could not be kept."
        self.keepsChanged.emit()
        self._set_result("Kept this find.")
        return "Kept this find."

    @Slot(int)
    def openKept(self, index: int) -> None:
        rows = self._recent_keeps()
        if index < 0 or index >= len(rows):
            return
        item = rows[index]
        query = str(item.get("query_media_id") or "")
        if query:
            self._query_focus_id = query
            self._open_focus_keep_results(query)
        region = item.get("region")
        if isinstance(region, list) and len(region) == 4:
            self._region_norm = tuple(float(value) for value in region)
        self.selectionChanged.emit()
        self._selection_note = str(item.get("understanding") or "")
        packed = []
        for hit in item.get("items") or []:
            if not hit.get("media_id"):
                continue
            norm = hit.get("match_norm") or [0, 0, 0, 0]
            packed.append(
                (
                    str(hit.get("media_id")),
                    float(hit.get("score") or 0.0),
                    float(norm[0]),
                    float(norm[1]),
                    float(norm[2]),
                    float(norm[3]),
                )
            )
        self._publish_similar(
            "ready" if packed else "empty",
            str(item.get("note") or "Kept find."),
            packed,
            basis=str(item.get("basis") or "region"),
            basis_label=str(item.get("basis_label") or "Similar look"),
        )

    def _publish_similar_result(self, result) -> None:
        """Shared Focus strip publish for whole / region / face doors."""
        understanding = str((result.data or {}).get("understanding") or "")
        if understanding:
            self._selection_note = understanding
        rows = []
        for item in (result.data.get("items") or []):
            if not item.get("media_id"):
                continue
            rows.append(
                (
                    str(item.get("media_id") or ""),
                    float(item.get("score") or 0.0),
                    float(item.get("match_nx") or 0.0),
                    float(item.get("match_ny") or 0.0),
                    float(item.get("match_nw") or 0.0),
                    float(item.get("match_nh") or 0.0),
                )
            )
        state = result.state if result.state in {"ready", "empty", "unavailable", "error"} else "error"
        note = result.message if result.message else "Similar search could not run."
        error_id = str((result.data or {}).get("error_id") or "")
        label = str((result.data or {}).get("basis_label") or self._similar_basis_label or "Similar look")
        if state == "unavailable" and error_id == "region.NO_PACK":
            note = f"Similar ({label}): the region model is not installed."
        elif state == "unavailable" and error_id == "region.NO_PATCH_INDEX":
            note = f"Similar ({label}): these photos are not indexed for region search yet."
        elif error_id in {"region.ENCODE", "region.NO_IMAGE", "region.NO_STORE"}:
            state = "error"
            note = f"Similar ({label}): search failed."
        self._result_text = ""
        self.resultChanged.emit()
        self._publish_similar(
            state,
            note,
            rows,
            basis=str(result.data.get("basis") or ""),
            basis_label=str(result.data.get("basis_label") or ""),
        )

    def _clear_query(self) -> None:
        if self._search_busy:
            self._stop_search(publish=False)
        self._region_norm = None
        self._selection_kind = ""
        self._selection_note = ""
        self.selectionChanged.emit()
        self._result_text = ""
        self.resultChanged.emit()
        self._clear_similar()

    def _load_focus_boxes(self, media_id: str) -> None:
        """Observation outlines for the open still. Face click → face-similar; never stamps identity."""
        from semblon.canvas_data import overlay_boxes

        self._selected_observation = ""
        self._focus_boxes = []
        item = self._jobs.media(media_id)
        if item is None or item.source_type not in {"folder", "video"}:
            return
        width = float(item.width or 0)
        height = float(item.height or 0)
        if width <= 0 or height <= 0:
            return
        try:
            board = self._jobs.canvas()
        except Exception:
            return
        for box in overlay_boxes(board, media_id):
            bbox = box.get("bbox") or []
            if len(bbox) != 4:
                continue
            try:
                x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            except (TypeError, ValueError):
                continue
            nw = max(0.0, (x2 - x1) / width)
            nh = max(0.0, (y2 - y1) / height)
            if nw <= 0 or nh <= 0:
                continue
            kind = str(box.get("kind") or "")
            source = str(box.get("source") or "")
            from semblon.selection import click_adopts_box

            self._focus_boxes.append(
                {
                    "id": str(box.get("id") or ""),
                    "kind": kind,
                    "source": source,
                    "snap": click_adopts_box(kind, source),
                    "tag": str(box.get("tag") or ""),
                    "color": str(box.get("color") or "#2e8b57"),
                    "nx": max(0.0, min(1.0, x1 / width)),
                    "ny": max(0.0, min(1.0, y1 / height)),
                    "nw": max(0.0, min(1.0, nw)),
                    "nh": max(0.0, min(1.0, nh)),
                }
            )

    def _clear_focus_boxes(self) -> None:
        self._focus_boxes = []
        self._selected_observation = ""

    @Property(bool, notify=focusChanged)
    def focusFileMissing(self) -> bool:
        """True when Focus is open but the stored original path is gone."""
        item = self._jobs.media(self._session.focus_id or "")
        if item is None or not item.path:
            return bool(self._session.focus_id)
        try:
            return not Path(item.path).is_file()
        except OSError:
            return True

    def _report_missing_original(self) -> None:
        # One line: primary presentation allowlists exact strings.
        self._set_result(
            "This photo is missing from its stored path. "
            "If you moved or renamed it, add that folder again so Semblon can reconnect it."
        )

    @Slot(str)
    def openFocus(self, media_id: str) -> None:
        item = self._jobs.media(media_id)
        if item is None or item.source_type not in {"folder", "video"}:
            return
        self._session.open_focus(media_id)
        self._clear_query()
        self._load_focus_boxes(media_id)
        try:
            missing = not item.path or not Path(item.path).is_file()
        except OSError:
            missing = True
        if missing:
            self._report_missing_original()
        self.focusChanged.emit()
        self.diagnosticsChanged.emit()

    @Slot(str)
    def openFocusInContext(self, media_id: str) -> None:
        """Open a search/similar hit and scope Time to its day when mtime exists."""
        item = self._jobs.media(media_id)
        if item is None or item.source_type not in {"folder", "video"}:
            return
        day = item.day
        try:
            missing = not item.path or not Path(item.path).is_file()
        except OSError:
            missing = True
        self.openFocus(media_id)
        if day:
            # Scope neighbours without inventing a date when mtime is missing.
            if len(day) >= 7:
                self._sync_calendar_month(day[:7])
            self._select_scope("day", day)
        elif not missing:
            self._set_result("Opened photo. No date on file — time context unavailable.")

    @Slot(int)
    def openIndex(self, index: int) -> None:
        rows = self._jobs.archive_window(index, 1)
        if not rows or rows[0].source_type not in {"folder", "video"}:
            return
        self._session.open_focus(rows[0].media_id)
        self._clear_query()
        self._load_focus_boxes(rows[0].media_id)
        self.focusChanged.emit()
        self.diagnosticsChanged.emit()

    @Slot(float)
    def setScroll(self, y: float) -> None:
        if self._session.focus_id:
            return
        self._session.scroll = max(0.0, float(y))

    @Slot()
    def focusNext(self) -> None:
        self._session.move_focus(1)
        self._clear_query()
        if self._session.focus_id:
            self._load_focus_boxes(self._session.focus_id)
        else:
            self._clear_focus_boxes()
        self.focusChanged.emit()
        self.diagnosticsChanged.emit()

    @Slot()
    def focusPrev(self) -> None:
        self._session.move_focus(-1)
        self._clear_query()
        if self._session.focus_id:
            self._load_focus_boxes(self._session.focus_id)
        else:
            self._clear_focus_boxes()
        self.focusChanged.emit()
        self.diagnosticsChanged.emit()

    @property
    def people_model(self) -> PeopleModel:
        return self._people

    @Property(bool, notify=peopleChanged)
    def peopleOpen(self) -> bool:
        return self._people_open

    @Property(str, notify=peopleChanged)
    def selectedTitle(self) -> str:
        row = self._people.row(self._selected_subject)
        if not row:
            return ""
        return str(row.get("title") or "")

    @Property(int, notify=peopleChanged)
    def selectedCount(self) -> int:
        row = self._people.row(self._selected_subject)
        if not row:
            return 0
        return len(row.get("members") or [])

    @Property("QVariantList", notify=peopleChanged)
    def selectedMembers(self):
        row = self._people.row(self._selected_subject)
        if not row:
            return []
        return list(row.get("members") or [])

    @Property(str, notify=peopleChanged)
    def mergeTargetSubject(self) -> str:
        return self._merge_target_subject

    @Property(str, notify=peopleChanged)
    def mergeTargetTitle(self) -> str:
        row = self._people.row(self._merge_target_subject)
        if not row:
            return ""
        return str(row.get("title") or "")

    @Property("QVariantList", notify=peopleChanged)
    def mergeCandidates(self):
        rows = []
        for item in self._people._rows:
            if item["subject"] == self._selected_subject:
                continue
            if str(item.get("kind") or "") != "cluster":
                continue
            rows.append(dict(item))
        return rows

    @Property(int, notify=peopleChanged)
    def splitSelectionCount(self) -> int:
        return len(self._split_faces)

    @Property(bool, notify=peopleChanged)
    def canSplitSelected(self) -> bool:
        row = self._people.row(self._selected_subject)
        if not row or str(row.get("kind") or "") != "cluster":
            return False
        total = len(row.get("members") or [])
        return 0 < len(self._split_faces) < total

    @Property(bool, notify=peopleChanged)
    def canMergeSelected(self) -> bool:
        selected = self._people.row(self._selected_subject)
        target = self._people.row(self._merge_target_subject)
        if not selected or not target:
            return False
        if str(selected.get("kind") or "") != "cluster" or str(target.get("kind") or "") != "cluster":
            return False
        return self._selected_subject != self._merge_target_subject

    @Property(str, notify=peopleChanged)
    def peopleNote(self) -> str:
        return self._people_note

    @Property(str, notify=peopleChanged)
    def selectedSubject(self) -> str:
        return self._selected_subject

    @Property(str, notify=peopleChanged)
    def selectedKind(self) -> str:
        row = self._people.row(self._selected_subject)
        if not row:
            return ""
        return str(row.get("kind") or "")

    @Property(str, notify=peopleChanged)
    def selectedBandLabel(self) -> str:
        row = self._people.row(self._selected_subject)
        if not row:
            return ""
        return str(row.get("bandLabel") or "")

    @Property(str, notify=peopleChanged)
    def selectedPersonId(self) -> str:
        row = self._people.row(self._selected_subject)
        if not row:
            return ""
        return str(row.get("personId") or "")

    @Property("QVariantList", notify=peopleChanged)
    def personDays(self):
        """Dated days for the selected named person (newest first). Not identity."""
        return list(self._person_days)

    @Property(bool, notify=peopleChanged)
    def canBrowsePersonTime(self) -> bool:
        return bool(self._person_days)

    @Property(bool, notify=focusChanged)
    def canReviewFaceGroup(self) -> bool:
        """True when the Focus face maps to a candidate group or unassigned face on the board."""
        return self._subject_for_face(self._selected_observation) is not None

    @Property(bool, notify=peopleChanged)
    def canNameSelected(self) -> bool:
        return self.selectedKind in {"cluster", "track", "unassigned"}

    @Property(bool, notify=peopleChanged)
    def canNoteSelected(self) -> bool:
        return self.selectedKind in {"cluster", "unassigned"}

    @Property(bool, notify=peopleChanged)
    def canIgnoreSelected(self) -> bool:
        return self.selectedKind in {"cluster", "unassigned"}

    @Property(bool, notify=peopleChanged)
    def canRuleOutSelected(self) -> bool:
        if self.selectedKind not in {"cluster", "unassigned"}:
            return False
        from semblon.review import ruled_out_enabled

        return bool(ruled_out_enabled())

    @Property(bool, notify=peopleChanged)
    def canMergeCluster(self) -> bool:
        return self.selectedKind == "cluster"

    @Property(bool, notify=peopleChanged)
    def canSplitCluster(self) -> bool:
        return self.selectedKind == "cluster"

    @Property(str, notify=peopleChanged)
    def evidenceId(self) -> str:
        return self._evidence_id

    @Property(bool, notify=peopleChanged)
    def peopleEmpty(self) -> bool:
        return self._people.rowCount() == 0

    @Slot()
    def openPeople(self) -> None:
        self._refresh_people()
        self._people_open = True
        self.peopleChanged.emit()

    @Slot(str)
    def reviewFaceGroup(self, face_id: str = "") -> None:
        """Leave Focus and open the People desk on the group or named person for this face."""
        fid = str(face_id or self._selected_observation or "").strip()
        subject = self._subject_for_face(fid)
        named_subject = self._named_subject_for_face(fid)
        if named_subject:
            subject = named_subject
        if not subject:
            self._set_result("No candidate group for this face yet.")
            return
        if self._session.focus_id:
            self._session.escape()
            self._clear_query()
            self._clear_focus_boxes()
            self.focusChanged.emit()
            self.diagnosticsChanged.emit()
            self.lensChanged.emit()
        self._refresh_people()
        self._people_open = True
        row = self._people.row(subject)
        self._selected_subject = subject if row else ""
        self._evidence_id = str(row["mediaId"]) if row else ""
        self._merge_target_subject = ""
        self._split_faces = []
        if row:
            note = (
                "Opened this person."
                if row.get("named")
                else "Opened the candidate group for this face."
            )
            self._people_note = present_message(
                self._mode,
                note,
                fallback=note,
            )
        else:
            self._people_note = present_message(
                self._mode,
                "That group is no longer here.",
                fallback="That group is no longer here.",
            )
        self._reload_person_days()
        self.peopleChanged.emit()

    @Slot()
    def closePeople(self) -> None:
        self._people_open = False
        self._selected_subject = ""
        self._evidence_id = ""
        self._merge_target_subject = ""
        self._split_faces = []
        self._person_days = []
        self.peopleChanged.emit()

    @Slot(str)
    def selectGroup(self, subject: str) -> None:
        row = self._people.row(subject)
        self._selected_subject = subject if row else ""
        self._evidence_id = str(row["mediaId"]) if row else ""
        if not row:
            self._people_note = "That group is no longer here."
        self._merge_target_subject = ""
        self._split_faces = []
        self._reload_person_days()
        self.peopleChanged.emit()

    @Slot()
    def browseSelectedPersonInTime(self) -> None:
        """Named person → newest dated day in Field/Focus. Archive day neighbours."""
        if not self._person_days:
            self._people_note = present_message(
                self._mode,
                "No dated photos for this person yet.",
                fallback="No dated photos for this person yet.",
            )
            self.peopleChanged.emit()
            return
        self.openPersonDay(str(self._person_days[0].get("day") or ""))

    @Slot(str)
    def openPersonDay(self, day: str) -> None:
        """Open a representative still for this person's day with Gate A day scope."""
        wanted = str(day or "").strip()
        hit = next((row for row in self._person_days if str(row.get("day") or "") == wanted), None)
        if hit is None:
            self._people_note = present_message(
                self._mode,
                "No dated photos for this person yet.",
                fallback="No dated photos for this person yet.",
            )
            self.peopleChanged.emit()
            return
        media_id = str(hit.get("mediaId") or "").strip()
        if not media_id:
            self._people_note = present_message(
                self._mode,
                "No dated photos for this person yet.",
                fallback="No dated photos for this person yet.",
            )
            self.peopleChanged.emit()
            return
        self.closePeople()
        self.openFocusInContext(media_id)
        if self._session.focus_id and self._scope_kind == "day":
            self._set_result("Opened this person in Time.")

    @Property(bool, notify=peopleChanged)
    def personFieldFilterActive(self) -> bool:
        return bool(self._person_field_filter)

    @Property(str, notify=peopleChanged)
    def personFieldFilterLabel(self) -> str:
        return str(self._person_field_label or "")

    @Slot()
    def showSelectedPersonOnly(self) -> None:
        """Explicit person-scoped Field. Day neighbours stay archive-wide until this is on."""
        row = self._people.row(self._selected_subject)
        if not row or not row.get("named"):
            self._people_note = present_message(
                self._mode,
                "No dated photos for this person yet.",
                fallback="No dated photos for this person yet.",
            )
            self.peopleChanged.emit()
            return
        person_id = str(row.get("personId") or "").strip()
        if not person_id:
            self._people_note = present_message(
                self._mode,
                "No dated photos for this person yet.",
                fallback="No dated photos for this person yet.",
            )
            self.peopleChanged.emit()
            return
        from semblon.memory import MemoryError, history

        try:
            rec = history(self._jobs.store, person=person_id)
        except MemoryError:
            rec = {"items": []}
        media_ids: list[str] = []
        seen: set[str] = set()
        for item in rec.get("items") or []:
            if str(item.get("source_type") or "") != "folder":
                continue
            mid = str(item.get("media_id") or "").strip()
            if mid and mid not in seen:
                seen.add(mid)
                media_ids.append(mid)
        if not media_ids:
            self._people_note = present_message(
                self._mode,
                "No dated photos for this person yet.",
                fallback="No dated photos for this person yet.",
            )
            self.peopleChanged.emit()
            return
        title = str(row.get("title") or "this person")
        self._person_field_filter = True
        self._person_field_ids = media_ids
        self._person_field_label = title
        self.closePeople()
        self._scope_kind = ""
        self._scope_label = ""
        self._facet = "memory"
        self._buckets = []
        self._apply_scope_view()
        self.editorialChanged.emit()
        self.peopleChanged.emit()
        self._apply_result(Result("ready", f"Showing only {title}."))

    @Slot()
    def clearPersonFieldFilter(self) -> None:
        if not self._person_field_filter and not self._person_field_ids:
            return
        self._person_field_filter = False
        self._person_field_ids = []
        self._person_field_label = ""
        self._apply_scope_view()
        self.editorialChanged.emit()
        self.peopleChanged.emit()
        self._apply_result(Result("ready", "Showing the full archive again."))

    @Slot()
    def openUnresolvedInbox(self) -> None:
        """Open People desk on the first overlooked / review-required face."""
        result = self._safe_call(
            lambda: self._adapter.unresolved(include_rejected=self._mode == ADVANCED)
        )
        faces = list(result.data.get("faces") or [])
        self._refresh_people()
        self._people_open = True
        if not faces:
            self._people_note = present_message(
                self._mode,
                "No overlooked faces right now.",
                fallback="No overlooked faces right now.",
            )
            self.peopleChanged.emit()
            self._apply_result(result)
            return
        # Prefer REVIEW_REQUIRED, then UNKNOWN — navigable inbox, not auto-name.
        ordered = sorted(
            faces,
            key=lambda row: 0 if str(row.get("bucket") or "") == "REVIEW_REQUIRED" else 1,
        )
        face_id = str(ordered[0].get("face_id") or "").strip()
        subject = self._subject_for_face(face_id) if face_id else None
        if subject is None and face_id and self._people.row(face_id) is not None:
            subject = face_id
        if subject and self._people.row(subject) is not None:
            self._selected_subject = subject
            row = self._people.row(subject)
            self._evidence_id = str(row.get("mediaId") or "") if row else ""
            self._reload_person_days()
        self._people_note = present_message(
            self._mode,
            "Opened overlooked faces for review.",
            fallback="Opened overlooked faces for review.",
        )
        self.peopleChanged.emit()
        self._apply_result(
            Result(
                "ready",
                f"Overlooked faces: {len(faces)} to review.",
                {"faces": faces},
            )
        )

    @Slot(str)
    def selectMergeTarget(self, subject: str) -> None:
        if subject and subject != self._selected_subject and self._people.row(subject) is not None:
            self._merge_target_subject = subject
        else:
            self._merge_target_subject = ""
        self.peopleChanged.emit()

    @Slot(str)
    def toggleSplitFace(self, face_id: str) -> None:
        fid = str(face_id or "").strip()
        if not fid:
            return
        row = self._people.row(self._selected_subject)
        if not row:
            return
        member_ids = {str(member.get("face_id") or "") for member in row.get("members") or []}
        if fid not in member_ids:
            return
        if fid in self._split_faces:
            self._split_faces = [face for face in self._split_faces if face != fid]
        else:
            self._split_faces = [*self._split_faces, fid]
        self.peopleChanged.emit()

    @Slot()
    def clearSplitSelection(self) -> None:
        if not self._split_faces:
            return
        self._split_faces = []
        self.peopleChanged.emit()

    @Slot(str)
    def openEvidence(self, media_id: str) -> None:
        if not media_id:
            self._people_note = "No photo for this group."
            self.peopleChanged.emit()
            return
        self.openFocus(media_id)

    def face_crop_spec(self, face_id: str) -> dict | None:
        fid = str(face_id or "").strip()
        if not fid:
            return None
        try:
            board = self._jobs.board()
        except Exception:
            return None
        for item in board.get("items") or []:
            for member in item.get("members") or []:
                if str(member.get("face_id") or "") == fid:
                    bbox = member.get("bbox") or ()
                    return {
                        "path": member.get("path") or "",
                        "bbox": bbox,
                        "media_id": member.get("media_id") or "",
                    }
        return None

    def _subject_for_face(self, face_id: str) -> str | None:
        """Board subject (cluster_id or unassigned face_id) for a Focus face. Read-only."""
        fid = str(face_id or "").strip()
        if not fid:
            return None
        for box in self._focus_boxes:
            if str(box.get("id") or "") == fid and str(box.get("kind") or "") != "face":
                return None
        try:
            board = self._jobs.board()
        except Exception:
            return None
        for item in board.get("items") or []:
            if item.get("kind") == "track":
                continue
            members = item.get("members") or []
            for member in members:
                if str(member.get("face_id") or "") != fid:
                    continue
                kind = str(item.get("kind") or "cluster")
                if kind == "unassigned":
                    return str(item.get("face_id") or fid)
                subject = str(item.get("cluster_id") or "")
                return subject or None
        return None

    def _named_subject_for_face(self, face_id: str) -> str | None:
        """If this face already belongs to a named person, return that board subject."""
        fid = str(face_id or "").strip()
        if not fid:
            return None
        try:
            board = self._jobs.board()
        except Exception:
            return None
        person_id = ""
        for item in board.get("items") or []:
            if item.get("kind") == "track":
                continue
            for member in item.get("members") or []:
                if str(member.get("face_id") or "") == fid:
                    person_id = str(member.get("person_id") or "").strip()
                    break
            if person_id:
                break
        if not person_id:
            return None
        for item in board.get("items") or []:
            if not item.get("named"):
                continue
            subject = str(item.get("cluster_id") or item.get("face_id") or "")
            for member in item.get("members") or []:
                if str(member.get("person_id") or "").strip() == person_id:
                    return subject or None
            names_pid = str(item.get("person_id") or "").strip()
            if names_pid == person_id:
                return subject or None
        return None

    def _reload_person_days(self) -> None:
        """Rebuild day chips for the selected named person from memory.history."""
        self._person_days = []
        row = self._people.row(self._selected_subject)
        if not row or not row.get("named"):
            return
        person_id = str(row.get("personId") or "").strip()
        if not person_id:
            for member in row.get("members") or []:
                person_id = str(member.get("person_id") or "").strip()
                if person_id:
                    break
        if not person_id:
            return
        self._person_days = self._person_days_for(person_id)

    def _person_days_for(self, person_id: str) -> list[dict]:
        """Unique calendar days with a folder still to open. Newest first."""
        from semblon.memory import MemoryError, history

        pid = str(person_id or "").strip()
        if not pid:
            return []
        try:
            rec = history(self._jobs.store, person=pid)
        except MemoryError:
            return []
        by_day: dict[str, dict] = {}
        for item in rec.get("items") or []:
            if str(item.get("source_type") or "") != "folder":
                continue
            when = str(item.get("when") or "")
            day = when[:10] if len(when) >= 10 and when[4:5] == "-" else ""
            media_id = str(item.get("media_id") or "").strip()
            if not day or not media_id:
                continue
            prev = by_day.get(day)
            if prev is None:
                by_day[day] = {"day": day, "mediaId": media_id, "count": 1}
            else:
                prev["count"] = int(prev.get("count") or 0) + 1
                # history items are oldest→newest; keep the latest still for that day
                prev["mediaId"] = media_id
        return sorted(by_day.values(), key=lambda row: str(row.get("day") or ""), reverse=True)

    def _refresh_people(self) -> None:
        from semblon.native_shell.presentation import group_band_label, group_list_title

        rows = []
        try:
            board = self._jobs.board()
        except Exception as exc:  # noqa: BLE001 — empty desk, not a traceback
            self._people.set_rows([])
            self._people_note = "No groups yet." if "unknown run" in str(exc).lower() else "Groups could not be read."
            return
        for item in board.get("items") or []:
            members = item.get("members") or []
            kind = str(item.get("kind") or "cluster")
            if kind == "track":
                # Tracks are shown as tracks — never as people. Video-only tracks stay off this desk.
                if members and all(str(member.get("source_type") or "") == "video" for member in members):
                    continue
                subject = str(item.get("track_id") or item.get("cluster_id") or "")
                if not subject:
                    continue
                media_id = str(members[0].get("media_id") or "") if members else ""
                face_id = str(members[0].get("face_id") or "") if members else ""
                rows.append(
                    {
                        "subject": subject,
                        "title": group_list_title(
                            named=False, names=[], kind="track", band="track"
                        ),
                        "count": int(item.get("face_count") or len(members) or 0),
                        "named": False,
                        "mediaId": media_id,
                        "faceId": face_id,
                        "personId": "",
                        "kind": "track",
                        "band": "track",
                        "bandLabel": group_band_label(named=False, kind="track", band="track"),
                        "members": list(members),
                    }
                )
                continue
            if members and all(str(member.get("source_type") or "") == "video" for member in members):
                continue
            media_id = ""
            face_id = ""
            if members:
                media_id = str(members[0].get("media_id") or "")
                face_id = str(members[0].get("face_id") or "")
            names = [str(n) for n in (item.get("person_names") or []) if n]
            subject = str(item.get("cluster_id") or item.get("face_id") or "")
            if not subject:
                continue
            band = str(item.get("band") or ("unassigned" if kind == "unassigned" else "review"))
            named = bool(item.get("named"))
            person_id = ""
            for member in members:
                pid = str(member.get("person_id") or "").strip()
                if pid:
                    person_id = pid
                    break
            rows.append(
                {
                    "subject": subject,
                    "title": group_list_title(named=named, names=names, kind=kind, band=band),
                    "count": int(item.get("face_count") or 0),
                    "named": named,
                    "mediaId": media_id,
                    "faceId": face_id,
                    "personId": person_id,
                    "kind": kind,
                    "band": band,
                    "bandLabel": group_band_label(named=named, kind=kind, band=band),
                    "members": list(members),
                }
            )
        self._people.set_rows(rows)
        self._review_text = self._adapter.review_counts().message
        self._unresolved_text = self._adapter.unresolved(include_rejected=self._mode == ADVANCED).message
        if self._selected_subject and self._people.row(self._selected_subject) is None:
            self._selected_subject = ""
            self._evidence_id = ""
            self._people_note = "That group is no longer here."
            self._merge_target_subject = ""
            self._split_faces = []
            self._person_days = []
        else:
            self._reload_person_days()

    @Slot()
    def escape(self) -> None:
        if self._search_busy:
            self.cancelSimilar()
            return
        if self._session.focus_id and self._people_open:
            self._session.escape()
            self._clear_query()
            self._clear_focus_boxes()
            self.focusChanged.emit()
            self.diagnosticsChanged.emit()
            return
        if self._people_open:
            self.closePeople()
            return
        if self._activity_open:
            self.closeActivity()
            return
        self._session.escape()
        self._clear_query()
        self._clear_focus_boxes()
        self.focusChanged.emit()
        self.diagnosticsChanged.emit()
        self.lensChanged.emit()

    def _close_stage_overlays(self, *, keep_focus: bool = False) -> None:
        """Leave People / Settings / Activity without dropping the archive."""
        changed = False
        if self._settings_open:
            self._settings_open = False
            changed = True
        if self._named_items_open:
            self._named_items_open = False
            changed = True
        if self._activity_open:
            self._activity_open = False
            self._activity_rows = []
            changed = True
        if self._people_open:
            self._people_open = False
            self._selected_subject = ""
            self._evidence_id = ""
            self._merge_target_subject = ""
            self._split_faces = []
            self._person_days = []
            self.peopleChanged.emit()
        if not keep_focus and self._session.focus_id:
            self._session.escape()
            self._clear_query()
            self._clear_focus_boxes()
            self.focusChanged.emit()
            self.diagnosticsChanged.emit()
            self.lensChanged.emit()
        if changed:
            self.surfaceChanged.emit()

    @Slot()
    def showHome(self) -> None:
        """Return to the permanent Home launchpad. Archive and scope stay."""
        self._close_stage_overlays(keep_focus=False)
        if self._stage != "home":
            self._stage = "home"
            self.surfaceChanged.emit()
        elif not self._settings_open:
            self.surfaceChanged.emit()

    @Slot()
    def showLibrary(self) -> None:
        """Open the archive field (timeline, calendar, grid)."""
        self._close_stage_overlays(keep_focus=False)
        if self._stage != "library":
            self._stage = "library"
            self.surfaceChanged.emit()
        else:
            self.surfaceChanged.emit()

    @Slot()
    def wordmark(self) -> None:
        """Sidebar Library entry — open the archive field."""
        self.showLibrary()

    @Slot()
    def openVisualDiscovery(self) -> None:
        """Open Focus so the person can point or draw. Empty archive adds a folder."""
        if self._jobs.archive_count() == 0:
            self.addFolder()
            return
        if self._settings_open or self._named_items_open or self._activity_open:
            self._settings_open = False
            self._named_items_open = False
            if self._activity_open:
                self._activity_open = False
                self._activity_rows = []
            self.surfaceChanged.emit()
        if self._people_open:
            self._people_open = False
            self._selected_subject = ""
            self._evidence_id = ""
            self._merge_target_subject = ""
            self._split_faces = []
            self._person_days = []
            self.peopleChanged.emit()
        media_id = self._session.focus_id or ""
        item = self._jobs.media(media_id) if media_id else None
        if item is None or item.source_type not in {"folder", "video"}:
            media_id = ""
            for row in self._jobs.archive_window(0, 48):
                if row.source_type in {"folder", "video"}:
                    media_id = row.media_id
                    break
        if not media_id:
            self._set_result("No photo is ready for visual discovery yet.")
            return
        self.openFocus(media_id)

    @Slot(str)
    def submitCommand(self, text: str) -> None:
        query = str(text or "").strip()
        if not query:
            self._set_result("Nothing was searched.")
            return
        lowered = query.lower()
        if lowered in {"people", "groups"}:
            self._set_result(self.peopleSummary())
            return
        mode = str(self._adapter.search_mode().data.get("mode") or "people")
        if mode in {"text", "object"}:
            within = self._active_field_media_ids()
            result = self._safe_call(
                lambda: self._adapter.search(mode, query, within_media_ids=within)
            )
            self._apply_discovery_search(result)
            return
        if self._mode == PRIMARY:
            self._set_result(self._search_people(query))
            return
        if lowered in {"status", "diag", "diagnostics"}:
            self._set_result(self.diagnosticsText)
            return
        self._set_result(self._search_people(query))

    def _search_people(self, query: str) -> str:
        """Primary-safe text search over named groups only."""
        try:
            board = self._jobs.board()
        except Exception:  # noqa: BLE001
            return "People groups are unavailable right now."
        q = query.strip().lower()
        if not q:
            return "Nothing was searched."
        names: list[str] = []
        for item in board.get("items") or []:
            for name in item.get("person_names") or []:
                value = str(name or "").strip()
                if value and q in value.lower():
                    names.append(value)
        deduped = sorted(set(names), key=str.lower)
        return summarize_people_results(deduped, len(deduped), self._mode)

    @Slot(str)
    def setMode(self, mode: str) -> None:
        chosen = normalize_mode(mode)
        if chosen == self._mode:
            return
        self._mode = chosen
        self._save_shell_mode(chosen)
        if chosen == PRIMARY:
            self._notice = present_message(chosen, self._notice, fallback="")
            self._similar_note = present_message(chosen, self._similar_note, fallback="") if self._similar_note else ""
            self._people_note = present_message(chosen, self._people_note, fallback="") if self._people_note else ""
            self.surfaceChanged.emit()
            self.similarChanged.emit()
            self.peopleChanged.emit()
        self._set_result(self._result_text)
        self.lensChanged.emit()
        self.diagnosticsChanged.emit()

    @Slot()
    def toggleMode(self) -> None:
        self.setMode(ADVANCED if self._mode == PRIMARY else PRIMARY)

    @Slot(str)
    def setAtmosphere(self, atmosphere_id: str) -> None:
        chosen = str(atmosphere_id or "").strip().lower()
        if chosen not in ATMOSPHERE_IDS:
            return
        if chosen == self._atmosphere_id:
            return
        self._atmosphere_id = chosen
        save_theme_mode(chosen, self._prefs_store())
        self.lensChanged.emit()
        self._sync_windows_caption()

    @Slot()
    def cycleAtmosphere(self) -> None:
        ids = list(ATMOSPHERE_IDS)
        try:
            index = ids.index(self._atmosphere_id)
        except ValueError:
            index = 0
        self.setAtmosphere(ids[(index + 1) % len(ids)])

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
        self._set_result(_ask_lines(lines, self._mode))

    @Slot(float, float, float, float)
    def setRegion(self, nx: float, ny: float, nw: float, nh: float) -> None:
        """Normalized image-space rectangle from the focus view. Not a widget image."""
        self._region_norm = (
            max(0.0, min(1.0, float(nx))),
            max(0.0, min(1.0, float(ny))),
            max(0.0, min(1.0, float(nw))),
            max(0.0, min(1.0, float(nh))),
        )
        if self._session.focus_id:
            self._query_focus_id = self._session.focus_id
        self._selection_kind = "drawn"
        self._selection_note = "Drawn region."
        self.selectionChanged.emit()

    @Slot(float, float, float, float, str, float, float, float, float, float, float, result=str)
    def adjustSelectionBox(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        edge: str,
        dx: float,
        dy: float,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
    ) -> str:
        """Local-pixel rectangle after dragging one edge or corner."""
        rect = adjust_box(x, y, w, h, edge, dx, dy, min_x, min_y, max_x, max_y)
        return ",".join(f"{value:.8f}" for value in rect)

    @Slot(float, float, float, float, float, result=str)
    def clampFocusView(self, x: float, y: float, scale: float, width: float, height: float) -> str:
        view = clamp_view(x, y, scale, width, height)
        return ",".join(f"{value:.8f}" for value in view)

    @Slot(float, float, float, float, float, float, float, float, result=str)
    def zoomFocusView(
        self,
        x: float,
        y: float,
        scale: float,
        view_x: float,
        view_y: float,
        width: float,
        height: float,
        factor: float,
    ) -> str:
        """Zoom the fitted photo about a viewport point. Returns x, y, scale."""
        view = zoom_about(x, y, scale, view_x, view_y, factor, width, height)
        return ",".join(f"{value:.8f}" for value in view)

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

    @Slot(float, float, result=str)
    def pointAt(self, nx: float, ny: float) -> str:
        """Settled Focus point. Stored region, else refine_from_point, then findSimilar."""
        self._point_source = ""
        media_id = self._session.focus_id
        if not media_id:
            self._clear_query()
            return ""
        item = self._jobs.media(media_id)
        if item is None:
            self._clear_query()
            return ""
        width = int(item.width or 0)
        height = int(item.height or 0)
        if width <= 0 or height <= 0:
            self._clear_query()
            return ""
        nx = float(nx)
        ny = float(ny)
        if nx < 0.0 or ny < 0.0 or nx >= 1.0 or ny >= 1.0:
            self._clear_query()
            return ""
        from semblon.selection import point_box

        px = max(0, min(width - 1, int(nx * width)))
        py = max(0, min(height - 1, int(ny * height)))
        # A click that missed a face, text, or detector box stays on that point.
        # Stored regions and flood-fill are not allowed to move it.
        x, y, w, h = point_box(px, py, width, height)
        self._point_source = "point"
        self.setRegion(x / width, y / height, w / width, h / height)
        self._selection_kind = "point"
        self._selection_note = "The click stays where you put it."
        self.findSimilar()
        return f"{x / width},{y / height},{w / width},{h / height}"

    def _bbox_at_point(self, media_id: str, px: int, py: int) -> tuple[int, int, int, int] | None:
        stored = self._stored_visual_bbox(media_id, px, py)
        if stored is not None:
            self._point_source = "stored"
            return stored
        refined = self._refine_bbox(media_id, px, py)
        if refined is None:
            return None
        self._point_source = "refine"
        return refined

    def _stored_visual_bbox(self, media_id: str, px: int, py: int) -> tuple[int, int, int, int] | None:
        from semblon.process import latest_run_id
        from semblon.visual.masks import point_in_rows
        from semblon.visual.model import PAINT_ORDER
        from semblon.visual.persist import load_hover_rows

        run_id = latest_run_id(self._jobs.store)
        if not run_id:
            return None
        rows = load_hover_rows(self._jobs.store, media_id=media_id, run_id=run_id)
        rank = {kind: index for index, kind in enumerate(PAINT_ORDER)}
        hit = None
        for item in sorted(rows, key=lambda row: rank.get(row.get("kind") or "unknown", 0)):
            if point_in_rows(item.get("rows") or {}, px, py):
                hit = item
        if hit is None:
            return None
        bbox = hit.get("bbox") or []
        if len(bbox) < 4 or bbox[0] is None:
            return None
        x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        if x2 <= x1 or y2 <= y1:
            return None
        return int(x1), int(y1), max(1, int(round(x2 - x1))), max(1, int(round(y2 - y1)))

    def _refine_bbox(self, media_id: str, px: int, py: int) -> tuple[int, int, int, int] | None:
        from semblon.selection import load_media_bgr
        from semblon.semantic_visual import LocalSemanticVisualProvider

        image = load_media_bgr(self._jobs.store, media_id)
        if image is None:
            return None
        try:
            raw = LocalSemanticVisualProvider().refine_from_point(image, px, py)
        except Exception:
            return None
        if not raw or not raw.get("bbox"):
            return None
        box = raw["bbox"]
        if len(box) < 4:
            return None
        x1, y1, x2, y2 = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        if x2 <= x1 or y2 <= y1:
            return None
        label = str(raw.get("label") or "").strip().lower()
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        refine = str(payload.get("refine") or "")
        if label == "unknown region" or refine not in {"floodfill", "sam2"}:
            self._selection_kind = "unknown"
            self._selection_note = "Plain rectangle. Segmentation is not available."
        else:
            self._selection_kind = "region"
            self._selection_note = "Pointed area from the photo. Not a named object."
        return int(x1), int(y1), max(1, int(round(x2 - x1))), max(1, int(round(y2 - y1)))

    def _item_for_decision(self, subject: str) -> dict:
        """Board row for a people-desk subject. Cluster id is never a person id."""
        subject = str(subject or "").strip()
        items: list[dict] = []
        try:
            board = self._jobs.board()
            items = [item for item in (board.get("items") or []) if isinstance(item, dict)]
        except Exception:  # noqa: BLE001 — decide still reports a review error
            items = []
        for item in items:
            if subject and str(item.get("cluster_id") or "") == subject:
                if item.get("kind") not in {"cluster", "track", "unassigned"}:
                    return {**item, "kind": "cluster"}
                return item
        for item in items:
            if item.get("kind") == "track" and subject and str(item.get("track_id") or "") == subject:
                return item
        for item in items:
            if item.get("kind") == "cluster":
                continue
            if subject and str(item.get("face_id") or "") == subject:
                return item
        return {"kind": "cluster", "cluster_id": subject}

    @Slot(str, str, str, result=str)
    def decide(self, kind: str, subject: str, text: str) -> str:
        """Human decision only. review_board routes; review.py is the only SQL writer."""
        from semblon.process import latest_run_id
        from semblon.review import ReviewError
        from semblon.review_board import (
            ReviewUiError,
            apply_ignore,
            apply_merge,
            apply_name,
            apply_note,
            apply_rule_out,
            apply_split,
        )

        run_id = latest_run_id(self._jobs.store)
        if not run_id:
            return self._after_decision("No reviewed run yet.")
        if not (text or "").strip() and kind in {"name", "note"}:
            return self._after_decision("A name or note is required.")
        item = self._item_for_decision(subject)
        try:
            if kind == "name":
                rec = apply_name(self._jobs.store, run_id, item, text)
                return self._after_decision(decision_success("name", str(rec.get("display_name") or "")))
            if kind == "ignore":
                apply_ignore(self._jobs.store, run_id, item)
                return self._after_decision(decision_success("ignore"))
            if kind == "note":
                apply_note(self._jobs.store, run_id, item, text)
                return self._after_decision(decision_success("note"))
            if kind == "merge":
                other = text.strip()
                apply_merge(self._jobs.store, run_id, [subject, other])
                return self._after_decision(decision_success("merge"))
            if kind == "split":
                face_ids = [part.strip() for part in text.split(",") if part.strip()]
                cluster_id = str(item.get("cluster_id") or subject)
                apply_split(self._jobs.store, run_id, cluster_id, face_ids)
                return self._after_decision(decision_success("split"))
            if kind == "rule_out":
                target_person = text.strip() or None
                ruled = {}
                if target_person:
                    ruled["person" + "_id"] = target_person
                apply_rule_out(self._jobs.store, run_id, item, **ruled)
                return self._after_decision(decision_success("rule_out"))
        except (ReviewError, ReviewUiError) as exc:
            return self._after_decision(str(exc))
        except Exception as exc:  # noqa: BLE001 — show the decision failure
            return self._after_decision(str(exc))
        return self._after_decision("That decision is not available.")

    @Slot(result=str)
    def mergeSelectedGroup(self) -> str:
        if not self._selected_subject:
            return self._after_decision("Select a group first.")
        if not self._merge_target_subject or self._merge_target_subject == self._selected_subject:
            return self._after_decision("Select another group to merge with.")
        return self.decide("merge", self._selected_subject, self._merge_target_subject)

    @Slot(result=str)
    def splitSelectedFaces(self) -> str:
        if not self._selected_subject:
            return self._after_decision("Select a group first.")
        row = self._people.row(self._selected_subject)
        if not row:
            return self._after_decision("That group is no longer here.")
        members = row.get("members") or []
        if not self._split_faces:
            return self._after_decision("Select one or more faces to split.")
        if len(self._split_faces) >= len(members):
            return self._after_decision("Leave at least one face in the group.")
        return self.decide("split", self._selected_subject, ",".join(self._split_faces))

    @Slot(str, result=str)
    def faceThumb(self, face_id: str) -> str:
        if not face_id:
            return ""
        return f"image://face/{face_id}"

    @Slot(str, result=bool)
    def isSplitFaceSelected(self, face_id: str) -> bool:
        return str(face_id or "") in self._split_faces

    def _after_decision(self, note: str) -> str:
        if str(note).startswith(("Saved", "Merged", "Split", "Left this", "Marked this")):
            self._events.record(IDENTITY_CHANGED, {})
        self._people_note = present_message(self._mode, note, fallback="Semblon couldn't save that decision.")
        self._merge_target_subject = ""
        self._split_faces = []
        self._refresh_people()
        self.peopleChanged.emit()
        return self._people_note

    @Slot(result=str)
    def peopleSummary(self) -> str:
        try:
            board = self._jobs.board()
        except Exception as exc:  # noqa: BLE001
            return present_message(self._mode, str(exc), fallback="People groups are unavailable right now.")
        lines: list[str] = []
        names: list[str] = []
        for item in board.get("items") or []:
            if item.get("named"):
                label = (item.get("person_names") or [""])[0]
                if label:
                    names.append(str(label))
                continue
            label = item.get("cluster_id") or item.get("face_id") or "group"
            lines.append(f"{label} · {item.get('face_count') or 0}")
        if self._mode == ADVANCED:
            return "\n".join(lines) or "No unnamed groups."
        return summarize_people_results(names, len(names), self._mode)

    def _safe_call(self, fn) -> Result:
        try:
            return fn()
        except AdapterError as exc:
            state = exc.state if exc.state in {"error", "unavailable"} else "error"
            return Result(state, exc.message)
        except Exception as exc:  # noqa: BLE001 - a slot must never raise into Qt
            return Result("error", str(exc) or "Semblon couldn't complete that step.")

    def _apply_result(self, result: Result) -> None:
        self._notice = present_message(self._mode, result.message, fallback="Semblon couldn't complete that step.")
        self._surface_state = result.state if result.state in {
            "empty",
            "loading",
            "error",
            "unavailable",
            "ready",
        } else "error"
        self._set_result(result.message)
        self.surfaceChanged.emit()

    @Slot(str)
    def setFacet(self, name: str) -> None:
        mapping = {
            "memory": "memory",
            "days": "timeline",
            "timeline": "timeline",
            "folders": "folders",
            "folder": "folders",
            "moments": "moments",
        }
        facet = mapping.get(str(name or "").strip().lower())
        if facet is None:
            return
        if facet == "memory":
            self._reset_library_scope()
            return
        self._facet = facet
        result = self._safe_call(lambda: self._adapter.browse(facet))
        self._buckets = list(result.data.get("buckets") or [])
        self._apply_result(result)

    @Slot(str)
    def selectBucket(self, key: str) -> None:
        wanted = str(key or "")
        for row in self._buckets:
            if str(row.get("key") or "") == wanted:
                self._scope_kind = ""
                self._scope_label = ""
                self._field_sections = []
                self._model.set_media_ids(list(row.get("media_ids") or []))
                self.editorialChanged.emit()
                label = str(row.get("label") or "group")
                self._apply_result(Result("ready", f"Showing {label}."))
                return

    @Slot(str)
    def setSearchMode(self, mode: str) -> None:
        self._apply_result(self._safe_call(lambda: self._adapter.set_search_mode(mode)))
        self.surfaceChanged.emit()

    @Slot(str)
    def setLibraryFilter(self, filter_key: str) -> None:
        self._apply_result(self._safe_call(lambda: self._adapter.set_library_filter(filter_key)))

    @Slot()
    def cycleDensity(self) -> None:
        order = ("cozy", "comfortable", "compact")
        current = str(self._adapter.density().data.get("density") or "cozy")
        nxt = order[(order.index(current) + 1) % len(order)] if current in order else "cozy"
        self._apply_result(self._adapter.set_density(nxt))

    @Slot(str)
    def setGpuPreference(self, value: str) -> None:
        key = str(value or "").strip().lower()
        if key in {"auto", "default", ""}:
            choice = None
        elif key in {"on", "gpu", "true", "1"}:
            choice = True
        elif key in {"off", "cpu", "false", "0"}:
            choice = False
        else:
            self._apply_result(Result("error", "GPU: choose on, off, or auto."))
            return
        self._apply_result(self._adapter.set_gpu(choice))

    @Slot()
    def libraryHealth(self) -> None:
        self._apply_result(self._safe_call(self._adapter.library_health))

    @Slot()
    def scanDuplicates(self) -> None:
        self._apply_result(self._safe_call(self._adapter.duplicates))

    @Property(bool, notify=surfaceChanged)
    def activityOpen(self) -> bool:
        return self._activity_open

    @Property("QVariantList", notify=surfaceChanged)
    def activityRows(self):
        return list(self._activity_rows)

    @Slot()
    def showActivity(self) -> None:
        result = self._safe_call(self._adapter.activity)
        rows: list[dict] = []
        rec = result.data.get("activity") or {}
        for key, label in (
            ("processing", "Processing"),
            ("together_lines", "Together"),
            ("moment_lines", "Moments"),
        ):
            if key == "processing":
                lines = list((rec.get("processing") or {}).get("lines") or [])
            else:
                lines = list(rec.get(key) or [])
            for line in lines:
                text = str(line or "").strip()
                if text:
                    rows.append({"section": label, "text": text})
        self._activity_rows = rows
        self._activity_open = self._mode == ADVANCED
        if self._mode != ADVANCED:
            self._apply_result(result)
            return
        if not rows:
            self._apply_result(result)
        else:
            self._apply_result(Result("ready", f"Activity: {len(rows)} recent lines.", {"activity": rec}))
        self.surfaceChanged.emit()

    @Slot()
    def closeActivity(self) -> None:
        if not self._activity_open and not self._activity_rows:
            return
        self._activity_open = False
        self._activity_rows = []
        self.surfaceChanged.emit()

    @Slot()
    def showCapabilities(self) -> None:
        self._apply_result(self._safe_call(self._adapter.capabilities))

    @Slot()
    def resetDefaults(self) -> None:
        result = self._safe_call(self._adapter.reset_defaults)
        self._atmosphere_id = self._load_atmosphere_id()
        self._apply_result(result)
        self.lensChanged.emit()

    @Slot()
    def clearLibrary(self) -> None:
        """Drop the folder index and names. Original files stay on disk."""
        if self._jobs.busy:
            self._apply_result(Result("unavailable", "A folder is being added. Wait until that finishes."))
            return
        answer = QMessageBox.question(
            None,
            "Clear library",
            "Remove the folder index, names, and kept finds from Semblon?\n\n"
            "Photos on disk stay where they are.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._apply_result(Result("empty", "Library clear was cancelled."))
            return
        self._stop_search(publish=False)
        try:
            self._jobs.wipe_library()
        except Exception:  # noqa: BLE001 — the notice stays non-technical
            self._apply_result(Result("error", "The library could not be cleared."))
            return
        self._discovery_trail.clear()
        for path in (self._discovery_file(), self._keeps_file()):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self._session.clear_focus()
        self._region_norm = None
        self._selection_kind = ""
        self._selection_note = ""
        self.selectionChanged.emit()
        self._clear_similar()
        self._clear_focus_boxes()
        self._refresh_library()
        self._refresh_people()
        self.keepsChanged.emit()
        self.focusChanged.emit()
        self.peopleChanged.emit()
        self._stage = "home"
        self.surfaceChanged.emit()
        self._apply_result(
            Result(
                "ready",
                "Library cleared. Photos on disk were kept. Add a folder to start again.",
            )
        )

    @Slot()
    def toggleSettings(self) -> None:
        self._settings_open = not self._settings_open
        self.surfaceChanged.emit()

    @Slot()
    def openNamedItems(self) -> None:
        result = self._safe_call(self._adapter.named_items)
        self._named_items = list(result.data.get("items") or [])
        self._named_items_open = True
        if self._named_item_id and not any(item.get("item_id") == self._named_item_id for item in self._named_items):
            self._named_item_id = ""
        self._apply_result(result)

    @Slot()
    def closeNamedItems(self) -> None:
        self._named_items_open = False
        self.surfaceChanged.emit()

    @Slot(str)
    def selectNamedItem(self, item_id: str) -> None:
        self._named_item_id = str(item_id or "")
        self.surfaceChanged.emit()

    @Slot(str, result=str)
    def nameNamedItem(self, name: str) -> str:
        result = self._safe_call(lambda: self._adapter.name_named_item(self._named_item_id, name))
        if result.state == "ready":
            listed = self._safe_call(self._adapter.named_items)
            self._named_items = list(listed.data.get("items") or [])
        self._apply_result(result)
        return self._notice

    @Slot()
    def rescanFolder(self) -> None:
        """Re-run the last folder through the existing ingest door with reprocess."""
        if self._jobs.busy:
            self._apply_result(Result("unavailable", "Rescan: a folder is already being added."))
            return
        if self._last_folder is None or not Path(self._last_folder).is_dir():
            folder = QFileDialog.getExistingDirectory(None, "Choose a folder to look through again")
            if not folder:
                self._apply_result(Result("empty", "Rescan: add a folder first."))
                return
            self._apply_result(Result("ready", "Rescan: looking through that folder again."))
            self._start_ingest(Path(folder), reprocess=True)
            return
        self._apply_result(Result("ready", "Rescan: looking through that folder again."))
        self._start_ingest(self._last_folder, reprocess=True)

    def _local_path(self, raw: str) -> str:
        text = str(raw or "").strip()
        if text.lower().startswith("file:"):
            return QUrl(text).toLocalFile()
        return text

    @Slot()
    def chooseKnowledgePack(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            None, "Choose a knowledge pack", "", "JSON (*.json)"
        )
        if not path:
            self._apply_result(Result("empty", "Pack: choose a local pack file."))
            return
        self.inspectPack(path)

    @Slot()
    def chooseModelInstall(self) -> None:
        source, _selected = QFileDialog.getOpenFileName(None, "Choose a model file", "", "All files (*.*)")
        if not source:
            self._apply_result(Result("empty", "Model file: choose a local file."))
            return
        dest, _selected = QFileDialog.getSaveFileName(None, "Where to install the model file", "", "All files (*.*)")
        if not dest:
            self._apply_result(Result("empty", "Model file: choose where to install it."))
            return
        self.installModelFile(source, dest)

    @Slot(str, result=str)
    def inspectPack(self, path: str) -> str:
        result = self._safe_call(lambda: self._adapter.inspect_pack(self._local_path(path)))
        self._apply_result(result)
        return self._notice

    @Slot(str, str, result=str)
    def installModelFile(self, source: str, dest: str) -> str:
        result = self._safe_call(
            lambda: self._adapter.install_model_file(self._local_path(source), self._local_path(dest))
        )
        self._apply_result(result)
        return self._notice

    @Slot()
    def findSimilarWhole(self) -> None:
        media_id = self._session.focus_id
        if not media_id:
            self._publish_similar("unavailable", "Open a photo first.", [])
            return
        self._query_focus_id = media_id
        if self._similar_state == "ready" and self._similar.rowCount():
            self._push_discovery()
        self._selection_kind = ""
        self._selection_note = ""
        adapter = self._adapter

        def build(_flag):
            return adapter.similar_media(media_id)

        self._start_visual_search(basis="whole", label="Colour only", build=build)

    @Slot(str)
    def findSimilarFaces(self, face_id: str = "") -> None:
        """Focus face → ranked same-pack face hits. Not colour-histogram Similar; no auto-name."""
        fid = str(face_id or self._selected_observation or "").strip()
        if not fid:
            self._publish_similar("unavailable", "Select a face on the photo first.", [])
            return
        if self._similar_state == "ready" and self._similar.rowCount():
            self._push_discovery()
        adapter = self._adapter

        def build(_flag):
            return adapter.similar_faces(fid)

        self._start_visual_search(basis="face", label="Same face", build=build)

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
        self._query_focus_id = media_id
        self.selectionChanged.emit()
        if self._similar_state == "ready" and self._similar.rowCount():
            self._push_discovery()
        kind = self._selection_kind or None
        jobs = self._jobs
        adapter = self._adapter

        def build(flag):
            from semblon.user_region import RegionError

            try:
                rec = jobs.remember_and_find_region(
                    media_id,
                    x,
                    y,
                    w,
                    h,
                    selection_kind=kind,
                    cancelled=lambda: bool(flag[0]),
                )
            except RegionError as exc:
                return Result(
                    "unavailable",
                    f"Similar (Similar look): {exc}.",
                    {
                        "basis": "region",
                        "basis_label": "Similar look",
                        "engine": "dinov2-patch",
                        "items": [],
                    },
                )
            if flag[0]:
                return None
            return adapter.similar_region(rec)

        self._start_visual_search(basis="region", label="Similar look", build=build)

    @Slot()
    def pauseJob(self) -> None:
        self._jobs.pause_job()
        self._poll_job()

    @Slot()
    def resumeJob(self) -> None:
        """Same job door. Paused work unpauses. A cancelled folder resubmits with resume."""
        if self._jobs.paused:
            self._jobs.unpause_job()
            self._poll_job()
            return
        if self._jobs.busy or self._last_folder is None or not self._resume_ready:
            return
        self._start_ingest(self._last_folder, resume=True)

    @Slot()
    def cancelJob(self) -> None:
        self._cancel_requested = True
        self._jobs.cancel_job()
        self._poll_job()

    def path_for(self, media_id: str) -> str | None:
        return self._jobs.media_path(media_id)

    def _start_ingest(self, folder: Path, *, resume: bool = False, reprocess: bool = False) -> None:
        from semblon.observers import resolve_product_observers

        self._last_folder = Path(folder)
        self._resume_ready = False
        self._cancel_requested = False
        self._last_job_failed = False
        self._terminal_status = ""
        self._events.record(JOB_STARTED, {"resume": bool(resume)})
        prefer = load_prefer_gpu(self._prefs_store())
        try:
            self._jobs.submit_ingest(
                self._last_folder,
                on_event=self._on_worker_progress,
                on_done=self._on_worker_done,
                open_review=False,
                observers=resolve_product_observers(),
                resume=resume,
                prefer_gpu=prefer,
                reprocess=bool(reprocess),
            )
        except JobBusy:
            return
        self._surface_state = "loading"
        self.surfaceChanged.emit()
        self._poll_job()

    def _on_worker_progress(self, ev) -> None:
        current = getattr(ev, "current", None)
        total = getattr(ev, "total", None)
        self._events.record(
            JOB_PROGRESS,
            {
                "stage": str(getattr(ev, "stage", "") or ""),
                "kind": str(getattr(ev, "kind", "") or ""),
                "current": current,
                "total": total,
            },
        )
        QMetaObject.invokeMethod(self, "_flush_progress", Qt.ConnectionType.QueuedConnection)

    def _on_worker_done(self, result) -> None:
        status = str(getattr(result, "status", "") or "")
        self._terminal_status = status or "completed"
        if status in {"cancelled", "failed"} and self._last_folder is not None:
            self._resume_ready = True
        name = {
            "completed": JOB_COMPLETED,
            "cancelled": JOB_CANCELLED,
            "failed": JOB_FAILED,
        }.get(status, JOB_COMPLETED)
        self._events.record(name, {"status": status or "completed"})
        self._queue_ingest_finished()

    @Slot()
    def _flush_progress(self) -> None:
        last = self._events.last(JOB_PROGRESS)
        payload = (last or {}).get("payload") or {}
        current = payload.get("current")
        total = payload.get("total")
        if isinstance(current, int) and isinstance(total, int) and total > 0:
            self._progress_current = current
            self._progress_total = total
            self._progress_label = (
                f"Processing {current}/{total}. Photos already added can be opened."
            )
        elif payload.get("stage"):
            self._progress_label = "Processing"
        self.jobChanged.emit()
        if isinstance(current, int) and current != self._progress_seen:
            self._progress_seen = current
            self._refresh_library()
            self._refresh_index_note()

    @Slot()
    def _queue_ingest_finished(self) -> None:
        QMetaObject.invokeMethod(self, "_emit_ingest_finished", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _emit_ingest_finished(self) -> None:
        self.ingestFinished.emit()

    def _after_ingest(self) -> None:
        self._refresh_library()
        self._poll_job()
        self.jobChanged.emit()

    def _poll_job(self) -> None:
        active = self._session.job_active()
        state = self._session.job_state()
        if state == "paused" and self._job_state != "paused":
            self._events.record(JOB_PAUSED, {})
        if active != self._job_active or state != self._job_state:
            was = self._job_active
            if was and not active:
                self._progress_current = 0
                self._progress_total = 0
                self._resume_ready = self._resume_ready or bool(self._cancel_requested and self._last_folder is not None)
                self._cancel_requested = False
                self._last_job_failed = self._terminal_status == "failed"
                if self._surface_state == "loading":
                    self._surface_state = "empty" if self._jobs.archive_count() == 0 else "ready"
                    self.surfaceChanged.emit()
            self._job_active = active
            self._job_state = state
            self.jobChanged.emit()
            if was and not active:
                self._refresh_library()

    def _refresh_library(self) -> None:
        self._model.reload()
        self._events.record(LIBRARY_CHANGED, {"count": int(self._jobs.archive_count())})
        empty = self._jobs.archive_count() == 0
        self._reload_editorial()
        focus_id = self._session.focus_id
        if focus_id and self._jobs.media(focus_id) is None:
            self._session.clear_focus()
            self._clear_query()
            self.focusChanged.emit()
        self.diagnosticsChanged.emit()
        self.libraryChanged.emit()
        if empty != self._empty:
            self._empty = empty
            self.emptyChanged.emit()


def _ask_lines(lines, mode: str) -> str:
    kept = []
    for line in lines:
        text = str(line).strip()
        if not text:
            continue
        lowered = text.lower()
        if mode == PRIMARY and ("traceback" in lowered or "sqlite" in lowered):
            continue
        kept.append(text)
    return "\n".join(kept) or "Nothing was searched."

