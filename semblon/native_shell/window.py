"""Legacy three-column widgets. Not launched by `semblon shell`.

The archive shell is qml/Shell.qml via host.py.
Kept so an existing import of ShellWindow still loads. Do not wire it back
as the daily window.

Native shell main window — R3-BRIEF §4 IA.

Library | Workspace / Intelligence Canvas | Inspector
Job bar: Choose folder · Pause · Resume · Cancel

Pause = Application.pause_job (same job). Resume while paused = unpause_job.
Resume while idle with a prior folder = submit_ingest(..., resume=True).

Inspector verbs go through semblon.inspector_verbs -> review_ui.apply_* .
UI never calls process_folder or FaceKit.
"""

from __future__ import annotations

import queue
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from semblon.application import Application, JobBusy
from semblon.canvas import overlay_boxes
from semblon.inspector_verbs import (
    VERB_IGNORE,
    VERB_MERGE,
    VERB_NAME,
    VERB_RULE_OUT,
    VERB_SPLIT,
    apply_inspector_ignore,
    apply_inspector_merge,
    apply_inspector_name,
    apply_inspector_rule_out,
    apply_inspector_split,
    evidence_lines_for_selection,
    flatten_board_items_for_inspector,
    inspector_verb_states,
)
from semblon.progress import KIND_QUEUED, STAGE_PROCESS, ProgressEvent, make_event
from semblon.review_ui import ReviewUiError
from semblon.state_triple import format_media_card_label, media_inspector_triple_line, triples_for_board
from semblon.ui_copy import status_text


