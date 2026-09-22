"""Native shell main window — R3-BRIEF §4 IA.

Library | Workspace / Intelligence Canvas | Inspector
Job bar: Choose folder · Pause · Resume · Cancel

Pause = Application.pause_job (same job). Resume while paused = unpause_job.
Resume while idle with a prior folder = submit_ingest(..., resume=True).
"""

from __future__ import annotations

import queue
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from semblon.application import Application, JobBusy
from semblon.progress import KIND_QUEUED, STAGE_PROCESS, ProgressEvent, make_event
from semblon.ui_copy import status_text


class ShellWindow(QMainWindow):
    """Production shell chrome. UI commands Application; never process_folder."""

    def __init__(self, session: Application):
        super().__init__()
        self.session = session
        self._last_folder: Path | None = None
        self._resume_ready = False
        self._q: queue.Queue = queue.Queue()
        self.setWindowTitle("Semblon")
        self.resize(1280, 800)

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
        self.workspace = QLabel(
            "Select Library · People · Unknown · Activity.\n"
            "Ingest goes through Application → JobEngine.\n"
            "review.html is an engineering export, not this shell."
        )
        self.workspace.setWordWrap(True)
        self.workspace.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.workspace, stretch=1)
        return panel

    def _build_inspector(self) -> QWidget:
        panel = QWidget()
        col = QVBoxLayout(panel)
        col.addWidget(QLabel("INSPECTOR"))
        self.inspector = QLabel(
            "Evidence (machine) ≠ proposed action (human).\n"
            "Merge observations ≠ Assign to person.\n"
            "Identity mutations stay on review.apply_* — not this chrome."
        )
        self.inspector.setWordWrap(True)
        self.inspector.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.inspector, stretch=1)
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
                    self._load_library_home()
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
            self.workspace.setText("People\n\n" + "\n".join(lines))
            self.inspector.setText("Named persons only. Cluster ≠ person.")
        elif name == "Unknown":
            try:
                box = self.session.inbox()
            except Exception as e:  # noqa: BLE001 — surface in workspace
                self.workspace.setText(f"Unknown / inbox unavailable: {e}")
                return
            counts = box.get("counts") or {}
            unknown_n = counts.get("UNKNOWN", counts.get("unknown", 0))
            self.workspace.setText(
                "Unknown (inbox)\n\n"
                f"UNKNOWN: {unknown_n}\n"
                "Unknown is valid. Wrong identity > unknown."
            )
            self.inspector.setText("Inbox is observation triage — not auto-ID.")
        elif name == "Activity":
            try:
                act = self.session.activity()
            except Exception as e:  # noqa: BLE001
                self.workspace.setText(f"Activity unavailable: {e}")
                return
            self.workspace.setText(
                "Activity\n\n"
                f"groups: {len(act.get('groups', []))}\n"
                f"relationships: {len(act.get('relationships', []))}\n"
                f"events: {len(act.get('events', []))}\n"
                f"tracks: {act.get('track_count', 0)}\n"
                "Track ≠ person."
            )
            self.inspector.setText("Activity is observation-graph RO.")
        else:
            self._load_library_home()

    def _load_library_home(self) -> None:
        self.workspace.setText(
            "Semblon — local-first image intelligence\n\n"
            f"Store: {self.session.store}\n"
            "Job door: Application → JobEngine → process_folder\n"
            "Pause granularity: between files / stage gates (honest)."
        )
        self.inspector.setText(
            "Evidence (machine) ≠ proposed action (human).\n"
            "Use review-ui or Inspector verbs for Name/Merge/Split/Rule out."
        )
