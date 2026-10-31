"""QML-facing session. Qt reports input. Application owns archive and jobs."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import uuid
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
from PySide6.QtWidgets import QApplication, QFileDialog

from semblon.native_shell.signal_guard import install_signal_emit_guard

install_signal_emit_guard()

from semblon.atmosphere import ATMOSPHERE_LABELS, ATMOSPHERE_IDS
from semblon.application import Application, JobBusy
from semblon.library_tasks import library_work
from semblon.native_shell.images import clear_thumb_cache, reset_image_cache
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
    is_primary_safe_message,
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
    UNDATED_DAY,
    calendar_month_cells,
    day_detail,
    day_section_short_label,
    default_calendar_month,
    field_sections,
    format_count,
    format_count_exact,
    month_end_day,
    month_heading,
    parse_iso_day,
    range_media_ids,
    rows_from_scope,
    scope_ids,
    shift_month,
    sort_ids_newest_first,
    source_counts,
    timeline_density,
    undated_count,
    video_ids,
    year_matrix,
)
from semblon.ui_prefs import load_prefer_gpu, load_prefs, save_theme_mode, update_prefs
from semblon.store import connect_readonly


KEY_SHELL_MODE = "shell_mode"
KEY_CALENDAR_VIEW = "calendar_view"
KEY_ARCHIVE_SPLIT = "archive_split"
CALENDAR_VIEWS = ("years", "months", "days")


def _format_bytes(size: int) -> str:
    value = int(size or 0)
    if value <= 0:
        return "Not in this file"
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"
KEY_SCREEN_QUERY_MODE = "screen_query_mode"
SCREEN_QUERY_MODE_VISUAL = "visual"
SCREEN_QUERY_MODE_TEXT_PRIORITY = "text_priority"
SCREEN_QUERY_MODES = (SCREEN_QUERY_MODE_VISUAL, SCREEN_QUERY_MODE_TEXT_PRIORITY)

_INSTALL_LABELS = {
    "region_pack": "Get finding-by-look ready",
    "object_pack": "Get finding-by-object ready",
    "vlm_local": "Get photo descriptions ready",
}
_INSTALL_METHODS = {
    "region_pack": "install_region_pack",
    "object_pack": "install_object_pack",
    "vlm_local": "install_vlm",
}
_NOTHING_LEAVES = "Nothing leaves your computer except the add-on download."
_INSTALL_PROMPTS = {
    "region_pack": (
        "Get finding-by-look ready?",
        "Semblon needs a small add-on on this computer to find places that look like the detail you pointed at. "
        "When it is ready, this search runs again on its own.",
        ["About 85 MB, downloaded once.", _NOTHING_LEAVES],
    ),
    "object_pack": (
        "Get finding-by-object ready?",
        "Semblon needs a small add-on on this computer to recognise things in pictures, such as a bicycle or a cake. "
        "When it is ready, this search runs again on its own.",
        ["About 4 MB, downloaded once.", _NOTHING_LEAVES],
    ),
    "vlm_local": (
        "Get photo descriptions ready?",
        "Semblon will set up photo descriptions on this computer. "
        "When it is ready, this search runs again on its own.",
        ["Everything stays on this computer."],
    ),
}
_SETUP_NAMES = {
    "region_pack": "finding-by-look",
    "object_pack": "finding-by-object",
    "vlm_local": "photo descriptions",
}
_JARGON = re.compile(
    r"\b(models?|packs?|quer(?:y|ies)|embeddings?|index(?:ed|es|ing)?|capabilit(?:y|ies)|schema|api|sha256|onnx)\b",
    re.IGNORECASE,
)


def _plain(text: object, fallback: str) -> str:
    """Words a person can read. Engine wording never reaches a dialog or banner."""
    line = " ".join(str(text or "").split())
    if not line or _JARGON.search(line):
        return fallback
    return line


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


_PHASE_LABELS = {
    "first": "First look",
    "refined": "Refined",
    "detailed": "Sharpened",
    "fast": "Fast look",
    "kept": "Kept the first look",
    "checked": "Checked the matches",
}

_DOOR_LABELS = {
    "region": "Similar region",
    "face": "Same face",
    "whole": "Whole photo",
    "duplicate": "Duplicates",
}


def _confidence_label(value) -> str:
    if value is None:
        return ""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return ""
    percent = max(0, min(100, int(round(score * 100))))
    return f"Confidence {percent}%."


def _stamp_phase(result: Result, phase: str) -> Result:
    data = dict(result.data or {})
    data["search_phase"] = phase
    return Result(result.state, result.message, data)


class _VisualSearchThread(QThread):
    """Region and similar lookups off the UI thread. The slot applies the result."""

    succeeded = Signal(int, object)
    failed = Signal(int, str)
    progressed = Signal(int, object)

    def __init__(self, generation: int, fn, parent=None):
        super().__init__(parent)
        self._generation = generation
        self._fn = fn

    def _emit_progress(self, payload) -> None:
        self.progressed.emit(self._generation, payload)

    def run(self) -> None:
        try:
            self.succeeded.emit(self._generation, self._fn(self._emit_progress))
        except Exception as exc:  # noqa: BLE001 — the UI slot turns this into search failed
            self.failed.emit(self._generation, str(exc) or "search failed")


class _NameSelectionThread(QThread):
    """Name the highlighted crop off the UI thread. Does not touch the match strip."""

    succeeded = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, generation: int, fn, parent=None):
        super().__init__(parent)
        self._generation = generation
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._generation, self._fn())
        except Exception as exc:  # noqa: BLE001 — the slot turns this into an unnamed area
            self.failed.emit(self._generation, str(exc) or "naming failed")


class _TaskThread(QThread):
    """One background task that returns a Result-like object."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._fn())
        except Exception as exc:  # noqa: BLE001 — UI translates this to a safe message
            self.failed.emit(str(exc) or "task failed")