class ShellWindow(QMainWindow):
    """Production shell chrome. UI commands Application; never process_folder."""

    def __init__(self, session: Application):
        super().__init__()
        self.session = session
        self._last_folder: Path | None = None
        self._resume_ready = False
        self._q: queue.Queue = queue.Queue()
        self._board_items: list[dict] = []
        self._run_id: str | None = None
        self._selected: list[dict] = []
        self._canvas: dict | None = None
        self._canvas_media_id: str | None = None
        self.setWindowTitle("Semblon")
        self.resize(1280, 800)
        try:
            from semblon.ui_prefs import load_theme_mode, resolve_palette
            from semblon.ui_tokens import qt_stylesheet

            self.setStyleSheet(qt_stylesheet(resolve_palette(load_theme_mode(session.store))))
        except Exception:  # noqa: BLE001 — optional shell still opens without tokens
            pass

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_job_bar())
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._build_library())
        split.addWidget(self._build_workspace())
        split.addWidget(self._build_inspector())
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        split.setStretchFactor(2, 2)
        layout.addWidget(split, stretch=1)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — choose a folder to ingest")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_queue)
        self._timer.start(50)
        self._refresh_controls()
        self._load_library_home()
        self._reload_board()

    def _build_job_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("jobBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 12, 8)
        self.btn_folder = QPushButton("Choose folder")
        self.btn_folder.clicked.connect(self._choose_folder)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self._request_pause)
        self.btn_resume = QPushButton("Resume")
        self.btn_resume.clicked.connect(self._request_resume)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._request_cancel)
        for b in (self.btn_folder, self.btn_pause, self.btn_resume, self.btn_cancel):
            row.addWidget(b)
        row.addStretch(1)
        self.lbl_state = QLabel("idle")
        row.addWidget(self.lbl_state)
        return bar

    def _build_library(self) -> QWidget:
        panel = QWidget()
        col = QVBoxLayout(panel)
        col.addWidget(QLabel("LIBRARY"))
        self.nav = QListWidget()
        for name in ("Home", "Photos", "Videos", "People", "Unknown", "Activity"):
            self.nav.addItem(name)
        self.nav.currentTextChanged.connect(self._on_nav)
        col.addWidget(self.nav)
        return panel

    def _build_workspace(self) -> QWidget:
        panel = QWidget()
        col = QVBoxLayout(panel)
        col.addWidget(QLabel("WORKSPACE / INTELLIGENCE CANVAS"))
        self.workspace_hint = QLabel("")
        self.workspace_hint.setWordWrap(True)
        col.addWidget(self.workspace_hint)
        self.board_list = QListWidget()
        self.board_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.board_list.itemSelectionChanged.connect(self._on_board_selection)
        col.addWidget(self.board_list, stretch=1)
        return panel

    def _build_inspector(self) -> QWidget:
        panel = QWidget()
        col = QVBoxLayout(panel)
        col.addWidget(QLabel("INSPECTOR"))
        self.evidence = QLabel("Evidence (machine) ≠ proposed action (human).")
        self.evidence.setWordWrap(True)
        self.evidence.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.evidence)
        col.addWidget(QLabel("Proposed action (human)"))
        self.btn_merge = QPushButton("Merge observations")
        self.btn_name = QPushButton("Name")
        self.btn_split = QPushButton("Split")
        self.btn_ignore = QPushButton("Ignore")
        self.btn_rule_out = QPushButton("Rule out")
        self.btn_merge.clicked.connect(self._do_merge)
        self.btn_name.clicked.connect(self._do_name)
        self.btn_split.clicked.connect(self._do_split)
        self.btn_ignore.clicked.connect(self._do_ignore)
        self.btn_rule_out.clicked.connect(self._do_rule_out)
        for b in (
            self.btn_merge,
            self.btn_name,
            self.btn_split,
            self.btn_ignore,
            self.btn_rule_out,
        ):
            col.addWidget(b)
        col.addStretch(1)
        return panel

    def _refresh_controls(self) -> None:
        states = self.session.control_states(resume_ready=self._resume_ready)
        mapping = {
            "folder": self.btn_folder,
            "pause": self.btn_pause,
            "resume": self.btn_resume,
            "cancel": self.btn_cancel,
        }
        for key, btn in mapping.items():
            btn.setEnabled(states[key] == "normal")
        self.lbl_state.setText(self.session.state)

    def _choose_folder(self) -> None:
        if self.session.busy:
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder of photos for Semblon")
        if not folder:
            return
        self._start_process(Path(folder), resume=False)

    def _request_pause(self) -> None:
        if not self.session.busy or self.session.paused:
            return
        self.session.pause_job()
        self._status.showMessage("Pausing… (stops between files; not mid-file)")
        self._refresh_controls()

    def _request_resume(self) -> None:
        if self.session.paused:
            self.session.unpause_job()
            self._status.showMessage("Resuming job…")
            self._refresh_controls()
            return
        if self.session.busy or self._last_folder is None:
            return
        self._start_process(self._last_folder, resume=True)

    def _request_cancel(self) -> None:
        if not self.session.busy:
            return
        self.session.cancel_job()
        self._status.showMessage("Cancelling…")
        self._refresh_controls()

    def _start_process(self, path: Path, *, resume: bool) -> None:
        self._last_folder = path
        self._resume_ready = False
        queued = make_event(
            STAGE_PROCESS,
            KIND_QUEUED,
            path=str(path),
            outcome="resumed" if resume else None,
        )
        self._status.showMessage(status_text(queued))
        self._refresh_controls()

        def on_event(ev: ProgressEvent) -> None:
            self._q.put(("event", ev))

        def on_done(result) -> None:
            self._q.put(("done", result))

        try:
            self.session.submit_ingest(
                path,
                resume=resume,
                on_event=on_event,
                on_done=on_done,
            )
        except JobBusy:
            self._status.showMessage("Job busy — ingest already running.")
        self._refresh_controls()

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "event":
                    self._status.showMessage(status_text(payload))
                elif kind == "done":
                    status = getattr(payload, "status", "failed")
                    if status == "completed":
                        self._status.showMessage("Completed")
                        self._resume_ready = False
                    elif status == "cancelled":
                        self._status.showMessage("Cancelled — Resume continues from partial")
                        self._resume_ready = self._last_folder is not None
                    else:
                        err = getattr(payload, "error", None)
                        self._status.showMessage(f"Failed: {err}")
                        self._resume_ready = self._last_folder is not None
                    self._reload_board()
                self._refresh_controls()
        except queue.Empty:
            if self.session.paused:
                self._status.showMessage(
                    "Paused — not processing; Resume continues this job (between-files pause)"
                )
            self._refresh_controls()

    def _on_nav(self, name: str) -> None:
        if name == "People":
            people = self.session.people()
            items = people.get("items", []) if isinstance(people, dict) else []
            lines = [
                f"{p.get('display_name') or p.get('person_id')}" for p in items
            ] or ["(no named people)"]
            self.workspace_hint.setText("People — named persons only. Cluster ≠ person.")
            self.board_list.clear()
            for line in lines:
                self.board_list.addItem(line)
            self.evidence.setText("Named persons only. Cluster ≠ person.")
        elif name == "Unknown":
            try:
                box = self.session.inbox()
            except Exception as e:  # noqa: BLE001 — surface in workspace
                self.workspace_hint.setText(f"Unknown / inbox unavailable: {e}")
                return
            counts = box.get("counts") or {}
            unknown_n = counts.get("UNKNOWN", counts.get("unknown", 0))
            self.workspace_hint.setText(
                f"Unknown (inbox) — UNKNOWN: {unknown_n}. Unknown is valid."
            )
            self.board_list.clear()
            for it in box.get("items") or []:
                if it.get("bucket") == "UNKNOWN":
                    self.board_list.addItem(f"{it.get('face_id')}  {it.get('bucket')}")
            self.evidence.setText("Inbox is observation triage — not auto-ID.")
        elif name == "Activity":
            try:
                act = self.session.activity()
            except Exception as e:  # noqa: BLE001
                self.workspace_hint.setText(f"Activity unavailable: {e}")
                return
            self.workspace_hint.setText(
                f"Activity — groups:{len(act.get('groups', []))} "
                f"relationships:{len(act.get('relationships', []))} "
                f"events:{len(act.get('events', []))} "
                f"tracks:{act.get('track_count', 0)} (Track ≠ person)"
            )
            self.board_list.clear()
            self.evidence.setText("Activity is observation-graph RO.")
        elif name in {"Photos", "Videos", "Home"}:
            self._load_canvas_media(source_type="video" if name == "Videos" else None)
        else:
            self._load_library_home()
            self._reload_board()

    def _load_canvas_media(self, *, source_type: str | None = None) -> None:
        """Observation overlay list via Application.canvas — never writes person_id."""
        try:
            board = self.session.canvas()
        except Exception as e:  # noqa: BLE001
            self.workspace_hint.setText(f"Canvas unavailable: {e}")
            self.board_list.clear()
            return
        self._canvas = board
        self._run_id = board.get("run_id")
        triples = triples_for_board(
            board,
            job_state=self.session.state,
            run_finished=board.get("run_finished"),
        )
        media_rows = board.get("media") or []
        if source_type:
            media_rows = [m for m in media_rows if m.get("source_type") == source_type]
        self.workspace_hint.setText(
            f"Canvas — run={self._run_id} media={len(media_rows)} "
            f"boxes never write person_id. {board.get('note') or ''}"
        )
        self.board_list.clear()
        for m in media_rows:
            mid = str(m.get("media_id") or "")
            triple = triples.get(mid)
            label = format_media_card_label(m, triple) if triple else (m.get("path") or mid)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, {"kind": "media", "media_id": mid, **m})
            self.board_list.addItem(item)
        self.evidence.setText(
            "Library is the source-media layer.\n"
            "Canvas overlays boxes/tracks — never writes faces.person_id.\n"
            "Group ≠ person. Track ≠ person."
        )

    def _show_canvas_selection(self, media_id: str) -> None:
        if not self._canvas:
            return
        boxes = overlay_boxes(self._canvas, media_id)
        triples = triples_for_board(
            self._canvas,
            job_state=self.session.state,
            run_finished=self._canvas.get("run_finished"),
            current_media_id=media_id,
        )
        triple = triples.get(media_id)
        lines = [
            f"media={media_id}",
            f"boxes={len(boxes)} (no person_id in overlay payload)",
        ]
        if triple is not None:
            lines.append(media_inspector_triple_line(triple))
        for b in boxes[:12]:
            kind = b.get("kind") or "box"
            tag = b.get("tag") or b.get("id") or ""
            lines.append(f"  {kind} {tag}".rstrip())
        if len(boxes) > 12:
            lines.append(f"  … +{len(boxes) - 12} more")
        lines.append("Canvas never writes faces.person_id.")
        self.evidence.setText("\n".join(lines))
        self._canvas_media_id = media_id

    def _load_library_home(self) -> None:
        self.workspace_hint.setText(
            f"Semblon — store: {self.session.store}\n"
            "Job door: Application -> JobEngine. Pause: between files."
        )

    def _reload_board(self) -> None:
        try:
            rec = self.session.board()
        except Exception as e:  # noqa: BLE001 — empty store is normal at first open
            self._run_id = None
            self._board_items = []
            self.board_list.clear()
            self.workspace_hint.setText(f"Board unavailable: {e}")
            self._refresh_inspector()
            return
        self._run_id = rec.get("run_id")
        self._board_items = flatten_board_items_for_inspector(rec.get("items") or [])
        self.board_list.clear()
        for it in self._board_items:
            kind = it.get("kind") or "?"
            label = it.get("cluster_id") or it.get("face_id") or it.get("track_id") or kind
            item = QListWidgetItem(f"{kind}: {label}")
            item.setData(Qt.ItemDataRole.UserRole, it)
            self.board_list.addItem(item)
        self._refresh_inspector()

    def _on_board_selection(self) -> None:
        selected = []
        for item in self.board_list.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                selected.append(data)
        self._selected = selected
        if (
            len(selected) == 1
            and selected[0].get("kind") == "media"
            and selected[0].get("media_id")
        ):
            self._show_canvas_selection(str(selected[0]["media_id"]))
            return
        self._refresh_inspector()

    def _refresh_inspector(self) -> None:
        lines = evidence_lines_for_selection(
            run_id=self._run_id,
            selected=self._selected,
        )
        self.evidence.setText("\n".join(lines))
        states = inspector_verb_states(self._selected, run_id=self._run_id)
        self._verb_states = states
        self.btn_merge.setEnabled(bool(states.get(VERB_MERGE, {}).get("enabled")))
        self.btn_name.setEnabled(bool(states.get(VERB_NAME, {}).get("enabled")))
        self.btn_split.setEnabled(bool(states.get(VERB_SPLIT, {}).get("enabled")))
        self.btn_ignore.setEnabled(bool(states.get(VERB_IGNORE, {}).get("enabled")))
        self.btn_rule_out.setEnabled(bool(states.get(VERB_RULE_OUT, {}).get("enabled")))
        for btn, key in (
            (self.btn_merge, VERB_MERGE),
            (self.btn_name, VERB_NAME),
            (self.btn_split, VERB_SPLIT),
            (self.btn_ignore, VERB_IGNORE),
            (self.btn_rule_out, VERB_RULE_OUT),
        ):
            reason = (states.get(key) or {}).get("reason")
            btn.setToolTip(reason or "")

    def _require_run(self) -> str | None:
        if not self._run_id:
            QMessageBox.information(self, "Semblon", "No run selected")
            return None
        return self._run_id

    def _do_merge(self) -> None:
        run_id = self._require_run()
        if not run_id:
            return
        st = self._verb_states.get(VERB_MERGE) or {}
        if not st.get("enabled"):
            QMessageBox.information(self, "Semblon", st.get("reason") or "Merge unavailable")
            return
        try:
            apply_inspector_merge(self.session.store, run_id, st.get("cluster_ids") or [])
        except ReviewUiError as e:
            QMessageBox.warning(self, "Semblon", str(e))
            return
        self._status.showMessage("Merged observations (not persons)")
        self._reload_board()

    def _do_name(self) -> None:
        run_id = self._require_run()
        if not run_id:
            return
        st = self._verb_states.get(VERB_NAME) or {}
        if not st.get("enabled"):
            QMessageBox.information(self, "Semblon", st.get("reason") or "Name unavailable")
            return
        name, ok = QInputDialog.getText(self, "Name", "Display name:")
        if not ok or not name.strip():
            return
        try:
            apply_inspector_name(
                self.session.store, run_id, st.get("item") or {}, name.strip()
            )
        except ReviewUiError as e:
            QMessageBox.warning(self, "Semblon", str(e))
            return
        self._status.showMessage(f"Named person: {name.strip()}")
        self._reload_board()

    def _do_split(self) -> None:
        run_id = self._require_run()
        if not run_id:
            return
        st = self._verb_states.get(VERB_SPLIT) or {}
        if not st.get("enabled"):
            QMessageBox.information(self, "Semblon", st.get("reason") or "Split unavailable")
            return
        face_ids = st.get("face_ids") or []
        if not face_ids:
            QMessageBox.information(
                self, "Semblon", "Select faces within the cluster to split"
            )
            return
        try:
            apply_inspector_split(
                self.session.store,
                run_id,
                st.get("cluster_id") or "",
                face_ids,
            )
        except ReviewUiError as e:
            QMessageBox.warning(self, "Semblon", str(e))
            return
        self._status.showMessage("Split applied")
        self._reload_board()

    def _do_ignore(self) -> None:
        run_id = self._require_run()
        if not run_id:
            return
        st = self._verb_states.get(VERB_IGNORE) or {}
        item = st.get("item")
        if not item and self._selected:
            item = self._selected[0]
        if not item:
            QMessageBox.information(self, "Semblon", "Select an item to ignore")
            return
        try:
            apply_inspector_ignore(self.session.store, run_id, item)
        except ReviewUiError as e:
            QMessageBox.warning(self, "Semblon", str(e))
            return
        self._status.showMessage("Ignored (deferral). Not Rule out.")
        self._reload_board()

    def _do_rule_out(self) -> None:
        run_id = self._require_run()
        if not run_id:
            return
        st = self._verb_states.get(VERB_RULE_OUT) or {}
        if not st.get("enabled"):
            QMessageBox.information(self, "Semblon", st.get("reason") or "Rule out unavailable")
            return
        try:
            apply_inspector_rule_out(
                self.session.store, run_id, st.get("item") or {}
            )
        except ReviewUiError as e:
            QMessageBox.warning(self, "Semblon", str(e))
            return
        self._status.showMessage("Ruled out (durable reject)")
        self._reload_board()
