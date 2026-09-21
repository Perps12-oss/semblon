"""Home shell — Library | Workspace/Canvas | Inspector (R3-BRIEF §4 IA).

Opaque tkinter. No Mica. No second PySide Home. Ingest goes through JobEngine —
job control, not an application lock. Review is a Toplevel on this root; Home
keeps pumping events. Cooperative cancel and pause stop ingest between files
(not mid-file). Progress text comes from process on_event only — no invented percent.

Canvas is first-class in the workspace pane (observation overlay). Canvas never
writes faces.person_id. Toolkit bake-off winner is still human-named (E.5: no
PySide promote).
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except ModuleNotFoundError:  # pragma: no cover - depends on host Python build
    tk = None
    filedialog = messagebox = simpledialog = ttk = None

from semblon.ui_copy import friendly_exception, status_text
from semblon.jobs import JobBusy, JobEngine
from semblon.process import default_store_path
from semblon.progress import (
    KIND_QUEUED,
    KIND_STALLED,
    STAGE_PROCESS,
    ProgressEvent,
    format_duration,
    format_progress_line,
    make_event,
    stills_percent,
)

# Tests and callers import the status line from home_ui.
__all__ = [
    "HOME_NAV",
    "HOME_OBSERVERS",
    "HomeApp",
    "format_library_lines",
    "format_progress_line",
    "home_control_states",
    "resolve_home_observers",
    "run_home_ui",
]
from semblon.watchdog import Watchdog

# Base Home observers (always). Product path may append OCR/CLIP/pose when ready.
HOME_OBSERVERS = "face,color,object"

# R3-BRIEF §4 information architecture (nav ids → label).
HOME_NAV: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("LIBRARY", (("home", "Home"), ("photos", "Photos"), ("videos", "Videos"))),
    ("PEOPLE", (("people", "People"), ("unknown", "Unknown"))),
    ("WORK", (("activity", "Activity"),)),
)

# Job control, not an application lock. These stay usable while ingest runs.
HOME_CONTROLS_ALWAYS_ON = (
    "review",
    "html",
    "people",
    "unknown",
    "activity",
    "settings",
    "canvas",
    "search",
    "live",
)


def resolve_home_observers() -> str:
    """Product observer CSV: base + optional modalities when MODALITY_PRODUCT + ready."""
    from semblon.observers import resolve_product_observers

    return resolve_product_observers()


def resolve_home_prefer_gpu() -> bool:
    """Product GPU prefer flag from honest ORT EP detection."""
    from semblon.engine import product_prefer_gpu

    return product_prefer_gpu()


def home_control_states(
    *,
    job_running: bool,
    resume_ready: bool,
    job_paused: bool = False,
) -> dict[str, str]:
    """NORMAL/DISABLED for each Home control while a job is running.

    Folder / Pause / Resume / Cancel are job controls. Review / People / Search are not.
    Resume while paused = unpause the same job. Resume while idle = resume-after-cancel.
    """
    on, off = "normal", "disabled"
    states = {name: on for name in HOME_CONTROLS_ALWAYS_ON}
    if job_running:
        states["folder"] = off
        states["cancel"] = on
        states["pause"] = off if job_paused else on
        states["resume"] = on if job_paused else off
    else:
        states["folder"] = on
        states["pause"] = off
        states["cancel"] = off
        states["resume"] = on if resume_ready else off
    return states


if tk is None:
    class StillProgressBar:
        """Headless stub for environments without tkinter."""

        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("tkinter is required for home-ui")

        def reset(self) -> None:  # pragma: no cover - stub
            return None

        def set_from_event(self, _ev: ProgressEvent) -> None:  # pragma: no cover - stub
            return None

        def redraw(self) -> None:  # pragma: no cover - stub
            return None
else:
    class StillProgressBar(tk.Canvas):
        """Determinate stills bar. Fills only when the event has a real percent."""

        TRACK = "#1c1c1c"
        FILL = "#3d8bfd"
        TEXT = "#f4f4f4"
        EDGE = "#3a3a3a"

        def __init__(self, master, width: int = 520, height: int = 28, **kw):
            super().__init__(
                master,
                width=width,
                height=height,
                highlightthickness=0,
                bg="#121212",
                **kw,
            )
            self._percent = 0.0
            self._label = "0%"
            self.bind("<Configure>", lambda _e: self.redraw())
            self.redraw()

        def reset(self) -> None:
            self._percent = 0.0
            self._label = "0%"
            self.redraw()

        def set_from_event(self, ev: ProgressEvent) -> None:
            pct = stills_percent(ev)
            if pct is None:
                return
            bits = [f"{pct:g}%"]
            if ev.files_processed is not None and ev.files_total is not None:
                bits.append(f"{ev.files_processed}/{ev.files_total}")
            self._percent = pct
            self._label = "  ".join(bits)
            self.redraw()

        def redraw(self) -> None:
            self.delete("all")
            w = max(int(self.winfo_width() or 520), 8)
            h = max(int(self.winfo_height() or 28), 8)
            pad = 2
            self.create_rectangle(pad, pad, w - pad, h - pad, fill=self.TRACK, outline=self.EDGE)
            inner = w - 2 * pad
            fill_w = pad + int(inner * self._percent / 100.0)
            if self._percent > 0:
                self.create_rectangle(pad, pad, max(pad + 1, fill_w), h - pad, fill=self.FILL, outline="")
            self.create_text(w / 2, h / 2, text=self._label, fill=self.TEXT, font=("Segoe UI", 10, "bold"))


def format_people_lines(rec: dict) -> list[str]:
    items = rec.get("items") or []
    if not items:
        return ["No named people yet. Open Review and Name a cluster or face."]
    return [f"{i.get('display_name') or i.get('person_id')}  ({i.get('faces', 0)} faces)" for i in items]


def format_unknown_lines(rec: dict, run_id: str) -> list[str]:
    c = rec.get("counts") or {}
    return [
        f"run={run_id}",
        f"KNOWN={c.get('KNOWN', 0)}  UNKNOWN={c.get('UNKNOWN', 0)}",
        f"REVIEW_REQUIRED={c.get('REVIEW_REQUIRED', 0)}  REJECTED={c.get('REJECTED', 0)}",
        "UNKNOWN is valid. Identify never auto-assigns a person.",
    ]


def format_search_lines(rec: dict) -> list[str]:
    kind = rec.get("kind")
    if kind == "person":
        items = rec.get("items") or []
        if not items:
            return [f"No named person matching {rec.get('query')!r}."]
        return [f"{i.get('display_name') or i.get('person_id')}  ({i.get('faces', 0)} faces)  {i.get('why','')}" for i in items]
    if kind == "similar":
        lines = [
            f"similar {rec.get('query')}  modality={rec.get('modality')}  pack={rec.get('pack_id')}",
            rec.get("note") or "Similarity is not identity.",
        ]
        for i in rec.get("items") or []:
            score = i.get("score")
            if score is None:
                s = "n/a"
            else:
                try:
                    s = f"{float(score):.4f}"
                except (TypeError, ValueError):
                    s = "n/a"
            lines.append(f"{s}  {i.get('kind')}  {i.get('item_id')}  {i.get('why','')}")
        if rec.get("count") == 0:
            lines.append("No same-space neighbours.")
        return lines
    if kind == "text":
        lines = [
            f"OCR text {rec.get('query')!r}  hits={rec.get('count', 0)}",
            rec.get("note") or "OCR text is not identity.",
        ]
        for i in rec.get("items") or []:
            snippet = (i.get("text") or "")[:80]
            lines.append(f"{i.get('item_id')}  {snippet!r}  {i.get('why', '')}")
        if rec.get("count") == 0:
            lines.append("No OCR text matches.")
        return lines
    return [json_fallback(rec)]


def format_activity_lines(
    *,
    run_line: str,
    integrity_line: str,
    groups: list[dict],
    relationships: list[dict],
    events: list[dict],
    track_count: int,
) -> list[str]:
    lines = [run_line, integrity_line]
    if groups:
        lines.append("observation_groups:")
        for g in groups:
            lines.append(
                f"  kind={g.get('kind')} members={g.get('member_count')} status={g.get('status')} (not a person)"
            )
    else:
        lines.append("observation_groups: none")

    if relationships:
        lines.append("relationships:")
        for r in relationships:
            names = [n for n in (r.get("name_a"), r.get("name_b")) if n]
            ids = [i for i in [r.get("src_person_id"), *(r.get("other_person_ids") or [])] if i]
            who = ", ".join(names) if names else (", ".join(ids) if ids else "unknown")
            lines.append(
                f"  kind={r.get('kind')} people={who} confirmed={r.get('confirmed', 0)}"
            )
    else:
        lines.append("relationships: none")

    if events:
        lines.append("events:")
        for ev in events:
            lines.append(
                f"  {ev.get('label')}  {ev.get('t_start')} -> {ev.get('t_end')}  folder={ev.get('folder')}"
            )
    else:
        lines.append("events: none")

    lines.append(f"tracks={track_count}  (track ≠ person)")
    return lines


def format_library_lines(store: Path, *, source_type: str | None = None) -> list[str]:
    """Library rows: source-media layer (includes zero-face files when present)."""
    if not store.is_file():
        return [f"No store yet: {store}"]
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        if source_type:
            rows = conn.execute(
                """
                SELECT media_id, path, source_type
                FROM media
                WHERE source_type=?
                ORDER BY path
                LIMIT 200
                """,
                (source_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT media_id, path, source_type
                FROM media
                ORDER BY path
                LIMIT 200
                """
            ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    except sqlite3.OperationalError as e:
        conn.close()
        return [f"Library unavailable: {e}"]
    conn.close()
    label = source_type or "all"
    if not rows:
        return [f"Library ({label}): no media yet. Choose a folder to ingest."]
    lines = [f"Library ({label}): showing {len(rows)} of {total}  (source-media layer)"]
    for r in rows:
        lines.append(f"  {r['source_type']}  {r['path']}")
    return lines