_NO_MATCHES = object()


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
    nameChanged = Signal()
    doorChanged = Signal()
    searchBusyChanged = Signal()
    indexChanged = Signal()
    keepsChanged = Signal()
    peopleChanged = Signal()
    surfaceChanged = Signal()
    editorialChanged = Signal()
    screenQueryChanged = Signal()
    _scanProgress = Signal(int)
    preflightChanged = Signal()
    tasksChanged = Signal()
    confirmChanged = Signal()
    tidyChanged = Signal()
    # QML zooms once when a discovery hit becomes Focus (not on every similar refresh).
    focusMatchZoomRequested = Signal()

    def __init__(self, model: ArchiveModel, jobs: Application):
        super().__init__()
        self._jobs = jobs
        self._session = jobs.archive
        self._model = model
        self._job_active = False
        self._job_state = "idle"
        self._category_note = ""
        self._category_coverage_text = ""
        self._refresh_coverage_when_idle = False
        self._category_job = ""
        self._category_resume = ""
        self._last_folder: Path | None = None
        self._resume_ready = False
        self._cancel_requested = False
        self._empty = self._jobs.archive_count() == 0
        self._stage = "home"
        self._reduced = reduced_motion()
        self._result_text = ""
        self._region_norm: tuple[float, float, float, float] | None = None
        self._similar = SimilarStripModel()
        self._matches_prior = _NO_MATCHES
        self._similar_state = "idle"
        self._similar_note = ""
        self._similar_basis = ""
        self._similar_basis_label = ""
        self._similar_phase = ""
        self._selection_note = ""
        self._selection_kind = ""
        self._refine_mode = "look"
        self._refine_modifier = ""
        self._refine_part_index = -1
        self._refine_parts: list[dict] = []
        self._name_note = ""
        self._name_confidence = ""
        self._identify_busy = False
        self._identify_generation = 0
        self._name_thread: _NameSelectionThread | None = None
        self._search_door = ""
        self._search_started = 0.0
        self._search_first_ms = -1
        self._search_refined_ms = -1
        self._similar_cancel = False
        self._search_generation = 0
        self._search_busy = False
        self._search_thread: _VisualSearchThread | None = None
        self._cancel_flag: list[bool] | None = None
        self._path_cache: dict[str, str] = {}
        self._index_cache: dict[tuple, tuple[str, str]] = {}
        self._index_note_at = 0.0
        self._index_note_media = ""
        self._library_refresh_at = 0.0
        self._search_failure = ""
        self._install_suggestion = ""
        self._install_suggestion_label = ""
        self._install_kind = ""
        self._install_retry = ""
        self._install_retry_rect: tuple[int, int, int, int] | None = None
        self._install_thread: _TaskThread | None = None
        self._screen_query_rect: tuple[int, int, int, int] | None = None
        self._query_source = ""
        self._screen_query_mode = self._load_screen_query_mode()
        self._screen_query_state = "idle"
        self._index_state = ""
        self._index_note = ""
        self._progress_seen: int | None = None
        self._pass_outcome = ""
        self._pass_started_mono = 0.0
        self._progress_current = 0
        self._progress_total = 0
        self._job_started_mono = 0.0
        self._job_paused_seconds = 0.0
        self._job_pause_started = 0.0
        self._job_timing_shown = ""
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
        self._confirm = {"open": False, "busy": False}
        self._confirm_yes = self._confirm_no = None
        self._confirm_keep = False
        self._confirm_dismiss_is_no = True
        self._tidy_open = False
        self._tidy_busy = False
        self._tidy_pct = 0
        self._tidy_exact_on = True
        self._tidy_near_on = False
        self._tidy_sort = "copies"
        self._tidy_picks: set[str] = set()
        self._tidy_thread: _TaskThread | None = None
        self._scanProgress.connect(self._on_scan_progress)
        self._tidy_sets: list[dict] = []
        self._name_apart = False
        self._tasks_open = False
        self._mode = self._load_shell_mode()
        self._atmosphere_id = self._load_atmosphere_id()
        self._adapter = ArchiveAdapter(jobs)
        self._events = ShellEvents()
        self._buckets: list[dict] = []
        self._facet = "memory"
        self._settings_open = False
        self._preflight_rows: list[dict] = []
        self._preflight_thread: QThread | None = None
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
        self._year_matrix: list[dict] = []
        self._undated_count = 0
        self._revealed_day = ""
        self._video_ids: set[str] = set()
        self._calendar_view = self._load_calendar_view()
        self._archive_split = self._load_archive_split()
        # One library workspace: the calendar, or a grid that replaced it.
        self._library_workspace = "calendar"
        self._grid_title = ""
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
        self.jobChanged.connect(self.tasksChanged)
        self.searchBusyChanged.connect(self.tasksChanged)
        self.indexChanged.connect(self.tasksChanged)
        self.libraryChanged.connect(self.tasksChanged)
        self.emptyChanged.connect(self.tasksChanged)
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
        install = self._install_thread
        if install is not None and install.isRunning():
            install.wait(2000)
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

    def _load_screen_query_mode(self) -> str:
        prefs = load_prefs(self._prefs_store())
        mode = str(prefs.get(KEY_SCREEN_QUERY_MODE) or "").strip().lower()
        if mode in SCREEN_QUERY_MODES:
            return mode
        return SCREEN_QUERY_MODE_VISUAL

    def _save_screen_query_mode(self, mode: str) -> None:
        picked = str(mode or "").strip().lower()
        if picked not in SCREEN_QUERY_MODES:
            picked = SCREEN_QUERY_MODE_VISUAL
        update_prefs(self._prefs_store(), **{KEY_SCREEN_QUERY_MODE: picked})

    def _load_atmosphere_id(self) -> str:
        prefs = load_prefs(self._prefs_store())
        chosen = str(prefs.get("theme") or "").strip().lower()
        if chosen in ATMOSPHERE_IDS:
            return chosen
        return "mica_dark"

    def _load_calendar_view(self) -> str:
        raw = str(load_prefs(self._prefs_store()).get(KEY_CALENDAR_VIEW) or "").strip().lower()
        if raw in CALENDAR_VIEWS:
            return raw
        return "months"

    def _load_archive_split(self) -> float:
        raw = load_prefs(self._prefs_store()).get(KEY_ARCHIVE_SPLIT, 0.46)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.46
        return max(0.32, min(0.68, value))

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

    @Property("QVariantMap", notify=focusChanged)
    def focusFileFacts(self):
        """Read-only file facts for the open photo. Missing facts stay unnamed."""
        item = self._jobs.media(self._session.focus_id or "")
        if item is None:
            return {}
        path = Path(item.path) if item.path else None
        size_text = "Not in this file"
        if path is not None:
            try:
                if path.is_file():
                    size_text = _format_bytes(path.stat().st_size)
            except OSError:
                size_text = "Not in this file"
        if item.width and item.height:
            dimensions = f"{int(item.width)} × {int(item.height)}"
        else:
            dimensions = "Not in this file"
        taken = day_section_short_label(item.day) if item.day else "Not in this file"
        return {
            "name": item.name or "Not in this file",
            "date": taken,
            "dimensions": dimensions,
            "size": size_text,
            "camera": "Not in this file",
            "location": "No location stored",
        }

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

    @Property("QVariantList", notify=focusChanged)
    def hotspots(self):
        """A few well-spaced tap targets for the open picture. Cheap: no disk, no detector."""
        from semblon.hotspots import rank_hotspots

        return rank_hotspots(self._focus_boxes)

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
            "whole": "This photo",
            "region": "A detail",
        }.get(mode, "Names")

    @Property(bool, notify=jobChanged)
    def jobActive(self) -> bool:
        return self._job_active

    @Property(str, notify=jobChanged)
    def jobState(self) -> str:
        return self._job_state

    @Property(bool, notify=jobChanged)
    def canResume(self) -> bool:
        if self._jobs.busy:
            return False
        return bool(self._category_resume) or (self._resume_ready and self._last_folder is not None)

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

    @Property(str, notify=jobChanged)
    def categoryScanNote(self) -> str:
        return self._category_note

    @Property(str, notify=jobChanged)
    def categoryCoverageText(self) -> str:
        return self._category_coverage_text

    @Slot()
    def refreshCategoryCoverage(self) -> None:
        """Read what has been checked. Does not start a scan."""
        from semblon.category_backfill import discover_coverage_text

        try:
            self._category_coverage_text = discover_coverage_text(self._jobs.store)
        except Exception:
            self._category_coverage_text = ""
        self.jobChanged.emit()

    @Property(int, notify=jobChanged)
    def jobCurrent(self) -> int:
        return int(self._progress_current)

    @Property(int, notify=jobChanged)
    def jobTotal(self) -> int:
        return int(self._progress_total)

    def _task_snapshot(self) -> dict:
        folder = self._last_folder
        has_folder = folder is not None and Path(folder).is_dir()
        count = int(self._jobs.archive_count())
        return {
            "library_count": count,
            "job_active": bool(self._job_active),
            "job_state": self._job_state,
            "job_current": int(self._progress_current),
            "job_total": int(self._progress_total),
            "can_resume": bool(self.canResume),
            "last_failed": bool(self._last_job_failed),
            "has_folder": has_folder,
            "search_busy": bool(self._search_busy),
            "index_state": self._index_state,
            "index_note": self._index_note,
            "library_summary": self.archiveSummary,
        }

    def _library_work(self) -> dict:
        return library_work(self._task_snapshot())

    @Property(bool, notify=tasksChanged)
    def tasksOpen(self) -> bool:
        return self._tasks_open

    @Property(str, notify=tasksChanged)
    def taskLabel(self) -> str:
        return str(self._library_work()["label"])

    @Property(str, notify=tasksChanged)
    def taskSummary(self) -> str:
        return str(self._library_work()["summary"])

    @Property(int, notify=tasksChanged)
    def taskCount(self) -> int:
        return int(self._library_work()["count"])

    @Property("QVariantList", notify=tasksChanged)
    def taskRows(self):
        return list(self._library_work()["rows"])

    @Slot()
    def toggleTasks(self) -> None:
        self._tasks_open = not self._tasks_open
        self.tasksChanged.emit()

    @Slot()
    def openTasks(self) -> None:
        if self._tasks_open:
            return
        self._tasks_open = True
        self.tasksChanged.emit()

    @Slot()
    def closeTasks(self) -> None:
        if not self._tasks_open:
            return
        self._tasks_open = False
        self.tasksChanged.emit()

    @Slot(str)
    def runTaskAction(self, action: str) -> None:
        name = str(action or "")
        if name == "pause":
            self.pauseJob()
        elif name == "resume":
            self.resumeJob()
        elif name == "cancel":
            self.cancelJob()
        elif name == "cancel-search":
            self.cancelSimilar()
        elif name == "rescan":
            self.rescanFolder()
        elif name == "add-folder":
            self.addFolder()
        if not self._tasks_open:
            self._tasks_open = True
            self.tasksChanged.emit()

    @Property(str, notify=jobChanged)
    def jobTiming(self) -> str:
        return self._job_timing_text()

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
        self._video_ids = video_ids(store)
        if self._scope_kind and self._scope_label not in self._scope_ids.get(self._scope_kind, {}):
            self._scope_kind = ""
            self._scope_label = ""
        day_map = self._scope_ids.get("day", {})
        if not self._calendar_month:
            self._calendar_month = default_calendar_month(day_map)
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
            self._paint_calendar()
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
        self._paint_calendar()

    def _emphasis_days(self) -> set[str]:
        """Days that intersect the active person filter or the folder scope."""
        wanted: set[str] = set()
        if self._person_field_filter and self._person_field_ids:
            wanted.update(str(media_id) for media_id in self._person_field_ids)
        if self._scope_kind == "folder":
            wanted.update(
                str(media_id)
                for media_id in self._scope_ids.get("folder", {}).get(self._scope_label, [])
            )
        if not wanted:
            return set()
        days: set[str] = set()
        for day, members in self._scope_ids.get("day", {}).items():
            if wanted.intersection(str(media_id) for media_id in members):
                days.add(str(day))
        return days

    def _paint_calendar(self) -> None:
        day_map = self._scope_ids.get("day", {})
        emphasis = self._emphasis_days()
        self._calendar_cells = calendar_month_cells(
            self._calendar_month,
            day_map,
            video_ids=self._video_ids,
            emphasis_days=emphasis,
        )
        self._year_matrix = year_matrix(
            (self._calendar_month or "")[:4],
            day_map,
            emphasis_days=emphasis,
        )
        self._undated_count = undated_count(day_map)

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
        self._paint_calendar()
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
        key = str(label or "")
        if key not in self._scope_ids.get("folder", {}):
            return
        self._grid_title = key
        self._library_workspace = "grid"
        self._select_scope("folder", key)

    @Slot(str)
    def selectDay(self, label: str) -> None:
        """Toggle a day scope. The library click path is ``openDay``."""
        day = str(label or "").strip()[:10]
        if (
            self._scope_kind == "day"
            and self._scope_label == day
        ):
            self._revealed_day = ""
            self.clearScope()
            return
        self._revealed_day = day
        if len(day) >= 7:
            self._sync_calendar_month(day[:7])
        self._select_scope("day", day)

    def _open_day_grid(self, day: str) -> None:
        """Point the grid at one day, including a day with no stored photos."""
        bucket = self._scope_ids.setdefault("day", {})
        bucket.setdefault(day, [])
        self._revealed_day = day
        self._scope_kind = "day"
        self._scope_label = day
        self._facet = "memory"
        self._buckets = []
        self._person_field_filter = False
        self._person_field_ids = []
        self._person_field_label = ""
        self._grid_title = ""
        self._library_workspace = "grid"
        if len(day) >= 7 and day[4:5] == "-":
            month = day[:7]
            if month != self._calendar_month:
                self._calendar_month = month
        ordered = self._ordered_ids(list(bucket.get(day, [])))
        self._model.set_media_ids(ordered)
        self._refresh_field_sections(ordered)
        self._sticky_heading = ""
        self._paint_calendar()
        self.editorialChanged.emit()
        if day == UNDATED_DAY:
            shown = "Unknown day"
        else:
            shown = day_section_short_label(day) or day
        self._apply_result(Result("ready", f"Showing {shown}."))

    @Slot(str)
    def openDay(self, label: str) -> None:
        """Enter a day's grid. A second call for the same day stays there."""
        day = str(label or "").strip()[:10]
        if not day:
            return
        self._open_day_grid(day)

    @Slot(str)
    def focusDay(self, label: str) -> None:
        """Enter the day grid and stay there when that day is already open."""
        self.openDay(label)

    @Slot(str)
    def revealDay(self, label: str) -> None:
        """Move the calendar to a real day without changing the media scope."""
        day = parse_iso_day(label)
        if not day:
            return
        self._revealed_day = day
        self._sync_calendar_month(day[:7])

    @Slot()
    def showUndated(self) -> None:
        """Open the no-date bucket as a grid. The calendar month stays put."""
        self._scope_ids.setdefault("day", {}).setdefault(UNDATED_DAY, [])
        self._open_day_grid(UNDATED_DAY)

    @Slot()
    def showCalendar(self) -> None:
        """Leave the grid. Highlight the day that was open and clear the scope."""
        day = self._scope_label if self._scope_kind == "day" else ""
        self._library_workspace = "calendar"
        self._reset_library_scope()
        parsed = parse_iso_day(day)
        if parsed:
            self._revealed_day = parsed
            self._sync_calendar_month(parsed[:7])
            return
        if self._revealed_day:
            self._revealed_day = ""
            self.editorialChanged.emit()

    @Slot()
    def showEverything(self) -> None:
        """Clear filters and fill the workspace with the whole library grid."""
        self._library_workspace = "grid"
        self._grid_title = ""
        self._reset_library_scope()

    @Property(str, notify=editorialChanged)
    def calendarView(self) -> str:
        return self._calendar_view

    @Slot(str)
    def setCalendarView(self, view: str) -> None:
        picked = str(view or "").strip().lower()
        if picked not in CALENDAR_VIEWS or picked == self._calendar_view:
            return
        self._calendar_view = picked
        update_prefs(self._prefs_store(), **{KEY_CALENDAR_VIEW: picked})
        self.editorialChanged.emit()

    @Property(float, notify=editorialChanged)
    def archiveSplit(self) -> float:
        return float(self._archive_split)

    @Slot(float)
    def setArchiveSplit(self, ratio: float) -> None:
        try:
            value = float(ratio)
        except (TypeError, ValueError):
            return
        value = max(0.32, min(0.68, value))
        if abs(value - float(self._archive_split)) < 0.001:
            return
        self._archive_split = value
        update_prefs(self._prefs_store(), **{KEY_ARCHIVE_SPLIT: value})
        self.editorialChanged.emit()

    @Property(str, notify=editorialChanged)
    def calendarYear(self) -> str:
        return (self._calendar_month or "")[:4]

    @Property(str, notify=editorialChanged)
    def revealedDay(self) -> str:
        return self._revealed_day

    @Property(int, notify=editorialChanged)
    def undatedCount(self) -> int:
        return int(self._undated_count)

    @Property(str, notify=editorialChanged)
    def libraryWorkspace(self) -> str:
        """``calendar`` fills the library. ``grid`` replaces it with photos."""
        return self._library_workspace

    @Property(str, notify=editorialChanged)
    def gridTitle(self) -> str:
        if self._person_field_filter and self._person_field_label:
            return str(self._person_field_label)
        if self._scope_kind == "day":
            if self._scope_label == UNDATED_DAY:
                return "Unknown day"
            return day_section_short_label(self._scope_label) or self._scope_label or "Day"
        if self._scope_kind == "folder":
            return self._scope_label or "Folder"
        if self._scope_kind == "month":
            return month_heading(self._scope_label + "-01") or self._scope_label
        if self._scope_kind == "year":
            return self._scope_label or "Year"
        if self._scope_kind == "range":
            return self._scope_label.replace(":", " – ")
        if self._grid_title:
            return self._grid_title
        if self._media_kind == "photo":
            return "Photos"
        if self._media_kind == "video":
            return "Videos"
        return "Everything"

    @Property("QVariantList", notify=editorialChanged)
    def yearMatrix(self):
        return list(self._year_matrix)

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
        if not self._session.focus_id:
            return "Open a photo first, then find similar memories."
        if self._region_norm:
            return "Search the highlighted area for a similar region."
        return "Draw a region on the photo, then search that area."

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
        """Update the sticky heading and follow the visible month. Scope stays."""
        text = str(day or "").strip()
        heading = month_heading(text)
        heading_changed = heading != self._sticky_heading
        if heading_changed:
            self._sticky_heading = heading
        month = text[:7] if len(text) >= 7 and text[4:5] == "-" else ""
        if month and month != self._calendar_month:
            self._sync_calendar_month(month)
            return
        if heading_changed:
            self.editorialChanged.emit()

    @Slot(int, bool, bool, result="QVariantMap")
    def rollLayout(self, columns: int, grouped: bool, dayRows: bool):
        """Months, day dividers and rows of pictures for the Roll. Counts are per section."""
        from semblon.native_shell.sections import build_sections

        return build_sections(self._model.days(), int(columns), grouped=bool(grouped), day_rows=bool(dayRows))

    @Slot(int, result="QVariantMap")
    def cellInfo(self, index: int):
        return self._model.row_info(int(index))

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
        self._grid_title = ""
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
            self._library_workspace = "grid"
            self._grid_title = basis_label or basis or "Search"
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

    @Property(str, notify=lensChanged)
    def okColor(self) -> str:
        return tokens_for(self._atmosphere_id)["ok"]

    @Property(str, notify=lensChanged)
    def warnColor(self) -> str:
        return tokens_for(self._atmosphere_id)["warn"]

    @Property(bool, notify=lensChanged)
    def screenQueryAvailable(self) -> bool:
        return sys.platform == "win32"

    @Property(bool, notify=screenQueryChanged)
    def screenQueryInProgress(self) -> bool:
        return self._screen_query_state in {"selecting", "searching"}

    @Property(str, notify=screenQueryChanged)
    def screenQueryState(self) -> str:
        return self._screen_query_state

    @Property(str, notify=screenQueryChanged)
    def screenQueryProgressLabel(self) -> str:
        if self._screen_query_state == "selecting":
            return "Pick on screen in progress: drag a box on your screen."
        if self._screen_query_state == "searching":
            return "Pick on screen: searching your photos."
        return ""

    @Property(str, notify=screenQueryChanged)
    def screenQueryMode(self) -> str:
        return self._screen_query_mode

    @Property(str, notify=screenQueryChanged)
    def screenQueryModeLabel(self) -> str:
        if self._screen_query_mode == SCREEN_QUERY_MODE_TEXT_PRIORITY:
            return "Text first — read the words on screen"
        return "Picture first — match the look on screen"

    @Slot()
    def toggleScreenQueryMode(self) -> None:
        if self.screenQueryInProgress:
            self._apply_result(Result("unavailable", "Semblon is already looking at the screen."))
            return
        nxt = (
            SCREEN_QUERY_MODE_TEXT_PRIORITY
            if self._screen_query_mode == SCREEN_QUERY_MODE_VISUAL
            else SCREEN_QUERY_MODE_VISUAL
        )
        self.setScreenQueryMode(nxt)

    @Slot(str)
    def setScreenQueryMode(self, mode: str) -> None:
        raw = str(mode or "").strip().lower().replace("-", "_")
        if raw in {"text", "ocr"}:
            raw = SCREEN_QUERY_MODE_TEXT_PRIORITY
        if raw not in SCREEN_QUERY_MODES:
            raw = SCREEN_QUERY_MODE_VISUAL
        if raw == self._screen_query_mode:
            return
        self._screen_query_mode = raw
        self._save_screen_query_mode(raw)
        self.screenQueryChanged.emit()
        self._apply_result(Result("ready", f"{self.screenQueryModeLabel}."))

    @Property(str, notify=peopleChanged)
    def reviewCountText(self) -> str:
        return self._review_text

    @Property(str, notify=peopleChanged)
    def unresolvedText(self) -> str:
        return self._unresolved_text

    @Property(str, notify=surfaceChanged)
    def searchModeLabel(self) -> str:
        return self._adapter.search_mode().message

    @Property(str, notify=surfaceChanged)
    def searchQuality(self) -> str:
        return str(self._adapter.search_quality().data.get("quality") or "balanced")

    @Property(str, notify=surfaceChanged)
    def searchQualityLabel(self) -> str:
        return str(self._adapter.search_quality().data.get("label") or "Balanced")

    @Property(str, notify=selectionChanged)
    def refineMode(self) -> str:
        return self._refine_mode

    @Property(str, notify=selectionChanged)
    def refineModeLabel(self) -> str:
        from semblon.query_spec import mode_label

        return mode_label(self._refine_mode)

    @Property(str, notify=selectionChanged)
    def refineHint(self) -> str:
        from semblon.query_spec import QuerySpec, refine_hint

        return refine_hint(
            QuerySpec(
                mode=self._refine_mode,
                modifier=self._refine_modifier,
                part_index=self._refine_part_index,
            )
        )

    @Property(str, notify=selectionChanged)
    def refineModifier(self) -> str:
        return self._refine_modifier

    @Property(int, notify=selectionChanged)
    def refinePartIndex(self) -> int:
        return int(self._refine_part_index)

    @Property("QVariantList", notify=selectionChanged)
    def refineParts(self) -> list:
        return list(self._refine_parts)

    @Slot(str)
    def setRefineMode(self, mode: str) -> None:
        from semblon.query_spec import MODE_KIND, normalize_mode

        key = normalize_mode(mode)
        if key == self._refine_mode:
            return
        self._refine_mode = key
        self.selectionChanged.emit()
        note = (
            "Search looks at the same kind of thing."
            if key == MODE_KIND
            else "Search looks at the same thing."
        )
        self._apply_result(Result("ready", note))
        if self.selectionOnFocus:
            self.findSimilar()

    @Slot(str)
    def setRefineModifier(self, word: str) -> None:
        from semblon.query_spec import normalize_modifier

        text = normalize_modifier(word)
        if text == self._refine_modifier:
            return
        self._refine_modifier = text
        self.selectionChanged.emit()
        if text:
            self._apply_result(Result("ready", f"Search looks at photos with the word {text}."))
        else:
            self._apply_result(Result("ready", "Search looks at the highlighted area."))
        if self.selectionOnFocus:
            self.findSimilar()

    @Slot(int)
    def setRefinePart(self, index: int) -> None:
        from semblon.region_parts import select_part

        try:
            part_index = int(index)
        except (TypeError, ValueError):
            part_index = -1
        self._refine_part_index = part_index
        chosen = select_part(self._refine_parts, part_index)
        norm = chosen.get("norm") if isinstance(chosen, dict) else None
        if isinstance(norm, (list, tuple)) and len(norm) == 4:
            self._region_norm = (
                max(0.0, min(1.0, float(norm[0]))),
                max(0.0, min(1.0, float(norm[1]))),
                max(0.0, min(1.0, float(norm[2]))),
                max(0.0, min(1.0, float(norm[3]))),
            )
        self.selectionChanged.emit()
        label = str(chosen.get("label") or "Whole area")
        self._apply_result(Result("ready", f"Showing {label}."))
        if self.selectionOnFocus:
            self.findSimilar()

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

    @Property(bool, notify=similarChanged)
    def installSuggestionVisible(self) -> bool:
        return bool(self._install_suggestion)

    @Property(str, notify=similarChanged)
    def installSuggestionLabel(self) -> str:
        return self._install_suggestion_label or "Get this ready"

    @Property(str, notify=similarChanged)
    def similarPhase(self) -> str:
        """first, refined, fast, or kept. Empty when this search has no phase."""
        return self._similar_phase

    @Property(str, notify=similarChanged)
    def similarPhaseLabel(self) -> str:
        return _PHASE_LABELS.get(self._similar_phase, "")

    @Property(str, notify=similarChanged)
    def selectionNote(self) -> str:
        """How the current box was chosen. Plain language, not a model id."""
        return self._selection_note

    @Property(str, notify=nameChanged)
    def nameNote(self) -> str:
        """Local name for the highlighted area. Empty until Name this area runs."""
        return self._name_note

    @Property(str, notify=nameChanged)
    def nameConfidenceLabel(self) -> str:
        """Model score for the name. Empty when the name abstains or has no score."""
        return self._name_confidence

    @Property(bool, notify=nameChanged)
    def identifyBusy(self) -> bool:
        return self._identify_busy

    @Property(str, notify=doorChanged)
    def searchDoorLabel(self) -> str:
        """Which Focus door is open: Similar region, Same face, Whole photo, or Duplicates."""
        return _DOOR_LABELS.get(self._search_door, "")

    @Property(str, notify=similarChanged)
    def searchTimingLabel(self) -> str:
        """Time to the first visible look, then time to the refined result."""
        if self._search_first_ms < 0:
            return ""
        if self._search_refined_ms < 0:
            return f"First look {self._search_first_ms} ms."
        return f"First look {self._search_first_ms} ms. Refined {self._search_refined_ms} ms."

    @Property(bool, notify=similarChanged)
    def canBackDiscovery(self) -> bool:
        return bool(self._discovery_trail)

    def _discovery_file(self) -> Path:
        store = Path(self._jobs.store)
        return store.with_name(store.stem + ".visual-discovery.json")

    def _atomic_write_json(self, path: Path, payload: object) -> None:
        """tmp → fsync → replace. Keeps sidecars readable after a crash mid-write."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

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
            self._atomic_write_json(self._discovery_file(), payload)
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
        if len(self._discovery_trail) > 20:
            self._discovery_trail = self._discovery_trail[-20:]

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
        if item.day:
            self._revealed_day = item.day
            if len(item.day) >= 7:
                self._sync_calendar_month(item.day[:7])
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
        self.focusMatchZoomRequested.emit()

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
        self._grid_title = ""
        self._library_workspace = "grid"
        self._select_scope("day", day)

    @Slot()
    def reopenLastVisualSearch(self) -> None:
        path = self._discovery_file()
        if not path.is_file():
            note = "Similar (Similar look): no saved search yet."
            self._publish_similar(
                "empty",
                note,
                [],
                basis="region",
                basis_label="Similar look",
            )
            self._apply_result(Result("empty", note))
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            note = "Similar (Similar look): the saved search could not be read."
            self._publish_similar(
                "unavailable",
                note,
                [],
                basis="region",
                basis_label="Similar look",
            )
            self._apply_result(Result("unavailable", note))
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
        note = str(payload.get("note") or "Similar (Similar look): restored.")
        state = str(payload.get("state") or ("ready" if rows else "empty"))
        self._publish_similar(
            state,
            note,
            rows,
            basis=str(payload.get("basis") or "region"),
            basis_label=str(payload.get("basis_label") or "Similar look"),
        )
        if not self._session.focus_id:
            self._apply_result(Result(state if state in {"ready", "empty", "unavailable"} else "ready", note))

    @Slot()
    def cancelSimilar(self) -> None:
        self._stop_search(publish=True)

    def _stop_search(self, *, publish: bool) -> None:
        self._search_generation += 1
        if self._cancel_flag is not None:
            self._cancel_flag[0] = True
        self._similar_cancel = True
        self._set_screen_query_state("idle")
        was_busy = self._search_busy
        self._search_busy = False
        if was_busy:
            self.searchBusyChanged.emit()
        if not publish:
            return
        label = self._similar_basis_label or "Similar look"
        if self._similar_phase == "first" and self._similar.rowCount() > 0:
            self._similar_phase = "kept"
            self._similar_state = "ready"
            self._similar_note = present_message(
                self._mode,
                f"Similar ({label}): kept the first look.",
                fallback="Similar search could not run.",
            )
            self.similarChanged.emit()
            self._persist_discovery()
            return
        self._publish_similar(
            "empty",
            f"Similar ({label}): cancelled.",
            [],
            basis=self._similar_basis or "region",
            basis_label=label,
            persist=False,
            phase="",
        )

    def _start_visual_search(self, *, basis: str, label: str, build) -> None:
        """Publish looking immediately, then run build(cancel_flag, report) off the UI thread."""
        if self._cancel_flag is not None:
            self._cancel_flag[0] = True
        self._set_install_suggestion("", "")
        self._search_generation += 1
        generation = self._search_generation
        flag = [False]
        self._cancel_flag = flag
        self._similar_cancel = False
        self._similar_phase = ""
        self._search_failure = ""
        self._search_started = time.monotonic()
        self._search_first_ms = -1
        self._search_refined_ms = -1
        self._search_busy = True
        self.searchBusyChanged.emit()
        kept = list(self._similar._rows)
        self._publish_similar(
            "loading",
            f"Similar ({label}): looking through photos Semblon has already seen.",
            kept,
            basis=basis,
            basis_label=label,
            persist=False,
            phase="",
        )
        thread = _VisualSearchThread(generation, lambda report: build(flag, report), self)
        thread.succeeded.connect(self._on_visual_search)
        thread.progressed.connect(self._on_visual_progress)
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
    def _on_visual_progress(self, generation: int, payload) -> None:
        if generation != self._search_generation or self._similar_cancel or payload is None:
            return
        if isinstance(payload, Result):
            result = payload
        else:
            result = self._safe_call(lambda: self._adapter.similar_region(payload))
        self._publish_similar_result(result, interim=True)

    @Slot(int, object)
    def _on_visual_search(self, generation: int, payload) -> None:
        if generation != self._search_generation:
            return
        self._set_screen_query_state("idle")
        self._search_busy = False
        self.searchBusyChanged.emit()
        if payload is None or self._similar_cancel:
            if self._similar_phase == "first" and self._similar.rowCount() > 0:
                return
            self._publish_similar(
                "empty",
                f"Similar ({self._similar_basis_label or 'Similar look'}): cancelled.",
                [],
                basis=self._similar_basis or "region",
                basis_label=self._similar_basis_label or "Similar look",
                persist=False,
                phase="",
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
        self._set_screen_query_state("idle")
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
            phase="",
        )

    def _refresh_index_note(self) -> None:
        media_id = self._session.focus_id or ""
        now = time.monotonic()
        if (
            self._job_active
            and media_id == self._index_note_media
            and now - self._index_note_at < 0.5
        ):
            return
        self._index_note_at = now
        self._index_note_media = media_id
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
        cache_key = (media_id, self._index_stamp())
        if not self._job_active and cache_key in self._index_cache:
            return self._index_cache[cache_key]
        patch = 0
        coarse = 0
        try:
            store = Path(self._jobs.store)
            conn = connect_readonly(store.resolve())
            conn.execute("PRAGMA busy_timeout=80")
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
            if self._job_active:
                return "indexing", "Still looking through your photos. Ones already added can be opened."
            return "unknown", ""
        if patch > 0 and self._job_active:
            result = ("patch", "Still looking through your photos. This one can already be searched.")
        elif patch > 0:
            result = ("patch", "")
        elif self._job_active:
            result = ("indexing", "Still looking through your photos. Ones already added can be opened.")
        elif coarse > 0:
            result = (
                "fallback",
                "Semblon has only had a quick look at this photo. Matches may miss the area you point at.",
            )
        else:
            result = (
                "unindexed",
                "Semblon has not looked at this photo yet. Add its folder so search can see inside it.",
            )
        if not self._job_active:
            if len(self._index_cache) > 256:
                self._index_cache.clear()
            self._index_cache[cache_key] = result
        return result

    def _index_stamp(self) -> tuple[int, int]:
        """Main file and WAL times. A commit changes one of them, so the note is not stuck."""
        store = Path(self._jobs.store)
        try:
            main = int(store.stat().st_mtime_ns)
        except OSError:
            main = 0
        wal = Path(str(store) + "-wal")
        try:
            side = int(wal.stat().st_mtime_ns) if wal.is_file() else 0
        except OSError:
            side = 0
        return main, side

    @Property(int, notify=similarChanged)
    def similarCount(self) -> int:
        return self._similar.rowCount()

    @property
    def similar_model(self) -> SimilarStripModel:
        return self._similar

    @Property(bool, notify=similarChanged)
    def matchesOnRoll(self) -> bool:
        return self._matches_prior is not _NO_MATCHES

    @Slot()
    def showMatchesOnRoll(self) -> None:
        """Lay the current matches out on the Roll, best first. Nothing is written."""
        ids = [self._similar.media_id(row) for row in range(self._similar.rowCount())]
        ids = [item for item in ids if item]
        if not ids:
            return
        if self._matches_prior is _NO_MATCHES:
            self._matches_prior = self._model.media_ids()
        self._model.set_media_ids(ids)
        self.similarChanged.emit()

    @Slot()
    def clearMatches(self) -> None:
        if self._matches_prior is _NO_MATCHES:
            return
        prior = self._matches_prior
        self._matches_prior = _NO_MATCHES
        self._model.set_media_ids(prior)
        self.similarChanged.emit()

    @Slot(str, result="QVariantMap")
    def dayDetail(self, day: str):
        """A day's photos, face count and named people in one read for the Roll."""
        return day_detail(self._prefs_store(), day)

    @Slot(str)
    def addFolderPath(self, folder: str) -> None:
        """Add a folder that was dropped on the window. Files stay where they are."""
        text = str(folder or "").strip()
        if text.startswith("file:"):
            text = QUrl(text).toLocalFile()
        path = Path(text) if text else None
        if path is None or not path.is_dir():
            self._apply_result(
                Result("unavailable", "That is not a folder. Drop a folder of photos, or use Add a folder.")
            )
            return
        if self._jobs.busy:
            return
        self._start_ingest(path)

    @Property(float, notify=jobChanged)
    def jobFraction(self) -> float:
        total = int(self._progress_total)
        if total <= 0:
            return 0.0
        return max(0.0, min(1.0, float(self._progress_current) / float(total)))

    def _set_result(self, text: str) -> None:
        self._result_text = present_message(self._mode, text, fallback="Nothing was searched.")
        self.resultChanged.emit()

    def _clear_similar(self) -> None:
        self._similar.set_rows([])
        self._similar_state = "idle"
        self._similar_note = ""
        self._similar_basis = ""
        self._similar_basis_label = ""
        self._similar_phase = ""
        self._set_install_suggestion("", "")
        self.similarChanged.emit()

    def _set_install_suggestion(self, action: str, label: str = "") -> None:
        next_action = str(action or "")
        next_label = str(label or "")
        if (
            next_action == self._install_suggestion
            and next_label == self._install_suggestion_label
        ):
            return
        self._install_suggestion = next_action
        self._install_suggestion_label = next_label
        self.similarChanged.emit()

    def _set_screen_query_state(self, state: str) -> None:
        next_state = str(state or "").strip().lower()
        if next_state not in {"idle", "selecting", "searching"}:
            next_state = "idle"
        if next_state == self._screen_query_state:
            return
        self._screen_query_state = next_state
        self.screenQueryChanged.emit()

    def _publish_similar(
        self,
        state: str,
        note: str,
        rows: list,
        *,
        basis: str = "",
        basis_label: str = "",
        persist: bool = True,
        phase: str = "",
    ) -> None:
        # Rows are (media_id, score) or (media_id, score, nx, ny, nw, nh).
        self._similar.set_rows(rows)
        self._similar_state = state
        self._similar_note = present_message(self._mode, note, fallback="Similar search could not run.")
        self._similar_basis = str(basis or "")
        self._similar_basis_label = str(basis_label or "")
        self._similar_phase = str(phase or "")
        self.similarChanged.emit()
        if persist and state in {"ready", "empty"}:
            self._persist_discovery()

    def _match_for_media(self, media_id: str) -> tuple[float, float, float, float]:
        wanted = str(media_id or "")
        if not wanted:
            return 0.0, 0.0, 0.0, 0.0
        for row in self._similar._rows:
            if str(row[0]) != wanted or len(row) < 6:
                continue
            if float(row[4]) > 0 and float(row[5]) > 0:
                return float(row[2]), float(row[3]), float(row[4]), float(row[5])
        return 0.0, 0.0, 0.0, 0.0

    def _match_for_focus(self) -> tuple[float, float, float, float]:
        return self._match_for_media(self._session.focus_id or "")

    @Slot(str, result="QVariantList")
    def matchNormFor(self, media_id: str):
        """Normalized match box for a strip hit (Focus overlay / preview)."""
        return list(self._match_for_media(media_id))

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
        parts.append(self.searchQualityLabel)
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

    def _write_keeps(self, rows: list[dict]) -> bool:
        try:
            self._atomic_write_json(self._keeps_file(), rows)
        except OSError:
            return False
        self.keepsChanged.emit()
        return True

    def _recent_keeps(self) -> list[dict]:
        return list(reversed(self._read_keeps()[-8:]))

    def _kept_file_index(self, recent_index: int) -> int | None:
        rows = self._read_keeps()
        recent = list(reversed(rows[-8:]))
        if recent_index < 0 or recent_index >= len(recent):
            return None
        target = recent[recent_index]
        kept_id = str(target.get("kept_id") or "")
        if kept_id:
            for i, row in enumerate(rows):
                if str(row.get("kept_id") or "") == kept_id:
                    return i
        for i, row in enumerate(rows):
            if row == target:
                return i
        return None

    @Property(int, notify=keepsChanged)
    def keptCount(self) -> int:
        return len(self._recent_keeps())

    @Slot(int, result=str)
    def keptName(self, index: int) -> str:
        """Display name only (for rename field)."""
        rows = self._recent_keeps()
        if index < 0 or index >= len(rows):
            return ""
        item = rows[index]
        return str(item.get("name") or item.get("understanding") or "Kept find").strip() or "Kept find"

    @Slot(int, result=str)
    def keptLabel(self, index: int) -> str:
        rows = self._recent_keeps()
        if index < 0 or index >= len(rows):
            return ""
        item = rows[index]
        label = str(item.get("name") or item.get("understanding") or "Kept find")
        count = len(item.get("items") or [])
        noun = "match" if count == 1 else "matches"
        return f"{label} · {count} {noun}"

    @Slot(result=str)
    def keepDiscovery(self) -> str:
        """Remember the open visual search beside the library. No new table."""
        if self._similar_state != "ready" or not self._similar._rows or not self._region_norm:
            return "Search a region before keeping a find."
        entry = {
            "kept_id": uuid.uuid4().hex[:12],
            "name": str(self._selection_note or "Kept find").strip() or "Kept find",
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
        if not self._write_keeps(rows):
            return "This find could not be kept."
        self._set_result("Kept this find.")
        return "Kept this find."

    @Slot(int, str, result=bool)
    def renameKept(self, index: int, name: str) -> bool:
        label = str(name or "").strip()
        if not label:
            return False
        file_index = self._kept_file_index(index)
        if file_index is None:
            return False
        rows = self._read_keeps()
        if file_index < 0 or file_index >= len(rows):
            return False
        rows[file_index]["name"] = label
        return self._write_keeps(rows)

    @Slot(int, result=bool)
    def deleteKept(self, index: int) -> bool:
        file_index = self._kept_file_index(index)
        if file_index is None:
            return False
        rows = self._read_keeps()
        if file_index < 0 or file_index >= len(rows):
            return False
        del rows[file_index]
        if not rows:
            path = self._keeps_file()
            try:
                path.unlink(missing_ok=True)
            except OSError:
                return False
            self.keepsChanged.emit()
            return True
        return self._write_keeps(rows)

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

    def _publish_similar_result(self, result, *, interim: bool = False) -> None:
        """Shared Focus strip publish for whole / region / face doors."""
        self._note_search_timing(final=not interim)
        understanding = str((result.data or {}).get("understanding") or "")
        if understanding and not interim:
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
        phase = str((result.data or {}).get("search_phase") or "")
        from semblon.optional_providers import install_choice

        parts = (result.data or {}).get("parts")
        if isinstance(parts, list) and parts:
            self._refine_parts = [row for row in parts if isinstance(row, dict)]
            self.selectionChanged.emit()
        install_action, install_label = install_choice(state, error_id, result.data or {})
        if interim:
            install_action, install_label = "", ""
            if phase == "detailed":
                if rows:
                    state = "ready"
                    note = f"Similar ({label}): sharpened with fine detail, still checking the top matches."
                else:
                    state = "loading"
                    note = f"Similar ({label}): sharpening with fine detail."
            elif phase == "refined":
                if rows:
                    state = "ready"
                    note = f"Similar ({label}): still checking the top matches."
                else:
                    state = "loading"
                    note = f"Similar ({label}): first look found nothing yet."
            else:
                phase = "first"
                if rows:
                    state = "ready"
                    note = f"Similar ({label}): first look, still refining."
                else:
                    state = "loading"
                    note = f"Similar ({label}): first look found nothing yet."
        elif phase == "checked" and state in {"ready", "empty"}:
            note = (
                f"Similar ({label}): checked the matches."
                if rows
                else f"Similar ({label}): nothing close enough."
            )
        elif install_action == "region_pack":
            note = f"Similar ({label}): finding by look isn't set up yet."
        elif install_action == "object_pack" and state == "unavailable":
            note = f"Similar ({label}): finding things in pictures isn't set up yet."
        elif install_action == "vlm_local" and state == "unavailable":
            note = f"Similar ({label}): photo descriptions aren't set up yet."
        elif state == "unavailable" and error_id == "region.NO_PATCH_INDEX":
            note = f"Similar ({label}): Semblon has not looked closely at these photos yet."
        elif error_id in {"region.ENCODE", "region.NO_IMAGE", "region.NO_STORE"}:
            state = "error"
            note = f"Similar ({label}): search failed."
        self._set_install_suggestion(install_action, install_label)
        self._result_text = ""
        self.resultChanged.emit()
        self._publish_similar(
            state,
            note,
            rows,
            basis=str(result.data.get("basis") or ""),
            basis_label=str(result.data.get("basis_label") or ""),
            persist=not interim,
            phase=phase,
        )

    def _clear_query(self) -> None:
        if self._search_busy:
            self._stop_search(publish=False)
        self._set_screen_query_state("idle")
        self._region_norm = None
        self._selection_kind = ""
        self._selection_note = ""
        self.selectionChanged.emit()
        self._drop_name()
        self._search_door = ""
        self.doorChanged.emit()
        self._result_text = ""
        self.resultChanged.emit()
        self._clear_similar()

    def _load_focus_boxes(self, media_id: str) -> None:
        """Observation outlines for the open still. Face click → face-similar; never stamps identity."""
        from semblon.canvas_data import overlay_boxes_for_media

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
            boxes = overlay_boxes_for_media(self._jobs.store, media_id)
        except Exception:
            return
        for box in boxes:
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
            # The day grid stays under the photo so Back lands on that day.
            self._revealed_day = day
            if len(day) >= 7:
                self._sync_calendar_month(day[:7])
            self._grid_title = ""
            self._library_workspace = "grid"
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

    @Property(str, notify=peopleChanged)
    def selectedLabel(self) -> str:
        row = self._people.row(self._selected_subject)
        return str(row.get("label") or "") if row else ""

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
        self._grid_title = title
        self._library_workspace = "grid"
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
                    from semblon.geometry import xyxy_to_xywh

                    return {
                        "path": member.get("path") or "",
                        "bbox": xyxy_to_xywh(bbox),
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
                        "faceCount": int(item.get("face_count") or len(members) or 0),
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
                    "faceCount": int(item.get("face_count") or 0),
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
        counts: dict[str, int] = {}
        for row in rows:
            row["faceIds"] = [str(m.get("face_id") or "") for m in row["members"] if m.get("face_id")][:3]
            row["label"] = self._friendly_label(row)
            if row["named"]:
                key = row["title"].strip().casefold()
                counts[key] = counts.get(key, 0) + 1
        for row in rows:
            row["twin"] = bool(row["named"]) and counts.get(row["title"].strip().casefold(), 0) > 1
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

    @staticmethod
    def _friendly_label(row: dict) -> str:
        if row["named"]:
            return row["title"]
        kind = str(row.get("kind") or "")
        if kind == "track":
            return "Face from a video"
        if kind == "unassigned":
            return "Single face"
        return "Unnamed group"

    def _same_name_row(self, subject: str, name: str) -> dict | None:
        key = str(name or "").strip().casefold()
        for row in self._people._rows:
            if row["subject"] != subject and row.get("named") and row["title"].strip().casefold() == key:
                return row
        return None

    @Slot()
    def escape(self) -> None:
        if self._tasks_open:
            self.closeTasks()
            return
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
        if self._session.focus_id:
            self._session.escape()
            self._clear_query()
            self._clear_focus_boxes()
            self.focusChanged.emit()
            self.diagnosticsChanged.emit()
            self.lensChanged.emit()
            return
        if self._library_workspace == "grid":
            self.showCalendar()
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
        if self._tasks_open:
            self._tasks_open = False
            self.tasksChanged.emit()
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

    @Slot()
    def startScreenQuery(self) -> None:
        """SQ-3: transient desktop selection routed into the same discovery strip."""
        if not self.screenQueryAvailable:
            self._publish_similar(
                "unavailable",
                "Pick on screen: only available on Windows.",
                [],
                basis="region",
                basis_label="Similar look",
                persist=False,
            )
            return
        if self._search_busy or self.screenQueryInProgress:
            self._apply_result(Result("unavailable", "A search is already running."))
            return
        self._set_screen_query_state("selecting")
        self._set_install_suggestion("", "")
        self._publish_similar(
            "loading",
            "Pick on screen in progress: drag a box on your screen.",
            [],
            basis="region",
            basis_label=(
                "Text in the selection"
                if self._screen_query_mode == SCREEN_QUERY_MODE_TEXT_PRIORITY
                else "Similar look"
            ),
            persist=False,
        )
        try:
            from semblon.native_shell.screen_query_overlay import (
                ScreenSelectionUnavailable,
                select_screen_region,
            )

            rect = select_screen_region()
        except ScreenSelectionUnavailable as exc:
            self._set_screen_query_state("idle")
            self._set_install_suggestion("", "")
            self._publish_similar(
                "unavailable",
                f"Pick on screen: {exc}",
                [],
                basis="region",
                basis_label="Similar look",
                persist=False,
            )
            return
        if rect is None:
            self._set_screen_query_state("idle")
            self._publish_similar(
                "empty",
                "Pick on screen cancelled.",
                [],
                basis="region",
                basis_label="Similar look",
                persist=False,
            )
            self._apply_result(Result("empty", "Stopped looking at the screen."))
            return
        self._begin_screen_search(rect)

    def _begin_screen_search(self, rect: tuple[int, int, int, int]) -> None:
        """Run retrieval for a screen rect already chosen. Does not open the drag overlay."""
        x, y, w, h = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
        self._screen_query_rect = (x, y, w, h)
        self._query_source = "screen"
        mode = self._screen_query_mode
        mode_selection = (
            SCREEN_QUERY_MODE_TEXT_PRIORITY
            if mode == SCREEN_QUERY_MODE_TEXT_PRIORITY
            else "region"
        )
        mode_label = "Text in the selection" if mode_selection == SCREEN_QUERY_MODE_TEXT_PRIORITY else "Similar look"
        self._query_focus_id = ""
        self._region_norm = None
        self._selection_kind = str(mode_selection)
        self._selection_note = (
            "You pointed at words on the screen."
            if mode_selection == SCREEN_QUERY_MODE_TEXT_PRIORITY
            else "You pointed at something on the screen."
        )
        self.selectionChanged.emit()
        adapter = self._adapter
        jobs = self._jobs
        self._set_screen_query_state("searching")

        def build(flag, _report):
            rec = jobs.query_screen(
                x,
                y,
                w,
                h,
                limit=10,
                selection_kind=mode_selection,
                cancelled=lambda: bool(flag[0]),
            )
            if flag[0]:
                return None
            similar = rec.get("similar")
            if not isinstance(similar, dict):
                reason = str(rec.get("reason") or "Screen capture did not run. Nothing was searched.")
                return Result(
                    "unavailable",
                    f"Similar ({mode_label}): {reason}",
                    {
                        "basis": "region",
                        "basis_label": mode_label,
                        "engine": "screen",
                        "items": [],
                        "error_id": "screen.NO_CAPTURE",
                        "optional_providers": rec.get("optional_providers")
                        if isinstance(rec.get("optional_providers"), list)
                        else [],
                    },
                )
            result = adapter.similar_region(
                {"similar": similar, "optional_providers": rec.get("optional_providers")}
            )
            lines = rec.get("lines") or []
            observations = rec.get("observations") if isinstance(rec.get("observations"), list) else []
            understanding = _screen_understanding(lines, observations)
            data = dict(result.data or {})
            if understanding:
                data["understanding"] = understanding
            if observations:
                data["observations"] = observations
            if isinstance(rec.get("optional_providers"), list) and "optional_providers" not in data:
                data["optional_providers"] = rec.get("optional_providers")
            return Result(result.state, result.message, data)

        self._start_visual_search(basis="region", label=mode_label, build=build)

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
        self._refine_part_index = -1
        self._drop_name()
        self.selectionChanged.emit()
        self.surfaceChanged.emit()

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
                twin = None if self._name_apart else self._same_name_row(subject, text)
                own = self._people.row(subject)
                if twin and not (own and own.get("named") and own.get("personId") == twin.get("personId")):
                    self._ask_same_name(subject, text.strip(), twin)
                    return self._people_note
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
                a, b = self._people.row(subject), self._people.row(other)
                if a and b and a.get("named") and b.get("named") and a.get("personId") != b.get("personId"):
                    return self._after_decision(
                        "These are two named people, so Semblon will not join them. Rename one to tell them apart."
                    )
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

    def _ask_same_name(self, subject: str, name: str, twin: dict) -> None:
        count = int(twin.get("faceCount") or 0)
        self._ask(
            f"You already have someone called {name}",
            f"One group is already named {name}, with {count} {'photo' if count == 1 else 'photos'}. Is this the same person?",
            ["Same person puts the two groups together.", "Someone else keeps both, so you can tell them apart."],
            yes="Same person",
            no="Someone else",
            on_yes=lambda: self.decide("merge", str(twin["subject"]), subject),
            on_no=lambda: self._name_as_someone_else(subject, name),
            dismiss_is_no=False,
        )

    def _name_as_someone_else(self, subject: str, name: str) -> None:
        self._name_apart = True
        try:
            self.decide("name", subject, name)
        finally:
            self._name_apart = False

    @Slot(str, result=str)
    def sameAs(self, target: str) -> str:
        """The single 'Same as…' picker: the selected group is the same as `target`."""
        if not self._selected_subject or not target or target == self._selected_subject:
            return self._after_decision("Pick a different group to say this is the same.")
        named_target = bool((self._people.row(target) or {}).get("named"))
        first, second = (target, self._selected_subject) if named_target else (self._selected_subject, target)
        return self.decide("merge", first, second)

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
                label = str(row.get("label") or "group")
                self._scope_kind = ""
                self._scope_label = ""
                self._field_sections = []
                self._grid_title = label
                self._library_workspace = "grid"
                self._model.set_media_ids(list(row.get("media_ids") or []))
                self.editorialChanged.emit()
                self._apply_result(Result("ready", f"Showing {label}."))
                return

    @Slot(str)
    def setSearchMode(self, mode: str) -> None:
        self._apply_result(self._safe_call(lambda: self._adapter.set_search_mode(mode)))
        self.surfaceChanged.emit()

    @Slot(str)
    def setSearchQuality(self, value: str) -> None:
        self._apply_result(self._safe_call(lambda: self._adapter.set_search_quality(value)))
        self.surfaceChanged.emit()
        self.similarChanged.emit()

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
        self._set_door("duplicate")
        if os.environ.get("SEMBLON_SEARCH_SYNC") == "1":
            self._finish_scan(self._safe_call(self._adapter.duplicates))
            return
        if self._tidy_thread is not None:
            return
        self._tidy_busy = True
        self._tidy_pct = 0
        self.tidyChanged.emit()
        thread = _TaskThread(lambda: self._adapter.duplicates(self._scan_tick), self)
        thread.succeeded.connect(self._on_scan_done)
        thread.failed.connect(self._on_scan_failed)
        self._tidy_thread = thread
        thread.start()

    def _finish_scan(self, result: Result) -> None:
        self._tidy_busy = False
        self._tidy_picks = set()
        self._tidy_sets = self._build_tidy_sets(result.data.get("report") or {})
        self.tidyChanged.emit()
        self._apply_result(result)

    @Slot(object)
    def _on_scan_done(self, payload) -> None:
        self._tidy_thread = None
        self._finish_scan(payload if isinstance(payload, Result) else Result("ready", "Done."))

    @Slot(str)
    def _on_scan_failed(self, _message: str) -> None:
        self._tidy_thread = None
        self._finish_scan(Result("error", "Could not look for copies. Your photos were not changed."))

    def _scan_tick(self, phase: int, i: int, total: int) -> None:
        # Runs on the worker thread: only emit, and only now and then.
        if total <= 0 or (i % 25 and i != total):
            return
        self._scanProgress.emit(min(99, (phase * 50) + int(50 * i / total)))

    @Slot(int)
    def _on_scan_progress(self, pct: int) -> None:
        if self._tidy_busy and pct != self._tidy_pct:
            self._tidy_pct = pct
            self.tidyChanged.emit()

    @Property(int, notify=tidyChanged)
    def tidyPercent(self) -> int:
        return self._tidy_pct

    @Property(bool, notify=tidyChanged)
    def tidyBusy(self) -> bool:
        return self._tidy_busy

    @Slot()
    def openTidy(self) -> None:
        """Tidy up: look for copies and show them side by side. Nothing is removed here."""
        self.scanDuplicates()
        self._tidy_open = True
        self.tidyChanged.emit()

    @Slot()
    def closeTidy(self) -> None:
        if self._tidy_open:
            self._tidy_open = False
            self.tidyChanged.emit()

    @Property(bool, notify=tidyChanged)
    def tidyOpen(self) -> bool:
        return self._tidy_open

    @Property("QVariantList", notify=tidyChanged)
    def tidySets(self):
        rows = [
            dict(g, id=i) for i, g in enumerate(self._tidy_sets)
            if (g["exact"] and self._tidy_exact_on) or (not g["exact"] and self._tidy_near_on)
        ]
        key = self._tidy_sort
        if key == "size":
            rows.sort(key=lambda g: -max(m.get("bytes", 0) for m in g["members"]))
        elif key == "name":
            rows.sort(key=lambda g: min(m["path"].lower() for m in g["members"]))
        elif key == "time":
            rows.sort(key=lambda g: -max(m.get("mtime", 0) for m in g["members"]))
        else:
            rows.sort(key=lambda g: -len(g["members"]))
        picked = self._tidy_picks
        for g in rows:
            g["members"] = [dict(m, picked=m["path"] in picked) for m in g["members"]]
        return rows

    @Property(bool, notify=tidyChanged)
    def tidyExactOn(self) -> bool:
        return self._tidy_exact_on

    @Property(bool, notify=tidyChanged)
    def tidyNearOn(self) -> bool:
        return self._tidy_near_on

    @Property(str, notify=tidyChanged)
    def tidySort(self) -> str:
        return self._tidy_sort

    @Property(int, notify=tidyChanged)
    def tidyPickedCount(self) -> int:
        return len(self._tidy_picks)

    @Slot()
    def toggleTidyExact(self) -> None:
        if self._tidy_exact_on and not self._tidy_near_on:
            return  # one kind always stays on
        self._tidy_exact_on = not self._tidy_exact_on
        self.tidyChanged.emit()

    @Slot()
    def toggleTidyNear(self) -> None:
        if self._tidy_near_on and not self._tidy_exact_on:
            return
        self._tidy_near_on = not self._tidy_near_on
        self.tidyChanged.emit()

    @Slot(str)
    def setTidySort(self, key: str) -> None:
        if key in ("copies", "size", "name", "time") and key != self._tidy_sort:
            self._tidy_sort = key
            self.tidyChanged.emit()

    @Slot(str)
    def toggleTidyPick(self, path: str) -> None:
        if path in self._tidy_picks:
            self._tidy_picks.discard(path)
        else:
            self._tidy_picks.add(path)
        self.tidyChanged.emit()

    @Slot()
    def clearTidyPicks(self) -> None:
        if self._tidy_picks:
            self._tidy_picks = set()
            self.tidyChanged.emit()

    @Slot()
    def pickAllButFirst(self) -> None:
        """Tick every copy except the first of each set that is showing."""
        picks = set(self._tidy_picks)
        for g in self.tidySets:
            for m in g["members"][1:]:
                picks.add(m["path"])
        self._tidy_picks = picks
        self.tidyChanged.emit()

    @Slot()
    def binPicked(self) -> None:
        """Move the ticked copies to the Recycle Bin, after a plain confirm. Never all of a set."""
        picked = set(self._tidy_picks)
        if not picked:
            return
        for g in self._tidy_sets:
            if g["members"] and all(m["path"] in picked for m in g["members"]):
                self._apply_result(Result("error", "Keep at least one copy in each set. Untick one and try again."))
                return
        names = [m["name"] + " (" + m["folder"] + ")" for g in self._tidy_sets for m in g["members"] if m["path"] in picked]
        n = len(names)
        self._ask(
            f"Bin {n} {'photo' if n == 1 else 'photos'}?",
            f"{'It goes' if n == 1 else 'They go'} to the Recycle Bin, where you can still get "
            f"{'it' if n == 1 else 'them'} back. The copies you did not tick stay where they are.",
            names[:12],
            yes="Move to the Recycle Bin" if n == 1 else f"Move {n} to the Recycle Bin",
            no="Keep them all",
            danger=True,
            on_yes=lambda: self._bin_picked(picked),
        )

    def _bin_picked(self, picked: set) -> None:
        from PySide6.QtCore import QFile

        binned: list[str] = []
        failed = 0
        for path in sorted(picked):
            if QFile.moveToTrash(path):
                binned.append(path)
            else:
                failed += 1
        if binned:
            from ..forget import forget_files

            keep = [m["path"] for g in self._tidy_sets for m in g["members"] if m["path"] not in picked]
            try:
                forget_files(self._adapter.store, binned, keep=keep)
            except Exception:
                pass
            self._refresh_library()
        gone = set(binned)
        for g in self._tidy_sets:
            g["members"] = [m for m in g["members"] if m["path"] not in gone]
        self._tidy_sets = [g for g in self._tidy_sets if len(g["members"]) >= 2]
        self._tidy_picks = {p for p in self._tidy_picks if p not in gone}
        self.tidyChanged.emit()
        if failed:
            self._apply_result(Result("error", "Some photos could not be moved. They are still where they were."))
        else:
            self._apply_result(Result("ready", "Moved the ticked photos to the Recycle Bin."))

    @Property(str, notify=tidyChanged)
    def tidySummary(self) -> str:
        if self._tidy_busy:
            return f"Looking for copies, {self._tidy_pct}% done. You can keep using Semblon."
        sets = self.tidySets
        n = len(sets)
        if n == 0:
            hidden = len(self._tidy_sets)
            if hidden:
                kind = "near" if self._tidy_exact_on and not self._tidy_near_on else "exact"
                return f"No {'exact' if kind == 'near' else 'near'} copies. Turn on {kind} copies to see {hidden} more."
            return "No copies found. Your archive is already tidy."
        exact = sum(1 for g in sets if g["exact"])
        near = n - exact
        parts = []
        if exact:
            parts.append(f"{exact} {'set' if exact == 1 else 'sets'} of exact copies")
        if near:
            parts.append(f"{near} {'set' if near == 1 else 'sets'} of near copies")
        return ", ".join(parts)

    @staticmethod
    def _build_tidy_sets(report: dict) -> list[dict]:
        out: list[dict] = []
        for g in report.get("groups") or []:
            members = []
            for m in g.get("members") or []:
                path = str(m.get("path") or "")
                mid = str(m.get("media_id") or "")
                if not path:
                    continue
                p = Path(path)
                try:
                    st = p.stat()
                    size, mtime = st.st_size, int(st.st_mtime)
                except OSError:
                    size, mtime = 0, 0
                members.append({
                    "mediaId": mid,
                    "thumb": f"image://archive/t/{mid}" if mid else "",
                    "name": p.name,
                    "folder": p.parent.name,
                    "path": path,
                    "bytes": size,
                    "mtime": mtime,
                    "when": time.strftime("%d %b %Y", time.localtime(mtime)) if mtime else "",
                    "size": f"{size / 1_000_000:.1f} MB" if size >= 100_000 else f"{max(size // 1000, 0)} KB",
                })
            if len(members) >= 2:
                out.append({
                    "exact": str(g.get("kind") or "") == "exact",
                    "sha256": str(g.get("content_hash") or "") if str(g.get("kind") or "") == "exact" else "",
                    "members": members,
                })
        return out

    @Slot(int, int)
    def keepCopy(self, set_index: int, member_index: int) -> None:
        """Keep one copy. The others go to the Recycle Bin only after a plain confirm."""
        if not (0 <= set_index < len(self._tidy_sets)):
            return
        members = self._tidy_sets[set_index]["members"]
        if not (0 <= member_index < len(members)):
            return
        others = [m for i, m in enumerate(members) if i != member_index]
        n = len(others)
        self._ask(
            f"Keep this one and bin {n} {'copy' if n == 1 else 'copies'}?",
            f"{members[member_index]['name']} stays where it is. "
            f"The other {'copy goes' if n == 1 else 'copies go'} to the Recycle Bin, where you can still get "
            f"{'it' if n == 1 else 'them'} back.",
            [m["name"] + " (" + m["folder"] + ")" for m in others],
            yes="Move to the Recycle Bin" if n == 1 else f"Move {n} to the Recycle Bin",
            no="Keep them all",
            danger=True,
            on_yes=lambda: self._bin_copies(set_index, member_index),
        )

    def _bin_copies(self, set_index: int, member_index: int) -> None:
        from PySide6.QtCore import QFile

        members = self._tidy_sets[set_index]["members"]
        sha = self._tidy_sets[set_index].get("sha256") or ""
        keep_path = members[member_index]["path"]
        failed = 0
        binned: list[str] = []
        for i, m in enumerate(members):
            if i == member_index:
                continue
            if sha:
                from ..dedupe import verify_against_keeper

                # Exact sets: bin only a copy that still hashes to the group's SHA-256.
                if not verify_against_keeper(sha, keep_path, m["path"]).ok:
                    failed += 1
                    continue
            if QFile.moveToTrash(m["path"]):
                binned.append(m["path"])
            else:
                failed += 1
        if binned:
            from ..forget import forget_files

            try:
                forget_files(self._adapter.store, binned, keep=[members[member_index]["path"]])
            except Exception:
                pass
            self._refresh_library()
        del self._tidy_sets[set_index]
        self.tidyChanged.emit()
        if failed and not binned:
            self._apply_result(Result("error", "Nothing was moved. The copies changed or could not be reached, so they stay where they were."))
        elif failed:
            self._apply_result(Result("error", f"Moved {len(binned)}. {failed} changed or could not be moved and stayed where they were."))
        else:
            self._apply_result(Result("ready", "Moved the extra copies to the Recycle Bin."))

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
        if not rows:
            self._activity_open = False
            self._apply_result(result)
            return
        self._activity_open = True
        self._apply_result(Result("ready", f"Activity: {len(rows)} recent lines.", {"activity": rec}))

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
        self._calendar_view = self._load_calendar_view()
        self._archive_split = self._load_archive_split()
        self._apply_result(result)
        self.lensChanged.emit()
        self.editorialChanged.emit()

    @Property("QVariantMap", notify=confirmChanged)
    def confirm(self) -> dict:
        return dict(self._confirm)

    def _ask(self, title, body, facts=(), *, yes="Continue", no="Not now", danger=False,
             keep_open=False, on_yes=None, on_no=None, dismiss_is_no=True) -> None:
        self._confirm = {
            "open": True, "busy": False, "title": title, "body": body, "facts": list(facts),
            "yes": yes, "no": no, "danger": bool(danger), "progress": "",
        }
        self._confirm_yes, self._confirm_no, self._confirm_keep = on_yes, on_no, keep_open
        self._confirm_dismiss_is_no = dismiss_is_no
        self.confirmChanged.emit()

    def _confirm_progress(self, text: str) -> None:
        if self._confirm.get("open"):
            self._confirm = {**self._confirm, "busy": True, "progress": text}
            self.confirmChanged.emit()

    def _confirm_close(self) -> None:
        if self._confirm.get("open"):
            self._confirm = {"open": False, "busy": False}
            self.confirmChanged.emit()

    @Slot()
    def confirmAccept(self) -> None:
        if not self._confirm.get("open") or self._confirm.get("busy"):
            return
        action, keep = self._confirm_yes, self._confirm_keep
        self._confirm_yes = self._confirm_no = None
        if not keep:
            self._confirm_close()
        if action:
            action()

    @Slot()
    def confirmDismiss(self) -> None:
        """Escape: closes the sheet. Only counts as the second choice when that is harmless."""
        if self._confirm.get("open") and not self._confirm.get("busy") and not self._confirm_dismiss_is_no:
            self._confirm_yes = self._confirm_no = None
            self._confirm_close()
            return
        self.confirmDecline()

    @Slot()
    def confirmDecline(self) -> None:
        if not self._confirm.get("open") or self._confirm.get("busy"):
            return
        action = self._confirm_no
        self._confirm_yes = self._confirm_no = None
        self._confirm_close()
        if action:
            action()

    @Slot()
    def clearLibrary(self) -> None:
        """Drop the folder index and names. Original files stay on disk."""
        if self._jobs.busy:
            self._apply_result(Result("unavailable", "A folder is being added. Wait until that finishes."))
            return
        self._ask(
            "Forget what Semblon learned?",
            "Semblon will forget the folders you added, the names you gave and the finds you kept.",
            ["Your photo files stay exactly where they are.", "You can add the folder again any time."],
            yes="Forget it all",
            no="Keep everything",
            danger=True,
            on_yes=self._clear_library_now,
            on_no=lambda: self._apply_result(Result("empty", "Library clear was cancelled.")),
        )

    def _clear_library_now(self) -> None:
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
        clear_thumb_cache(Path(self._jobs.store))
        reset_image_cache()
        self._session.clear_focus()
        self._region_norm = None
        self._selection_kind = ""
        self._selection_note = ""
        self.selectionChanged.emit()
        self._drop_name()
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
                "Semblon's list of your photos was cleared. Your original photos were not changed. Add a folder to start again.",
            )
        )

    @Slot()
    def toggleSettings(self) -> None:
        self._settings_open = not self._settings_open
        if self._settings_open:
            self._refresh_preflight()
        self.surfaceChanged.emit()

    def _refresh_preflight(self) -> None:
        try:
            from semblon.preflight import capability_rows

            self._preflight_rows = capability_rows()
        except Exception as exc:  # noqa: BLE001 — settings must still open
            self._preflight_rows = [
                {
                    "id": "preflight",
                    "itemId": "preflight",
                    "name": "Setup check",
                    "detail": (
                        f"The setup check could not finish. {type(exc).__name__}: {exc}"
                    ),
                    "installable": False,
                    "status": "failed",
                }
            ]
        self.preflightChanged.emit()

    @staticmethod
    def _setup_line(text: str) -> str:
        """One primary-safe sentence. The real failure stays in the sentence."""
        line = " ".join(str(text or "Setup could not finish.").split())
        if not line.endswith("."):
            line += "."
        if line.startswith("Setup:"):
            return line
        return f"Setup: {line}"

    @Property("QVariantList", notify=preflightChanged)
    def preflightRows(self):
        """Capabilities that still need setup. Ready ones are omitted."""
        return list(self._preflight_rows)

    @Property(str, notify=preflightChanged)
    def preflightSummary(self) -> str:
        if not self._preflight_rows:
            return "Everything Semblon can do on this computer is ready."
        return (
            "A few extras are not ready yet. Searches that do not need them still work, "
            "and Semblon will say when one is missing."
        )

    @Slot(str)
    def installPreflight(self, item_id: str) -> None:
        """Install one missing capability, off the UI thread, then verify it."""
        item_id = str(item_id or "").strip()
        row = next((item for item in self._preflight_rows if item.get("id") == item_id), None)
        if row is None:
            self._refresh_preflight()
            row = next((item for item in self._preflight_rows if item.get("id") == item_id), None)
        if row is None or row.get("status") == "ready":
            self._apply_result(Result("ready", self._setup_line("That extra is already ready.")))
            return
        if not row.get("installable"):
            self._apply_result(
                Result(
                    "unavailable",
                    self._setup_line(
                        str(row.get("detail") or "This extra can't be added from here.")
                    ),
                )
            )
            return
        if self._preflight_thread is not None and self._preflight_thread.isRunning():
            self._apply_result(Result("loading", self._setup_line("An install is already running.")))
            return
        self._ask(
            f"Get {row.get('name') or 'this'} ready?",
            self._plain_confirm(row),
            [_NOTHING_LEAVES] if row.get("downloads") else [],
            yes="Get it ready",
            no="Not now",
            keep_open=True,
            on_yes=lambda: self._start_preflight_install(item_id, row),
            on_no=lambda: self._apply_result(Result("empty", self._setup_line("Nothing was added."))),
        )

    @staticmethod
    def _plain_confirm(row: dict) -> str:
        """The sheet's sentence. Setup wording that talks about software internals becomes plain."""
        text = str(row.get("confirm") or "").strip()
        technical = re.search(r"environment|==|package|\bpin\b|python", text, re.IGNORECASE)
        if not text or technical:
            name = str(row.get("name") or "this extra")
            return (
                f"Semblon will add {name} to its own private space on this computer. "
                "Your other programs and your photos are not touched."
            )
        return text

    def _start_preflight_install(self, item_id: str, row: dict) -> None:
        self._confirm_progress("Getting it ready\u2026")
        self._apply_result(
            Result("loading", self._setup_line(f"Installing {row.get('name') or item_id}."))
        )

        def _run():
            from semblon.preflight import install_item

            return install_item(item_id)

        thread = _TaskThread(_run, self)
        thread.succeeded.connect(self._on_preflight_installed)
        thread.failed.connect(self._on_preflight_failed)
        self._preflight_thread = thread
        thread.start()

    def _on_preflight_installed(self, rec: object) -> None:
        self._confirm_close()
        self._refresh_preflight()
        result = rec if isinstance(rec, dict) else {}
        if result.get("ready") and result.get("skipped"):
            self._apply_result(Result("ready", self._setup_line("Already ready. Nothing was installed.")))
            return
        if result.get("ready"):
            self._apply_result(Result("ready", self._setup_line("Installed and verified.")))
            return
        self._apply_result(
            Result(
                "unavailable",
                self._setup_line(
                    str(result.get("error") or "Install did not verify. It is still not ready.")
                ),
            )
        )

    def _on_preflight_failed(self, message: str) -> None:
        self._confirm_close()
        self._refresh_preflight()
        self._apply_result(Result("unavailable", self._setup_line(message or "Install failed.")))

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

    @Slot(str)
    def startCategoryScan(self, category: str) -> None:
        """Check one Discover category across the archive. Not the broad rescan."""
        name = str(category or "").strip()
        if name not in {"people", "objects", "regions", "words"}:
            self._category_note = "Choose people, objects, regions, or words in photos."
            self.jobChanged.emit()
            return
        if self._jobs.busy:
            self._category_note = "Something is already running."
            self.jobChanged.emit()
            return
        from semblon.category_backfill import _label

        self._category_note = f"Checking {_label(name).lower()}."
        self._category_job = name
        self._category_resume = ""
        self._resume_ready = False
        self._cancel_requested = False
        self.jobChanged.emit()
        try:
            self._jobs.submit_category(
                name,
                on_event=self._on_worker_progress,
                on_done=self._on_category_done,
            )
        except JobBusy:
            self._category_note = "Something is already running."
            self.jobChanged.emit()
            return
        self._poll_job()

    def _on_category_done(self, result) -> None:
        status = str(getattr(result, "status", "") or "")
        rec = getattr(result, "rec", None) or {}
        note = str(rec.get("user_message") or "")
        if not note:
            if status == "cancelled":
                note = "Stopped. Unfinished photos were not marked done."
            elif status == "unavailable":
                note = "That check is not available on this computer."
            elif status == "failed":
                note = "The check failed before it finished."
            else:
                note = ""
        self._category_note = note
        self._terminal_status = status or "completed"
        # A category stop is not a folder ingest to resume.
        self._cancel_requested = False
        self._refresh_coverage_when_idle = True
        self._events.record(
            {
                "completed": JOB_COMPLETED,
                "cancelled": JOB_CANCELLED,
                "failed": JOB_FAILED,
                "unavailable": JOB_FAILED,
            }.get(status, JOB_COMPLETED),
            {"status": status or "completed", "category": str(rec.get("category") or "")},
        )
        self._queue_ingest_finished()

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
            None, "Choose the face files you downloaded", "", "JSON (*.json)"
        )
        if not path:
            self._apply_result(Result("empty", "Face files: choose a file from this computer."))
            return
        self.inspectPack(path)

    @Slot()
    def chooseModelInstall(self) -> None:
        source, _selected = QFileDialog.getOpenFileName(None, "Choose the extra you downloaded", "", "All files (*.*)")
        if not source:
            self._apply_result(Result("empty", "Extra: choose a file from this computer."))
            return
        dest, _selected = QFileDialog.getSaveFileName(None, "Where should the extra go?", "", "All files (*.*)")
        if not dest:
            self._apply_result(Result("empty", "Extra: choose where to put it."))
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

    @Slot(result=str)
    def installSuggestedModel(self) -> str:
        """Install the suggested model here, then run the same search again."""
        kind = self._install_suggestion
        prompt = _INSTALL_PROMPTS.get(kind)
        if prompt is None:
            self._apply_result(Result("empty", "No install action is available right now."))
            return self._notice
        title, body, facts = prompt
        if self._install_thread is not None and self._install_thread.isRunning():
            self._apply_result(Result("loading", "Something is already being added."))
            return self._notice
        self._ask(
            title,
            body,
            facts,
            yes="Get it ready",
            no="Not now",
            keep_open=True,
            on_yes=lambda: self._start_suggested_install(kind),
            on_no=lambda: self._apply_result(Result("empty", "Nothing was added.")),
        )
        return self._notice

    def _start_suggested_install(self, kind: str) -> None:
        self._confirm_progress(f"Getting {_SETUP_NAMES.get(kind, 'it')} ready\u2026 You can keep this window open.")
        self._install_kind = kind
        self._install_retry = self._query_source
        self._install_retry_rect = self._screen_query_rect
        basis = self._similar_basis or "region"
        label = self._similar_basis_label or "Similar look"
        self._set_install_suggestion("", "")
        self._publish_similar(
            "loading",
            f"Similar ({label}): installing. This search will run again on this screen.",
            [],
            basis=basis,
            basis_label=label,
            persist=False,
        )
        method_name = _INSTALL_METHODS[kind]
        thread = _TaskThread(lambda: getattr(self._adapter, method_name)(), self)
        thread.succeeded.connect(self._on_install_suggested_ready)
        thread.failed.connect(self._on_install_suggested_failed)
        self._install_thread = thread
        thread.start()

    def _resume_current_query(self) -> bool:
        """Repeat the search the user was already on. Does not open a new screen drag."""
        if self._install_retry == "screen" and self._install_retry_rect:
            self._begin_screen_search(self._install_retry_rect)
            return True
        if self._install_retry == "focus" and self._session.focus_id and self._region_norm:
            self.findSimilar()
            return True
        if self._query_source == "screen" and self._screen_query_rect:
            self._begin_screen_search(self._screen_query_rect)
            return True
        if self._session.focus_id and self._region_norm:
            self.findSimilar()
            return True
        return False

    @Slot(object)
    def _on_install_suggested_ready(self, payload) -> None:
        self._install_thread = None
        self._confirm_close()
        result = payload if isinstance(payload, Result) else Result("ready", "Ready.")
        self._apply_result(result)
        if self._resume_current_query():
            return
        label = self._similar_basis_label or "Similar look"
        self._publish_similar(
            "empty",
            f"Similar ({label}): ready. Search this area again.",
            [],
            basis=self._similar_basis or "region",
            basis_label=label,
            persist=False,
        )

    @Slot(str)
    def _on_install_suggested_failed(self, message: str) -> None:
        self._install_thread = None
        self._confirm_close()
        label = self._similar_basis_label or "Similar look"
        kind = self._install_kind or "region_pack"
        self._set_install_suggestion(kind, _INSTALL_LABELS.get(kind, "Get this ready"))
        self._publish_similar(
            "unavailable",
            f"Similar ({label}): couldn't be set up.",
            [],
            basis=self._similar_basis or "region",
            basis_label=label,
            persist=False,
        )
        self._apply_result(Result("unavailable", _plain(message, "That didn't finish. Nothing was changed. Your photos were not touched.")))

    @Slot()
    def findSimilarWhole(self) -> None:
        self._set_door("whole")
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
        quality = str(adapter.search_quality().data.get("quality") or "balanced")

        def build(flag, report):
            if quality == "fast":
                return _stamp_phase(adapter.similar_media(media_id, search_quality="fast"), "fast")
            first = adapter.similar_media(media_id, search_quality="fast")
            if not flag[0]:
                report(_stamp_phase(first, "first"))
            if flag[0]:
                return None
            full = adapter.similar_media(media_id, search_quality=quality)
            if flag[0]:
                return None
            first_items = list((first.data or {}).get("items") or [])
            full_items = list((full.data or {}).get("items") or [])
            if first_items and not full_items:
                return _stamp_phase(first, "kept")
            return _stamp_phase(full, "refined")

        self._start_visual_search(basis="whole", label="Colour only", build=build)

    @Slot()
    @Slot(str)
    def findSimilarFaces(self, face_id: str = "") -> None:
        """Focus face → ranked same-pack face hits. Not colour-histogram Similar; no auto-name."""
        self._set_door("face")
        fid = str(face_id or self._selected_observation or "").strip()
        if not fid:
            self._publish_similar("unavailable", "Select a face on the photo first.", [])
            return
        if self._similar_state == "ready" and self._similar.rowCount():
            self._push_discovery()
        adapter = self._adapter

        def build(_flag, _report):
            return adapter.similar_faces(fid)

        self._start_visual_search(basis="face", label="Same face", build=build)

    def _set_door(self, key: str) -> None:
        self._search_door = key
        self.doorChanged.emit()

    def _note_search_timing(self, *, final: bool) -> None:
        if not self._search_started:
            return
        elapsed = max(0, int((time.monotonic() - self._search_started) * 1000))
        if self._search_first_ms < 0:
            self._search_first_ms = elapsed
        if final:
            self._search_refined_ms = elapsed

    def _drop_name(self) -> None:
        self._identify_generation += 1
        changed = self._identify_busy or bool(self._name_note) or bool(self._name_confidence)
        self._identify_busy = False
        self._name_note = ""
        self._name_confidence = ""
        if changed:
            self.nameChanged.emit()

    def _set_name(self, text: str, *, busy: bool, confidence: str = "") -> None:
        self._identify_busy = busy
        self._name_note = present_message(
            self._mode,
            text,
            fallback="This area could not be named.",
        )
        if busy or not confidence or not is_primary_safe_message(confidence):
            self._name_confidence = ""
        else:
            self._name_confidence = confidence
        self.nameChanged.emit()

    def _settle_name(self) -> None:
        thread = self._name_thread
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
            if not self._identify_busy:
                break

    @Slot()
    def nameSelection(self) -> None:
        """Name the highlighted crop. Leaves the similar strip where it is."""
        media_id = self._session.focus_id
        if not media_id:
            self._set_name("Open a photo first.", busy=False)
            return
        rect = self._pixel_rect()
        if rect is None:
            self._set_name("Draw a region on the photo first.", busy=False)
            return
        x, y, w, h = rect
        self._identify_generation += 1
        generation = self._identify_generation
        jobs = self._jobs
        self._set_name("Naming this area.", busy=True)

        def work():
            return jobs.name_selection(media_id, x, y, w, h)

        thread = _NameSelectionThread(generation, work, self)
        thread.succeeded.connect(self._on_named)
        thread.failed.connect(self._on_name_failed)
        self._name_thread = thread
        thread.start()
        if os.environ.get("SEMBLON_SEARCH_SYNC") == "1":
            self._settle_name()

    @Slot(int, object)
    def _on_named(self, generation: int, payload) -> None:
        if generation != self._identify_generation:
            return
        text = "Unlabelled region."
        confidence = ""
        if isinstance(payload, dict):
            text = str(payload.get("understanding") or text)
            confidence = _confidence_label(payload.get("confidence"))
        self._set_name(text, busy=False, confidence=confidence)

    @Slot(int, str)
    def _on_name_failed(self, generation: int, _message: str) -> None:
        if generation != self._identify_generation:
            return
        self._set_name("This area could not be named.", busy=False)

    @Slot()
    def findSimilar(self) -> None:
        """Region search door for a drawn rect. The Focus strip calls this on release."""
        self._set_door("region")
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
        quality = str(adapter.search_quality().data.get("quality") or "balanced")
        spec = {
            "mode": self._refine_mode,
            "modifier": self._refine_modifier,
            "part_index": self._refine_part_index,
        }

        def build(flag, report):
            from semblon.user_region import RegionError

            def on_first(rec):
                if flag[0]:
                    return
                report(adapter.similar_region(rec))

            try:
                rec = jobs.remember_and_find_region(
                    media_id,
                    x,
                    y,
                    w,
                    h,
                    selection_kind=kind,
                    search_quality=quality,
                    cancelled=lambda: bool(flag[0]),
                    on_first=None if quality == "fast" else on_first,
                    query_spec=spec,
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

        self._query_source = "focus"
        self._start_visual_search(basis="region", label="Similar look", build=build)

    @Slot()
    def pauseJob(self) -> None:
        self._jobs.pause_job()
        self._poll_job()

    @Slot()
    def resumeJob(self) -> None:
        """Paused work continues. A stopped category check restarts that category, not folder ingest."""
        from semblon.jobs import resume_action

        action = resume_action(
            paused=bool(self._jobs.paused),
            busy=bool(self._jobs.busy),
            category=self._category_resume or None,
            folder_ready=self._resume_ready and self._last_folder is not None,
        )
        if action == "unpause":
            self._jobs.unpause_job()
            self._poll_job()
            return
        if action == "category":
            self.startCategoryScan(self._category_resume)
            return
        if action != "ingest" or self._last_folder is None:
            return
        self._start_ingest(self._last_folder, resume=True)

    @Slot()
    def cancelJob(self) -> None:
        self._cancel_requested = True
        self._jobs.cancel_job()
        self._poll_job()

    def path_for(self, media_id: str) -> str | None:
        if not media_id:
            return None
        if media_id in self._path_cache:
            return self._path_cache[media_id] or None
        path = self._jobs.media_path(media_id) or ""
        if len(self._path_cache) > 4000:
            self._path_cache.clear()
        self._path_cache[media_id] = path
        return path or None

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
                "outcome": str(getattr(ev, "outcome", "") or ""),
                "message": str(getattr(ev, "message", "") or ""),
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
            message = str(payload.get("message") or "")
            if str(payload.get("stage") or "") == "category" and message:
                self._progress_label = message
                self._category_note = message
            else:
                outcome = str(payload.get("outcome") or "")
                if outcome in {"indexed", "detailed"} and outcome != self._pass_outcome:
                    self._pass_outcome = outcome
                    self._pass_started_mono = time.monotonic()
                if outcome == "indexed":
                    self._progress_label = (
                        f"Getting your photos ready to search: {current} of {total}. "
                        "You can already browse, open and search them."
                    )
                elif outcome == "detailed":
                    self._progress_label = (
                        f"Sharpening search: {current} of {total}. "
                        "Everything already works; searches just get more precise."
                    )
                else:
                    self._progress_label = (
                        f"Getting your photos ready: {current} of {total}. You can already browse and open them."
                    )
        elif payload.get("stage"):
            self._progress_label = "Processing"
        self.jobChanged.emit()
        if isinstance(current, int) and current != self._progress_seen:
            self._progress_seen = current
            now = time.monotonic()
            if now - self._library_refresh_at >= 0.75:
                self._library_refresh_at = now
                self._refresh_library(editorial=False)
                self._refresh_index_note()

    @Slot()
    def _queue_ingest_finished(self) -> None:
        QMetaObject.invokeMethod(self, "_emit_ingest_finished", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _emit_ingest_finished(self) -> None:
        if self._refresh_coverage_when_idle:
            self._refresh_coverage_when_idle = False
            self.refreshCategoryCoverage()
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
            if self._job_pause_started <= 0:
                self._job_pause_started = time.monotonic()
        elif self._job_state == "paused" and state != "paused" and self._job_pause_started > 0:
            self._job_paused_seconds += max(0.0, time.monotonic() - self._job_pause_started)
            self._job_pause_started = 0.0
        changed = active != self._job_active or state != self._job_state
        if changed:
            was = self._job_active
            if was and not active:
                self._progress_current = 0
                self._progress_total = 0
                if self._category_job:
                    if self._terminal_status in {"cancelled", "failed"}:
                        self._category_resume = self._category_job
                    else:
                        self._category_resume = ""
                    self._category_job = ""
                else:
                    self._resume_ready = self._resume_ready or bool(
                        self._cancel_requested and self._last_folder is not None
                    )
                self._cancel_requested = False
                self._last_job_failed = self._terminal_status == "failed"
                if self._surface_state == "loading":
                    self._surface_state = "empty" if self._jobs.archive_count() == 0 else "ready"
                    self.surfaceChanged.emit()
                self._clear_job_clock()
            if active and not was:
                self._arm_job_clock()
            self._job_active = active
            self._job_state = state
            self.jobChanged.emit()
            if was and not active:
                self._refresh_library()
        if self._job_active:
            timing = self._job_timing_text()
            if timing != self._job_timing_shown:
                self._job_timing_shown = timing
                if not changed:
                    self.jobChanged.emit()

    def _arm_job_clock(self) -> None:
        self._pass_outcome = ""
        self._pass_started_mono = 0.0
        self._job_started_mono = time.monotonic()
        self._job_paused_seconds = 0.0
        self._job_pause_started = 0.0
        self._job_timing_shown = ""

    def _clear_job_clock(self) -> None:
        self._job_started_mono = 0.0
        self._job_paused_seconds = 0.0
        self._job_pause_started = 0.0
        self._job_timing_shown = ""

    def _job_elapsed_seconds(self) -> float:
        if self._job_started_mono <= 0:
            return 0.0
        now = time.monotonic()
        paused = self._job_paused_seconds
        if self._job_state == "paused" and self._job_pause_started > 0:
            paused += max(0.0, now - self._job_pause_started)
        return max(0.0, now - self._job_started_mono - paused)

    def _job_timing_text(self) -> str:
        if not self._job_active or self._job_started_mono <= 0:
            return ""
        elapsed = _format_span(self._job_elapsed_seconds())
        if self._job_state in {"paused", "cancelling"}:
            return f"{elapsed} elapsed."
        current = int(self._progress_current)
        total = int(self._progress_total)
        spent = self._job_elapsed_seconds()
        if self._pass_outcome and self._pass_started_mono > 0:
            spent = max(0.0, time.monotonic() - self._pass_started_mono)
        if current <= 0 or total <= current or spent < 1:
            return f"{elapsed} elapsed."
        remaining = (total - current) * spent / current
        if remaining > 6 * 3600:
            return f"{elapsed} elapsed. This keeps going in the background; carry on using your photos."
        left = _format_span(max(1, int(round(remaining))))
        return f"{elapsed} elapsed. About {left} left."

    def _refresh_library(self, *, editorial: bool = True) -> None:
        self._path_cache.clear()
        self._index_cache.clear()
        self._session.invalidate_reads()
        # A running scan must not rebuild year/day/folder id lists on the UI
        # thread. That walk opens a writer connection per list and stalls the
        # shell for the whole folder. The field stays a SQL window until the
        # job ends, which is when the calendar catches up.
        if (
            not editorial
            and self._model.media_ids() is not None
            and not self._scope_kind
            and not self._person_field_filter
        ):
            self._model.set_media_ids(None)
        else:
            self._model.reload()
        self._events.record(LIBRARY_CHANGED, {"count": int(self._jobs.archive_count())})
        empty = self._jobs.archive_count() == 0
        if editorial:
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


def _format_span(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


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


def _screen_text_token(text: str) -> str:
    tokens = [part for part in str(text or "").replace("\n", " ").split() if any(ch.isalnum() for ch in part)]
    tokens.sort(key=len, reverse=True)
    for token in tokens:
        cleaned = "".join(ch for ch in token if ch.isalnum())
        if len(cleaned) >= 4:
            return cleaned
    return ""


def _screen_understanding(lines, observations=None) -> str:
    for row in observations or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        payload = row.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        if kind == "text":
            token = _screen_text_token(payload.get("text") or "")
            if token:
                return f"Text: {token}."
        if kind == "object":
            label = str(payload.get("label") or payload.get("class") or "").strip()
            if label and label.lower() not in {"region", "user_region"}:
                return f"Object: {label}."
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered == "lens" or lowered.startswith("selected area"):
            continue
        return text
    return "Screen selection."

