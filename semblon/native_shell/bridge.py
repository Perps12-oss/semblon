"""QML-facing session. Qt reports input. Application owns archive and jobs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QMetaObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from semblon.atmosphere import ATMOSPHERE_LABELS, ATMOSPHERE_IDS
from semblon.application import Application, JobBusy
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
    folder_rows,
    source_counts,
    year_rows,
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


class ShellBridge(QObject):
    lensChanged = Signal()
    focusChanged = Signal()
    libraryChanged = Signal()
    jobChanged = Signal()
    emptyChanged = Signal()
    ingestFinished = Signal()
    resultChanged = Signal()
    similarChanged = Signal()
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
        self._reduced = reduced_motion()
        self._result_text = ""
        self._region_norm: tuple[float, float, float, float] | None = None
        self._similar = SimilarStripModel()
        self._similar_state = "idle"
        self._similar_note = ""
        self._point_source = ""
        self._people = PeopleModel()
        self._people_open = False
        self._people_note = ""
        self._selected_subject = ""
        self._evidence_id = ""
        self._merge_target_subject = ""
        self._split_faces: list[str] = []
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
        self._photo_count = 0
        self._video_count = 0
        self._years: list[dict] = []
        self._folders: list[dict] = []
        self._unresolved_text = ""
        self.ingestFinished.connect(self._after_ingest)
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._poll_job)
        self._timer.start()
        model.reload()
        self._reload_editorial()

    def shutdown(self) -> None:
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

    @Property(str, notify=lensChanged)
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
    def folderRows(self):
        return list(self._folders)

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
        counts = source_counts(store)
        self._photo_count = int(counts.get("folder") or 0)
        self._video_count = int(counts.get("video") or 0)
        self._years = year_rows(store)
        self._folders = folder_rows(store)
        self.editorialChanged.emit()

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
        self.similarChanged.emit()

    def _publish_similar(self, state: str, note: str, rows: list[tuple[str, float]]) -> None:
        self._similar.set_rows(rows)
        self._similar_state = state
        self._similar_note = present_message(self._mode, note, fallback="Similar search could not run.")
        self.similarChanged.emit()

    def _clear_query(self) -> None:
        self._region_norm = None
        self._result_text = ""
        self.resultChanged.emit()
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
            rows.append(dict(item))
        return rows

    @Property(int, notify=peopleChanged)
    def splitSelectionCount(self) -> int:
        return len(self._split_faces)

    @Property(bool, notify=peopleChanged)
    def canSplitSelected(self) -> bool:
        row = self._people.row(self._selected_subject)
        if not row:
            return False
        total = len(row.get("members") or [])
        return 0 < len(self._split_faces) < total

    @Property(bool, notify=peopleChanged)
    def canMergeSelected(self) -> bool:
        return bool(self._selected_subject and self._merge_target_subject and self._selected_subject != self._merge_target_subject)

    @Property(str, notify=peopleChanged)
    def peopleNote(self) -> str:
        return self._people_note

    @Property(str, notify=peopleChanged)
    def selectedSubject(self) -> str:
        return self._selected_subject

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

    @Slot()
    def closePeople(self) -> None:
        self._people_open = False
        self._selected_subject = ""
        self._evidence_id = ""
        self._merge_target_subject = ""
        self._split_faces = []
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
        self.peopleChanged.emit()

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

    def _refresh_people(self) -> None:
        rows = []
        try:
            board = self._jobs.board()
        except Exception as exc:  # noqa: BLE001 — empty desk, not a traceback
            self._people.set_rows([])
            self._people_note = "No groups yet." if "unknown run" in str(exc).lower() else "Groups could not be read."
            return
        for item in board.get("items") or []:
            members = item.get("members") or []
            if item.get("kind") == "track":
                continue
            if members and all(str(member.get("source_type") or "") == "video" for member in members):
                continue
            media_id = ""
            face_id = ""
            if members:
                media_id = str(members[0].get("media_id") or "")
                face_id = str(members[0].get("face_id") or "")
            names = item.get("person_names") or []
            subject = str(item.get("cluster_id") or item.get("face_id") or "")
            if not subject:
                continue
            rows.append(
                {
                    "subject": subject,
                    "title": names[0] if names else "Unnamed",
                    "count": int(item.get("face_count") or 0),
                    "named": bool(item.get("named")),
                    "mediaId": media_id,
                    "faceId": face_id,
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

    @Slot()
    def escape(self) -> None:
        if self._session.focus_id and self._people_open:
            self._session.escape()
            self._clear_query()
            self.focusChanged.emit()
            return
        if self._people_open:
            self.closePeople()
            return
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
        query = str(text or "").strip()
        if not query:
            self._set_result("Nothing was searched.")
            return
        lowered = query.lower()
        if lowered in {"people", "groups"}:
            self._set_result(self.peopleSummary())
            return
        mode = str(self._adapter.search_mode().data.get("mode") or "people")
        if mode == "text":
            self._apply_result(self._safe_call(lambda: self._adapter.search("text", query)))
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
        px = max(0, min(width - 1, int(nx * width)))
        py = max(0, min(height - 1, int(ny * height)))
        bbox = self._bbox_at_point(media_id, px, py)
        if bbox is None:
            self._clear_query()
            return ""
        x, y, w, h = bbox
        self.setRegion(x / width, y / height, w / width, h / height)
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
        return int(x1), int(y1), max(1, int(round(x2 - x1))), max(1, int(round(y2 - y1)))

    @Slot(str, str, str, result=str)
    def decide(self, kind: str, subject: str, text: str) -> str:
        """Human decision only. Writes through review.py. Does not assign a person by score."""
        from semblon.process import latest_run_id
        from semblon.review import ReviewError

        run_id = latest_run_id(self._jobs.store)
        if not run_id:
            return self._after_decision("No reviewed run yet.")
        if not (text or "").strip() and kind in {"name", "note"}:
            return self._after_decision("A name or note is required.")
        try:
            if kind == "name":
                from semblon.review import name_cluster
                rec = name_cluster(self._jobs.store, run_id, subject, text)
                return self._after_decision(decision_success("name", str(rec.get("display_name") or "")))
            if kind == "ignore":
                from semblon.review import ignore_subject
                ignore_subject(self._jobs.store, run_id, cluster_id=subject)
                return self._after_decision(decision_success("ignore"))
            if kind == "note":
                from semblon.review import note_subject
                note_subject(self._jobs.store, run_id, text, cluster_id=subject)
                return self._after_decision(decision_success("note"))
            if kind == "merge":
                from semblon.review import merge_clusters
                other = text.strip()
                merge_clusters(self._jobs.store, run_id, [subject, other])
                return self._after_decision(decision_success("merge"))
            if kind == "split":
                from semblon.review import split_cluster
                face_ids = [part.strip() for part in text.split(",") if part.strip()]
                split_cluster(self._jobs.store, run_id, subject, face_ids)
                return self._after_decision(decision_success("split"))
            if kind == "rule_out":
                from semblon.review import rule_out_subject

                target_person = text.strip() or None
                kwargs = {"cluster_id": subject}
                if target_person:
                    kwargs["person" + "_id"] = target_person
                rule_out_subject(self._jobs.store, run_id, **kwargs)
                return self._after_decision(decision_success("rule_out"))
        except ReviewError as exc:
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
        if facet == "moments" and self._mode != ADVANCED:
            self._facet = "memory"
            self._apply_result(Result("unavailable", "Moments: open Advanced to see named moments."))
            return
        self._facet = facet
        if facet == "memory":
            self._buckets = []
            self._model.set_media_ids(None)
            self._apply_result(self._adapter.archive_summary())
            return
        result = self._safe_call(lambda: self._adapter.browse(facet))
        self._buckets = list(result.data.get("buckets") or [])
        self._model.set_media_ids(None)
        self._apply_result(result)

    @Slot(str)
    def selectBucket(self, key: str) -> None:
        wanted = str(key or "")
        for row in self._buckets:
            if str(row.get("key") or "") == wanted:
                self._model.set_media_ids(list(row.get("media_ids") or []))
                label = str(row.get("label") or "group")
                self._apply_result(Result("ready", f"Showing {label}."))
                return

    @Slot(str)
    def setSearchMode(self, mode: str) -> None:
        self._apply_result(self._safe_call(lambda: self._adapter.set_search_mode(mode)))

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

    @Slot()
    def showActivity(self) -> None:
        self._apply_result(self._safe_call(self._adapter.activity))

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
        result = self._safe_call(lambda: self._adapter.similar_media(media_id))
        rows = [
            (str(item.get("media_id") or ""), float(item.get("score") or 0.0))
            for item in (result.data.get("items") or [])
            if item.get("media_id")
        ]
        state = result.state if result.state in {"ready", "empty", "unavailable"} else "unavailable"
        note = result.message if result.message else "Similar search could not run."
        self._result_text = ""
        self.resultChanged.emit()
        self._publish_similar(state, note, rows)

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
            self._result_text = ""
            self.resultChanged.emit()
            self._publish_similar("unavailable", "Similar search could not run.", [])
            return
        self._result_text = ""
        self.resultChanged.emit()
        self._publish_similar(*_strip_from(rec))

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
            self._progress_label = f"Processing {current}/{total}"
        elif payload.get("stage"):
            self._progress_label = "Processing"
        self.jobChanged.emit()

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