def read_activity_snapshot(store: Path, run_id: str) -> dict:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        groups_rows = conn.execute(
            """
            SELECT kind, member_count, status
            FROM observation_groups
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        rel_rows = conn.execute(
            """
            SELECT kind, src_person_id, evidence_json, confirmed
            FROM relationships
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT label, t_start, t_end, folder
            FROM events
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        track_count = int(
            conn.execute("SELECT COUNT(*) FROM tracks WHERE run_id=?", (run_id,)).fetchone()[0]
        )
    finally:
        conn.close()

    groups = [dict(r) for r in groups_rows]
    relationships: list[dict] = []
    for row in rel_rows:
        rel = dict(row)
        evidence = {}
        raw = rel.get("evidence_json")
        if raw:
            try:
                evidence = json.loads(raw)
            except json.JSONDecodeError:
                evidence = {}
        rel["name_a"] = evidence.get("name_a") or evidence.get("src_name")
        rel["name_b"] = evidence.get("name_b") or evidence.get("dst_name")
        ids = evidence.get("person_ids")
        if isinstance(ids, list):
            if not rel.get("src_person_id") and len(ids) > 0:
                rel["src_person_id"] = ids[0]
            rel["other_person_ids"] = [str(i) for i in ids[1:] if i]
        else:
            rel["other_person_ids"] = []
        relationships.append(rel)

    events = [dict(r) for r in event_rows]
    return {
        "groups": groups,
        "relationships": relationships,
        "events": events,
        "track_count": track_count,
    }


def json_fallback(rec: dict) -> str:
    return json.dumps(rec, indent=2)[:4000]


class HomeApp:
    """Production Home shell: sidebar Library + Canvas workspace + Inspector."""

    def __init__(self, store: Path | None = None):
        if tk is None or ttk is None or filedialog is None or messagebox is None:
            raise RuntimeError("tkinter is required for home-ui")
        self.store = Path(store) if store is not None else default_store_path()
        self.engine = JobEngine(self.store)
        self._busy = False
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._last_run_id: str | None = None
        self._last_review_html: Path | None = None
        self._last_folder: Path | None = None
        self._resume_ready = False
        self._q: queue.Queue = queue.Queue()
        self._nav = "home"
        self._nav_buttons: dict[str, ttk.Button] = {}

        self.root = tk.Tk()
        self.root.title("Semblon")
        self.root.minsize(900, 560)
        self.root.geometry("1120x700")

        # ── Top chrome: brand · search · settings ──
        top = ttk.Frame(self.root, padding=(12, 10, 12, 4))
        top.pack(fill=tk.X)
        ttk.Label(top, text="SEMBLON", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)
        self.btn_settings = ttk.Button(top, text="⚙ Settings", command=self._show_settings)
        self.btn_settings.pack(side=tk.RIGHT)
        search_row = ttk.Frame(top)
        search_row.pack(side=tk.RIGHT, padx=(0, 12))
        ttk.Label(search_row, text="Search").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.search_var, width=22).pack(side=tk.LEFT, padx=(6, 0))
        self.btn_search = ttk.Button(search_row, text="Go", command=self._search_person)
        self.btn_search.pack(side=tk.LEFT, padx=(6, 0))

        # ── Job controls (ingest door) ──
        jobs = ttk.Frame(self.root, padding=(12, 0, 12, 4))
        jobs.pack(fill=tk.X)
        self.btn_folder = ttk.Button(jobs, text="Choose folder…", command=self._choose_folder)
        self.btn_folder.pack(side=tk.LEFT)
        self.btn_review = ttk.Button(jobs, text="Open Review", command=self._open_review_ui)
        self.btn_review.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_html = ttk.Button(jobs, text="Open review.html", command=self._open_html)
        self.btn_html.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_pause = ttk.Button(jobs, text="Pause", command=self._request_pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_cancel = ttk.Button(jobs, text="Cancel", command=self._request_cancel, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_resume = ttk.Button(jobs, text="Resume", command=self._resume, state=tk.DISABLED)
        self.btn_resume.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_live = ttk.Button(jobs, text="Live…", command=self._open_live_overlay)
        self.btn_live.pack(side=tk.LEFT, padx=(8, 0))
        # Canvas stays first-class; button focuses Home workspace canvas.
        self.btn_canvas = ttk.Button(jobs, text="Canvas", command=lambda: self._navigate("canvas"))
        self.btn_canvas.pack(side=tk.LEFT, padx=(8, 0))

        # Aliases kept for control-state map (People/Unknown/Activity are sidebar).
        self.btn_people = self.btn_canvas  # placeholder; rebound after sidebar build
        self.btn_unknown = self.btn_canvas
        self.btn_activity = self.btn_canvas

        prog = ttk.Frame(self.root, padding=(12, 0, 12, 6))
        prog.pack(fill=tk.X)
        self.status = tk.StringVar(value=f"Store: {self.store}")
        ttk.Label(prog, textvariable=self.status, wraplength=900, justify=tk.LEFT).pack(
            anchor=tk.W, fill=tk.X
        )
        self.clock = tk.StringVar(value="")
        ttk.Label(prog, textvariable=self.clock, wraplength=900, justify=tk.LEFT).pack(
            anchor=tk.W, fill=tk.X, pady=(2, 2)
        )
        self.bar = StillProgressBar(prog)
        self.bar.pack(fill=tk.X)

        # ── Body: Library | Workspace | Inspector ──
        body = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=3)
        body.columnconfigure(2, weight=2)
        body.rowconfigure(0, weight=1)

        # Library sidebar
        side = ttk.Frame(body, padding=(4, 4))
        side.grid(row=0, column=0, sticky="nsw")
        ttk.Label(side, text="LIBRARY", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 2))
        for section, items in HOME_NAV:
            if section != "LIBRARY":
                ttk.Label(side, text=section, font=("Segoe UI", 9)).pack(
                    anchor=tk.W, pady=(10, 2)
                )
            for nav_id, label in items:
                btn = ttk.Button(side, text=label, command=lambda n=nav_id: self._navigate(n))
                btn.pack(fill=tk.X, pady=1)
                self._nav_buttons[nav_id] = btn

        # Keep job-control map keys: people/unknown/activity point at sidebar buttons.
        self.btn_people = self._nav_buttons["people"]
        self.btn_unknown = self._nav_buttons["unknown"]
        self.btn_activity = self._nav_buttons["activity"]

        # Workspace (Canvas / welcome)
        work = ttk.LabelFrame(body, text="WORKSPACE / INTELLIGENCE CANVAS", padding=6)
        work.grid(row=0, column=1, sticky="nsew", padx=(8, 8))
        self._workspace = work
        self._welcome = ttk.Frame(work)
        ttk.Label(
            self._welcome,
            text="Choose a photo folder to process, or open Review to name people.",
            wraplength=420,
        ).pack(anchor=tk.W, pady=(4, 4))
        ttk.Label(
            self._welcome,
            text="Local-first. buffalo_l weights are internal evaluation only — not a commercial pack.",
            wraplength=420,
        ).pack(anchor=tk.W, pady=(0, 8))
        ttk.Label(
            self._welcome,
            text="Canvas overlays observations here. Identity stays FaceKit; canvas never writes person_id.",
            wraplength=420,
        ).pack(anchor=tk.W)

        from semblon.canvas import CanvasWorkspace

        self._canvas_ws = CanvasWorkspace(
            work,
            store=self.store,
            run_id=self._last_run_id,
            on_select=self._on_canvas_select,
            show_chrome=True,
        )

        # Inspector
        insp = ttk.LabelFrame(body, text="INSPECTOR", padding=6)
        insp.grid(row=0, column=2, sticky="nsew")
        self._inspector_title = tk.StringVar(value="Home")
        ttk.Label(insp, textvariable=self._inspector_title, font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W
        )
        insp_body = ttk.Frame(insp)
        insp_body.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self._inspector = tk.Listbox(insp_body, exportselection=False)
        sb = ttk.Scrollbar(insp_body, orient=tk.VERTICAL, command=self._inspector.yview)
        self._inspector.configure(yscrollcommand=sb.set)
        self._inspector.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_queue)
        self._navigate("home")

    def _set_inspector(self, title: str, lines: list[str]) -> None:
        self._inspector_title.set(title)
        self._inspector.delete(0, tk.END)
        for line in lines:
            self._inspector.insert(tk.END, line)

    def _on_canvas_select(self, media_id: str | None, lines: list[str]) -> None:
        title = "Selection" if media_id else "Canvas"
        self._set_inspector(title, lines)

    def _show_workspace_canvas(
        self,
        *,
        reload: bool = True,
        source_types: tuple[str, ...] | None = None,
    ) -> None:
        self._welcome.pack_forget()
        self._canvas_ws.pack(fill=tk.BOTH, expand=True)
        if reload:
            try:
                self._canvas_ws.reload(
                    self.store, self._last_run_id, source_types=source_types
                )
            except Exception as e:  # noqa: BLE001 — surface in inspector
                self._set_inspector("Canvas", [f"Canvas unavailable: {e}"])

    def _show_workspace_welcome(self) -> None:
        self._canvas_ws.pack_forget()
        self._welcome.pack(fill=tk.BOTH, expand=True, anchor=tk.NW)

    def _navigate(self, nav_id: str) -> None:
        self._nav = nav_id
        if nav_id in {"home", "canvas"}:
            self._show_workspace_canvas(reload=True, source_types=None)
            self._set_inspector(
                "Home" if nav_id == "home" else "Canvas",
                [
                    "Library is the source-media layer.",
                    "People/Unknown is the identity-observation layer.",
                    "Canvas overlays boxes/tracks — never writes faces.person_id.",
                    f"Product observers: {resolve_home_observers()}",
                    f"GPU product path prefer={resolve_home_prefer_gpu()}",
                    "Open Review to name people (cluster → review → person → name).",
                    *format_library_lines(self.store)[:6],
                ],
            )
            return
        if nav_id == "photos":
            # Stills are typically source_type=folder; exclude video assets.
            self._show_workspace_canvas(reload=True, source_types=("folder",))
            lib = format_library_lines(self.store, source_type="folder")
            self._set_inspector(
                "Photos",
                [
                    "Source-media layer. Zero-face files stay here.",
                    "Select a row in Canvas to inspect observation overlays.",
                    *lib,
                ],
            )
            return
        if nav_id == "videos":
            self._show_workspace_canvas(reload=True, source_types=("video",))
            lib = format_library_lines(self.store, source_type="video")
            self._set_inspector(
                "Videos",
                [
                    "One video asset, many observations. Track ≠ person.",
                    "Select a row in Canvas to inspect observation overlays.",
                    *lib,
                ],
            )
            return
        if nav_id == "people":
            self._show_workspace_welcome()
            self._show_people()
            return
        if nav_id == "unknown":
            self._show_workspace_welcome()
            self._show_unknown()
            return
        if nav_id == "activity":
            self._show_workspace_welcome()
            self._show_activity()
            return

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_job_controls()

    def _refresh_job_controls(self) -> None:
        busy = self.engine.busy
        self._busy = busy
        states = home_control_states(
            job_running=busy,
            job_paused=self.engine.paused,
            resume_ready=self._resume_ready,
        )
        buttons = {
            "folder": self.btn_folder,
            "pause": self.btn_pause,
            "resume": self.btn_resume,
            "cancel": self.btn_cancel,
            "review": self.btn_review,
            "html": self.btn_html,
            "people": self.btn_people,
            "unknown": self.btn_unknown,
            "activity": self.btn_activity,
            "settings": self.btn_settings,
            "canvas": self.btn_canvas,
            "live": self.btn_live,
            "search": self.btn_search,
        }
        for key, btn in buttons.items():
            btn.configure(state=tk.NORMAL if states[key] == "normal" else tk.DISABLED)

    def _request_pause(self) -> None:
        if not self.engine.busy or self.engine.paused:
            return
        self.engine.pause()
        self.status.set("Pausing… (stops between files; not mid-file)")
        self._refresh_job_controls()

    def _request_cancel(self) -> None:
        if not self.engine.busy:
            return
        self.engine.cancel()
        self.status.set("Cancelling…")
        self._refresh_job_controls()

    def _start_process(self, path: Path, *, resume: bool) -> None:
        self._last_folder = path
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._resume_ready = False
        self.bar.reset()
        self.clock.set("")
        queued = make_event(STAGE_PROCESS, KIND_QUEUED, path=str(path), outcome="resumed" if resume else None)
        self.status.set(status_text(queued))
        self._set_busy(True)
        observers = resolve_home_observers()
        prefer_gpu = resolve_home_prefer_gpu()

        def on_event(ev: ProgressEvent) -> None:
            self._wd.note(ev)
            self._q.put(("event", ev))

        def on_done(result) -> None:
            if result.status == "completed":
                self._q.put(("done", result.rec or {}))
            elif result.status == "cancelled":
                self._q.put(("cancelled", result.run_id or ""))
            else:
                self._q.put(("error", result.error or RuntimeError("ingest failed")))

        try:
            self.engine.submit_ingest(
                path,
                resume=resume,
                observers=observers,
                prefer_gpu=prefer_gpu,
                on_event=on_event,
                on_done=on_done,
            )
        except JobBusy:
            self._set_busy(False)
            self.status.set("Job busy — ingest already running.")

    def _choose_folder(self) -> None:
        if self.engine.busy:
            return
        folder = filedialog.askdirectory(title="Choose a folder of photos for Semblon")
        if not folder:
            return
        self._start_process(Path(folder), resume=False)

    def _resume(self) -> None:
        # Same-job unpause vs resume-after-cancel (new submit with resume=True).
        if self.engine.paused:
            self.engine.unpause()
            self.status.set("Resuming job…")
            self._refresh_job_controls()
            return
        if self.engine.busy or self._last_folder is None:
            return
        self._start_process(self._last_folder, resume=True)

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "status":
                    self.status.set(payload)
                elif kind == "event":
                    self.status.set(status_text(payload))
                    self.bar.set_from_event(payload)
                    bits = []
                    if payload.clock:
                        bits.append(payload.clock)
                    elapsed = format_duration(payload.elapsed_s)
                    if elapsed:
                        bits.append(f"elapsed {elapsed}")
                    eta = format_duration(payload.eta_s)
                    if eta:
                        bits.append(f"eta {eta}")
                    self.clock.set("   ".join(bits))
                elif kind == "done":
                    self._last_run_id = payload.get("run_id")
                    out = payload.get("out")
                    self._last_review_html = Path(out) if out else None
                    self._resume_ready = False
                    self._set_busy(False)
                    rid = self._last_run_id or "?"
                    self.status.set(f"Done. run_id={rid}  Open Review to name people.")
                    self.bar.set_from_event(
                        make_event(
                            STAGE_PROCESS,
                            "completed",
                            current=1,
                            total=1,
                            files_processed=1,
                            files_total=1,
                        )
                    )
                    if self._nav in {"home", "canvas", "photos", "videos"}:
                        types = None
                        if self._nav == "photos":
                            types = ("folder",)
                        elif self._nav == "videos":
                            types = ("video",)
                        self._show_workspace_canvas(reload=True, source_types=types)
                elif kind == "cancelled":
                    self._resume_ready = self._last_folder is not None
                    self._set_busy(False)
                    extra = f" run_id={payload}" if payload else ""
                    self.status.set(
                        f"Cancelled.{extra} Any partial results have been retained. Resume continues from the next unfinished stage."
                    )
                    if self._exit_after_cancel and self.root.winfo_exists():
                        self.root.destroy()
                        return
                elif kind == "error":
                    self._resume_ready = self._last_folder is not None
                    self._set_busy(False)
                    if isinstance(payload, BaseException):
                        user, detail = friendly_exception(payload)
                        self.status.set(user.replace("\n", " "))
                        messagebox.showerror("Semblon", f"{user}\n\n{detail}" if detail else user)
                    else:
                        self.status.set(f"Couldn't finish. {payload}")
                        messagebox.showerror("Semblon", str(payload))
                    if self._exit_after_cancel and self.root.winfo_exists():
                        self.root.destroy()
                        return
        except queue.Empty:
            pass
        if self.engine.busy:
            if self.engine.paused:
                self.status.set("Paused — not processing; Resume continues this job (between-files pause)")
            stalled = self._wd.check()
            if stalled is not None and stalled.kind == KIND_STALLED and not self.engine.paused:
                self.status.set(status_text(stalled))
            self._refresh_job_controls()
        if self.root.winfo_exists():
            self.root.after(100, self._drain_queue)

    def _open_review_ui(self) -> None:
        from semblon.review_ui import ReviewUiError, run_review_ui

        try:
            # Toplevel on Home's root. Home keeps pumping events. No nested mainloop.
            run_review_ui(store=self.store, run_id=self._last_run_id, parent=self.root)
        except ReviewUiError as e:
            messagebox.showerror("Semblon", str(e))

    def _open_html(self) -> None:
        path = self._last_review_html
        if path is None or not path.is_file():
            from semblon.process import default_review_out

            path = default_review_out(self.store)
        if not path.is_file():
            messagebox.showinfo("Semblon", f"No review.html yet:\n{path}")
            return
        webbrowser.open(path.resolve().as_uri())

    def _list_window(self, title: str, lines: list[str]) -> None:
        """Legacy helper: route into Inspector (no floating list-only windows)."""
        self._set_inspector(title, lines)

    def _show_people(self) -> None:
        from semblon.search import SearchError, search_people

        if not self.store.is_file():
            self._set_inspector("People", [f"No store yet:\n{self.store}"])
            return
        try:
            rec = search_people(self.store)
        except SearchError as e:
            messagebox.showerror("Semblon", str(e))
            return
        self._set_inspector("People", format_people_lines(rec))

    def _show_unknown(self) -> None:
        from semblon.inbox import InboxError, inbox
        from semblon.process import latest_run_id

        if not self.store.is_file():
            self._set_inspector("Unknown", [f"No store yet:\n{self.store}"])
            return
        rid = latest_run_id(self.store, with_faces=True)
        if rid is None:
            self._set_inspector("Unknown", ["Store has no runs with faces."])
            return
        try:
            rec = inbox(self.store, rid)
        except InboxError as e:
            messagebox.showerror("Semblon", str(e))
            return
        self._set_inspector("Unknown", format_unknown_lines(rec, rid))

    def _show_activity(self) -> None:
        from semblon.process import empty_state_line, latest_run_id
        from semblon.store import integrity_report

        if not self.store.is_file():
            self._set_inspector("Activity", [f"No store yet:\n{self.store}"])
            return
        rid = latest_run_id(self.store)
        line = empty_state_line(self.store, rid) if rid else "no runs"
        try:
            integ = integrity_report(self.store)
            extra = f"integrity ok={integ['ok']} unfinished={len(integ['unfinished_runs'])}"
        except OSError as e:
            extra = f"integrity unavailable: {e}"

        if not rid:
            self._set_inspector(
                "Activity",
                format_activity_lines(
                    run_line=line,
                    integrity_line=extra,
                    groups=[],
                    relationships=[],
                    events=[],
                    track_count=0,
                ),
            )
            return

        try:
            rec = read_activity_snapshot(self.store, rid)
        except (sqlite3.DatabaseError, OSError) as e:
            self._set_inspector("Activity", [line, extra, f"activity unavailable: {e}"])
            return
        self._set_inspector(
            "Activity",
            format_activity_lines(
                run_line=line,
                integrity_line=extra,
                groups=rec.get("groups") or [],
                relationships=rec.get("relationships") or [],
                events=rec.get("events") or [],
                track_count=int(rec.get("track_count") or 0),
            ),
        )

    def _open_canvas(self) -> None:
        """First-class canvas is the Home workspace; keep Toplevel as escape hatch."""
        self._navigate("home")

    def _search_person(self) -> None:
        from semblon.gates import MODALITY_PRODUCT, enabled
        from semblon.search import SearchError, search_person, search_text

        q = (self.search_var.get() or "").strip()
        if not q:
            messagebox.showinfo("Semblon", "Type a person name or OCR text.")
            return
        if not self.store.is_file():
            messagebox.showinfo("Semblon", f"No store yet:\n{self.store}")
            return
        try:
            rec = search_person(self.store, q)
        except SearchError as e:
            messagebox.showerror("Semblon", str(e))
            return
        lines = format_search_lines(rec)
        if enabled(MODALITY_PRODUCT) and int(rec.get("count") or 0) == 0:
            try:
                text_rec = search_text(self.store, q)
            except SearchError:
                text_rec = None
            if text_rec is not None and int(text_rec.get("count") or 0) > 0:
                lines.append("")
                lines.extend(format_search_lines(text_rec))
        self._set_inspector("Search", lines)

    def _show_settings(self) -> None:
        from semblon.engine import format_execution_status_lines
        from semblon.observers import modality_product_settings_lines
        from semblon.providers import weights_status

        w = weights_status()
        lines = [
            f"Store: {self.store}",
            "Shell: Library | Workspace/Canvas | Inspector (Tk; R3 toolkit winner still human-named)",
            "Ingest is a JobEngine job, not an application lock. Review/People/Search stay usable.",
            "Pause: cooperative between files (not mid-file); Resume while paused continues the same job",
            "Cancel: between files (not mid-file)",
            "Resume when idle: continues cancelled/interrupted run from next unfinished stage",
            "Stills bar: real files done / files total, climbs to 100%",
            f"Home observers (base): {HOME_OBSERVERS}",
            f"Home observers (product): {resolve_home_observers()}",
            f"Weights dir: {w['dir']}",
            f"onnx files: {w['onnx_count']}  bundled={w['bundled']}",
            w["note"],
        ]
        lines.extend(format_execution_status_lines())
        lines.extend(modality_product_settings_lines())
        self._set_inspector("Settings", lines)

    def _open_live_overlay(self) -> None:
        from semblon.gates import WIRE_HOME_LIVE, enabled, require_human_note
        from semblon.live_overlay import LiveOverlayError, run_live_overlay

        if not enabled(WIRE_HOME_LIVE):
            messagebox.showinfo(
                "Semblon",
                f"Live overlay Home entry is off.\n{require_human_note(WIRE_HOME_LIVE)}",
            )
            return
        if self.engine.busy:
            messagebox.showinfo("Semblon", "Finish or cancel ingest before Live.")
            return
        source = simpledialog.askstring(
            "Live overlay",
            "Camera index or RTSP URL (explicit start — no auto-webcam):",
            initialvalue="0",
            parent=self.root,
        )
        if source is None:
            return
        source = source.strip() or "0"
        try:
            seconds = float(
                simpledialog.askstring(
                    "Live overlay",
                    "Seconds (0 = until you close the window):",
                    initialvalue="30",
                    parent=self.root,
                )
                or "30"
            )
        except ValueError:
            messagebox.showerror("Semblon", "Seconds must be a number.")
            return
        self.status.set("Live overlay running…")
        self.root.update_idletasks()

        def _run() -> None:
            try:
                from semblon.engine import product_prefer_gpu

                src: str | int = int(source) if source.isdigit() else source
                rec = run_live_overlay(
                    self.store,
                    source=src,
                    seconds=seconds,
                    show=True,
                    from_home=True,
                    explicit_flag=False,
                    prefer_gpu=product_prefer_gpu(),
                )
            except Exception as e:  # noqa: BLE001 — surface to Home status
                self.root.after(0, lambda: self._live_failed(e))
                return
            self.root.after(0, lambda: self._live_done(rec))

        threading.Thread(target=_run, name="semblon-home-live", daemon=True).start()

    def _live_failed(self, err: BaseException) -> None:
        self.status.set(friendly_exception(err))
        messagebox.showerror("Semblon Live", friendly_exception(err))

    def _live_done(self, rec: dict) -> None:
        rid = rec.get("run_id") if isinstance(rec, dict) else None
        self.status.set(f"Live overlay done. run_id={rid or '—'}")

    def _on_close(self) -> None:
        if self.engine.busy:
            if messagebox.askyesno(
                "Semblon",
                "Processing is still running. Cancel and exit?",
            ):
                self._exit_after_cancel = True
                self._request_cancel()
            return
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_home_ui(store: Path | None = None) -> int:
    HomeApp(store=store).run()
    return 0
