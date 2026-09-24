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

from semblon.ui_copy import friendly_exception
from semblon.jobs import JobBusy, JobEngine
from semblon.process import default_store_path
from semblon.state_triple import (
    format_media_card_label,
    library_include_media,
    triples_for_board,
)
from semblon.progress import (
    KIND_QUEUED,
    KIND_STALLED,
    STAGE_PROCESS,
    ProgressEvent,
    format_progress_line,
    make_event,
    stills_percent,
)
from semblon.empty_states import (
    SEARCH_PLACEHOLDER,
    SEARCH_PLACEHOLDER_PHOTOS,
    activity_empty,
    activity_history_lines,
    failure_dialog_for,
    groups_waiting_line,
    is_expected_condition,
    library_has_media_lines,
    people_empty,
    photos_empty,
    search_library_analysing,
    search_no_matches,
    search_no_named_people,
    search_no_store,
    search_placeholder,
    search_result_lines,
    show_failure_dialog,
    to_review_empty,
    videos_empty,
)

# Visual design language — one token module. Soft import so Home still
# constructs if a partial checkout is missing the foundation.
try:
    from semblon.ui_icons import NAV_ICONS, draw as draw_icon
    from semblon.ui_theme import apply_theme, style_listbox
    from semblon.ui_tokens import (
        ACCENT,
        BG_CANVAS,
        BG_DARK,
        BG_SUBTLE,
        BG_SURFACE,
        BODY,
        BODY_SMALL,
        BODY_STRONG,
        BORDER_SUBTLE,
        CAPTION,
        DISPLAY,
        META,
        MONO,
        H1,
        H2,
        H3,
        INK_TERTIARY,
        SIDEBAR_WIDTH,
        SP_4,
        SP_8,
        SP_12,
        SP_16,
        SP_20,
        SP_24,
        SP_32,
        SP_48,
        SUCCESS,
        SURFACE_PRIMARY,
        TEXT_DISABLED,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        WINDOW_DEFAULT,
        WINDOW_MIN,
        tracked,
    )
    from semblon.ui_widgets import Button
except ImportError:  # pragma: no cover - mid-merge stub
    NAV_ICONS = {}
    draw_icon = None
    apply_theme = None
    style_listbox = None
    Button = None
    ACCENT = "#2E6BE6"
    BG_CANVAS = "#FFFFFF"
    BG_DARK = "#1C1C1D"
    BG_SUBTLE = "#F5F5F4"
    BG_SURFACE = "#FFFFFF"
    BODY = ("Segoe UI", 16)
    BODY_SMALL = ("Segoe UI", 15)
    BODY_STRONG = ("Segoe UI", 16, "bold")
    BORDER_SUBTLE = "#E4E4E2"
    CAPTION = ("Segoe UI", 12)
    DISPLAY = ("Segoe UI", 32, "bold")
    H1 = ("Segoe UI", 20, "bold")
    H2 = ("Segoe UI", 20, "bold")
    H3 = ("Segoe UI", 14)
    INK_TERTIARY = "#8A8A8A"
    META = ("Segoe UI", 13)
    MONO = ("Cascadia Code", 13)
    SIDEBAR_WIDTH = 228
    SP_4 = 4
    SP_8 = 8
    SP_12 = 12
    SP_16 = 16
    SP_20 = 20
    SP_24 = 24
    SP_32 = 32
    SP_48 = 48
    SUCCESS = "#1A7F37"
    SURFACE_PRIMARY = "#FFFFFF"
    TEXT_DISABLED = "#B9B9B9"
    TEXT_PRIMARY = "#171717"
    TEXT_SECONDARY = "#565656"
    WINDOW_DEFAULT = (1200, 780)
    WINDOW_MIN = (960, 640)

    def tracked(text: str) -> str:
        return " ".join(text.upper())

# Idle status (UX Rescue §10) — no Store: path.
HOME_IDLE_STATUS = "Ready — choose a folder of photos to begin."

# Soft Inspector defaults (UX Rescue §5) — architecture strings live in Advanced.
INSPECTOR_HOME_EMPTY = (
    "Your results will appear here",
    "Add a photo folder to get started.",
)
INSPECTOR_EMPTY = (
    "Nothing selected",
    "Select a photo, person, or result to see more details.",
)

# Tests and callers import the status line from home_ui.
__all__ = [
    "HOME_IDLE_STATUS",
    "HOME_NAV",
    "HOME_OBSERVERS",
    "INSPECTOR_EMPTY",
    "INSPECTOR_HOME_EMPTY",
    "HomeApp",
    "format_library_lines",
    "format_progress_line",
    "home_control_states",
    "landing_cta_plan",
    "landing_step_states",
    "resolve_home_observers",
    "run_home_ui",
]

# Re-export verb policy helpers for tests / application façade consumers.
from semblon.inspector_verbs import (  # noqa: E402
    inspector_verb_states as inspector_verb_states,
)
from semblon.watchdog import Watchdog

# Base Home observers (always). Product path may append OCR/CLIP/pose when ready.
HOME_OBSERVERS = "face,color,object"

# Dashboard route id stays "home". The sidebar label is Photos — Home was
# the redundant item. The photo grid remains route id "photos".
HOME_NAV: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("LIBRARY", (("home", "Photos"), ("videos", "Videos"))),
    ("PEOPLE", (("people", "People"), ("unknown", "To review"))),
    ("ACTIVITY", (("activity", "Recent activity"),)),
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


def landing_step_states(*, files: int, unnamed: int) -> list[dict]:
    """Pure Home landing step progression. phase: idle | current | done."""
    if files <= 0:
        return [
            {
                "marker": "1",
                "title": "Add your photos",
                "desc": "Add a photo folder to begin.",
                "phase": "current",
            },
            {
                "marker": "2",
                "title": "Semblon finds",
                "desc": "Similar faces are grouped together.",
                "phase": "idle",
            },
            {
                "marker": "3",
                "title": "Review and name",
                "desc": "Review the groups and name the people.",
                "phase": "idle",
            },
        ]
    if unnamed > 0:
        return [
            {
                "marker": "✓",
                "title": "Add your photos",
                "desc": "Folder added.",
                "phase": "done",
            },
            {
                "marker": "✓",
                "title": "Semblon finds",
                "desc": "Scan complete.",
                "phase": "done",
            },
            {
                "marker": "3",
                "title": "Review and name",
                "desc": "Review the groups and name the people.",
                "phase": "current",
            },
        ]
    return [
        {
            "marker": "✓",
            "title": "Add your photos",
            "desc": "Folder added.",
            "phase": "done",
        },
        {
            "marker": "✓",
            "title": "Semblon finds",
            "desc": "Scan complete.",
            "phase": "done",
        },
        {
            "marker": "✓",
            "title": "Review and name",
            "desc": "You're caught up.",
            "phase": "done",
        },
    ]


def landing_cta_plan(*, files: int, unnamed: int) -> dict:
    """Which landing CTAs to show and which is primary.

    primary: ``add`` | ``review`` | ``browse``
    """
    if files <= 0:
        return {
            "primary": "add",
            "show_review": False,
            "show_browse": False,
            "show_privacy": True,
            "add_label": "Add a photo folder",
            "review_label": "Review suggestions",
        }
    if unnamed > 0:
        return {
            "primary": "review",
            "show_review": True,
            "show_browse": True,
            "show_privacy": False,
            "add_label": "Add a photo folder",
            "review_label": f"Review {unnamed} suggestions",
        }
    return {
        "primary": "browse",
        "show_review": False,
        "show_browse": True,
        "show_privacy": False,
        "add_label": "Add another folder",
        "review_label": "Review suggestions",
    }


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

        def set_percent(self, _pct: float | None) -> None:  # pragma: no cover - stub
            return None

        def redraw(self) -> None:  # pragma: no cover - stub
            return None
else:
    class StillProgressBar(tk.Canvas):
        """Determinate stills bar. Fills only when the event has a real percent."""

        TRACK = BG_SUBTLE
        FILL = ACCENT
        TEXT = INK_TERTIARY
        EDGE = BG_SUBTLE

        def __init__(self, master, width: int = 520, height: int = 14, **kw):
            from semblon.ui_theme import px

            # Substantial track — not a hairline (product processing Home).
            self._design_h = max(10, int(height))
            super().__init__(
                master,
                width=width,
                height=px(master, self._design_h),
                highlightthickness=0,
                bg=BG_CANVAS,
                **kw,
            )
            self._percent = 0.0
            self._label = ""
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
            self._percent = pct
            # Counts stay on the status line. The bar itself is only the fill.
            self._label = ""
            self.redraw()

        def set_percent(self, pct: float | None) -> None:
            if pct is None:
                return
            self._percent = max(0.0, min(100.0, float(pct)))
            self._label = ""
            self.redraw()

        def redraw(self) -> None:
            self.delete("all")
            w = max(int(self.winfo_width() or 520), 8)
            h = max(int(self.winfo_height() or self._design_h), self._design_h)
            radius = h / 2
            self._pill(0, 0, w, h, radius, fill=self.TRACK)
            fill_w = int(w * self._percent / 100.0)
            if self._percent > 0 and fill_w > 1:
                self._pill(0, 0, max(h, fill_w), h, radius, fill=self.FILL)

        def _pill(self, x1, y1, x2, y2, r, fill: str) -> None:
            self.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")

def format_people_lines(rec: dict) -> list[str]:
    items = rec.get("items") or []
    if not items:
        return people_empty().as_lines()
    return [
        f"{i.get('display_name') or i.get('person_id')}  ({i.get('faces', 0)} photos)"
        for i in items
    ]


def format_unknown_lines(
    rec: dict, run_id: str, *, advanced: bool = False
) -> list[str]:
    """§13 To review — soft counts by default; KNOWN=/UNKNOWN= only when advanced."""
    c = rec.get("counts") or {}
    waiting = int(c.get("UNKNOWN", 0) or 0) + int(c.get("REVIEW_REQUIRED", 0) or 0)
    lines = [groups_waiting_line(waiting)]
    if advanced:
        lines.extend(
            [
                f"run={run_id}",
                f"KNOWN={c.get('KNOWN', 0)}  UNKNOWN={c.get('UNKNOWN', 0)}",
                f"REVIEW_REQUIRED={c.get('REVIEW_REQUIRED', 0)}  REJECTED={c.get('REJECTED', 0)}",
                "UNKNOWN is valid. Identify never auto-assigns a person.",
            ]
        )
    return lines


def format_search_lines(rec: dict, *, advanced: bool = False) -> list[str]:
    """§16 — demote modality=/pack= unless advanced=True."""
    lines = search_result_lines(rec, advanced=advanced)
    if lines:
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
    photos: int | None = None,
    faces: int | None = None,
    stamped: str | None = None,
    has_unnamed: bool = False,
    advanced: bool = False,
    group_count: int | None = None,
) -> list[str]:
    """§14 Recent activity — history rows by default; jargon only when advanced."""
    group_n = (
        int(group_count)
        if group_count is not None
        else (len(groups) if groups else 0)
    )
    soft = activity_history_lines(
        photos=photos,
        faces=faces if faces is not None else None,
        groups=group_n,
        stamped=stamped,
        has_unnamed=has_unnamed,
    )
    # Prefer a soft title derived from run_line only when no photo count given.
    if photos is None and run_line and not run_line.lower().startswith("run="):
        soft = [run_line, *soft[1:]] if soft else [run_line]
    if not advanced:
        return soft

    lines = list(soft)
    lines.append(run_line)
    lines.append(integrity_line)
    if groups:
        lines.append("observation_groups:")
        for g in groups:
            lines.append(
                f"  kind={g.get('kind')} members={g.get('member_count')} "
                f"status={g.get('status')} (not a person)"
            )
    else:
        lines.append("observation_groups: none")

    if relationships:
        lines.append("relationships:")
        for r in relationships:
            names = [n for n in (r.get("name_a"), r.get("name_b")) if n]
            ids = [
                i
                for i in [r.get("src_person_id"), *(r.get("other_person_ids") or [])]
                if i
            ]
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
                f"  {ev.get('label')}  {ev.get('t_start')} -> {ev.get('t_end')}  "
                f"folder={ev.get('folder')}"
            )
    else:
        lines.append("events: none")

    lines.append(f"tracks={track_count}  (track ≠ person)")
    return lines


def format_library_lines(store: Path, *, source_type: str | None = None) -> list[str]:
    """Library rows: source-media layer with Artifact 2 state-triple channels.

    Channels (must not collide): identity=notch · analysis=ring · ingest=glyph.
    Failed ingest is excluded (belongs in Activity, not Library cards).
    """
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
        from semblon.process import latest_run_id

        rid = latest_run_id(Path(store), with_faces=True) or latest_run_id(Path(store))
        faces: list[dict] = []
        decisions: list[dict] = []
        clusters: list[dict] = []
        observed: set[str] = set()
        run_finished = None
        if rid:
            faces = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT f.face_id, f.cluster_id, f.person_id, f.status, o.media_id
                    FROM faces f
                    JOIN observations o ON o.observation_id = f.observation_id
                    WHERE f.run_id=?
                    """,
                    (rid,),
                ).fetchall()
            ]
            decisions = [
                dict(r)
                for r in conn.execute(
                    "SELECT kind, face_id, person_id, cluster_id, policy_json "
                    "FROM decisions WHERE run_id=?",
                    (rid,),
                ).fetchall()
            ]
            clusters = [
                dict(r)
                for r in conn.execute(
                    "SELECT cluster_id, status FROM clusters WHERE run_id=?",
                    (rid,),
                ).fetchall()
            ]
            observed = {
                str(r[0])
                for r in conn.execute(
                    "SELECT DISTINCT media_id FROM observations WHERE run_id=?",
                    (rid,),
                ).fetchall()
            }
            fin = conn.execute(
                "SELECT finished_at FROM runs WHERE run_id=?", (rid,)
            ).fetchone()
            if fin is not None:
                run_finished = fin["finished_at"] is not None
    except sqlite3.OperationalError as e:
        conn.close()
        return [f"Library unavailable: {e}"]
    conn.close()
    label = source_type or "all"
    if not rows:
        return [f"Library ({label}): no media yet. Choose a folder to ingest."]

    media_rows = [dict(r) for r in rows]
    cluster_status = {
        str(c["cluster_id"]): str(c.get("status") or "auto") for c in clusters
    }
    face_counts: dict[str, int] = {}
    for f in faces:
        mid = str(f.get("media_id") or "")
        face_counts[mid] = face_counts.get(mid, 0) + 1
    board = {"media": media_rows, "faces": faces, "decisions": decisions, "items": []}
    triples = triples_for_board(
        board,
        media_rows=media_rows,
        decisions=decisions,
        cluster_status=cluster_status,
        run_finished=run_finished,
        observed_media_ids=observed,
    )
    lines = [
        f"Library ({label}): showing {len(rows)} of {total}  "
        f"(source-media · state=(Ingest, Analysis, Identity))"
    ]
    shown = 0
    for m in media_rows:
        mid = str(m["media_id"])
        triple = triples.get(mid)
        if triple is not None and not library_include_media(triple):
            continue
        shown += 1
        if triple is None:
            lines.append(f"  {m['source_type']}  {m['path']}")
        else:
            lines.append(
                "  "
                + format_media_card_label(
                    m, triple, face_count=face_counts.get(mid, 0)
                )
            )
    if shown != len(rows):
        lines[0] = (
            f"Library ({label}): showing {shown} of {total}  "
            f"(source-media · state triple; failed ingest omitted)"
        )
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


def _format_sel_item(it: dict) -> str:
    """One-line label for Inspector selection — soft product copy, never bare UUIDs."""
    from semblon.product_surface import soft_sel_item_label

    return soft_sel_item_label(it)


def _recent_face_paths(store: Path, *, limit: int = 8) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Cheap RO sample of recent ok faces with media paths. No identity writes."""
    if limit <= 0 or not store.is_file():
        return []
    conn = sqlite3.connect(str(store))
    try:
        conn.execute("PRAGMA busy_timeout=2000")
        rows = conn.execute(
            """
            SELECT m.path, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2
            FROM faces f
            JOIN observations o ON o.observation_id = f.observation_id
            JOIN media m ON m.media_id = o.media_id
            WHERE f.status = 'ok'
            ORDER BY f.rowid DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    out: list[tuple[str, tuple[float, float, float, float]]] = []
    for path, x1, y1, x2, y2 in rows:
        if not path or None in (x1, y1, x2, y2):
            continue
        out.append((str(path), (float(x1), float(y1), float(x2), float(y2))))
    return out


def _button(master, text, command, kind="secondary", icon=None, plate=None):
    """One button class. Falls back to ttk only if the canvas control is absent."""
    if Button is None or tk is None:
        return ttk.Button(master, text=text, command=command)
    return Button(
        master, text=text, command=command, kind=kind, icon=icon, plate=plate or BG_CANVAS
    )


class HomeApp:
    """Production Home shell: sidebar Library + Canvas workspace + Inspector.

    Pane roles stay addressable for the shell layout. Visible chrome uses the
    visual design language (no all-caps LabelFrame titles).
    """

    _PANE_WORKSPACE = "WORKSPACE / INTELLIGENCE CANVAS"
    _PANE_INSPECTOR = "INSPECTOR"

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
        self._prefer_gpu_user: bool | None = None  # Settings toggle; None = product default
        self._completion: dict | None = None  # last done/cancelled summary for §11 card
        self._completion_kind: str | None = None  # "done" | "cancelled" | None
        self._last_progress_files: tuple[int | None, int | None] = (None, None)
        self._last_faces_found: int | None = None
        self._proc_thumbs_faces: int | None = None
        self._inspector_collapsed = False
        self._settings_win: tk.Toplevel | None = None
        self._last_progress_event: ProgressEvent | None = None
        from semblon.scan_present import ScanPace

        self._scan_pace = ScanPace()
        self._apply_saved_theme()

        self.root = tk.Tk()
        self.root.title("Semblon")
        from semblon.ui_theme import px

        self.root.minsize(px(self.root, WINDOW_MIN[0]), px(self.root, WINDOW_MIN[1]))
        self.root.geometry(
            f"{px(self.root, WINDOW_DEFAULT[0])}x{px(self.root, WINDOW_DEFAULT[1])}"
        )
        if apply_theme is not None:
            apply_theme(self.root)
        try:
            self.root.configure(bg=BG_CANVAS)
        except tk.TclError:
            pass
        self._workspace_role = self._PANE_WORKSPACE
        self._inspector_role = self._PANE_INSPECTOR

        # Sidebar is full height. Search and Settings sit over the content only.
        self._shell = tk.Frame(self.root, bg=BG_CANVAS)
        self._shell.pack(fill=tk.BOTH, expand=True)
        self._main = ttk.Frame(self._shell)
        self._main.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ── Top chrome: search · settings ──
        top = ttk.Frame(self._main, padding=(SP_20, SP_12, SP_20, SP_12))
        top.pack(fill=tk.X)
        self._top = top
        self.btn_settings = _button(
            top, "", self._show_settings, kind="secondary", icon="settings"
        )
        self.btn_settings.pack(side=tk.RIGHT)
        search_row = ttk.Frame(top)
        search_row.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, SP_12))
        self.search_var = tk.StringVar()
        self._search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=28)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._search_placeholder = SEARCH_PLACEHOLDER_PHOTOS
        self._search_entry.insert(0, self._search_placeholder)
        try:
            self._search_entry.configure(foreground=INK_TERTIARY)
        except tk.TclError:
            pass
        self._search_entry.bind("<FocusIn>", self._search_focus_in)
        self._search_entry.bind("<FocusOut>", self._search_focus_out)
        # Kept for the control-state map. Enter submits the field.
        self.btn_search = _button(
            search_row, "Search", self._search_person, kind="tertiary", icon="search"
        )
        self._search_entry.bind("<Return>", lambda _e: self._search_person())
        self.root.bind("<Control-f>", lambda _e: self._search_entry.focus_set())
        self.root.bind("<Control-k>", self._open_command_palette)
        self.root.bind("<Control-Key-1>", lambda _e: self._navigate("home"))
        self.root.bind("<Control-Key-2>", lambda _e: self._navigate("videos"))
        self.root.bind("<Control-Key-3>", lambda _e: self._navigate("people"))
        self.root.bind("<Control-Key-4>", lambda _e: self._navigate("unknown"))
        self.root.bind("<Control-Key-5>", lambda _e: self._navigate("activity"))

        # ── Job controls (demoted on home — UX Rescue §3) ──
        jobs = ttk.Frame(self._main, padding=(12, 0, 12, 4))
        jobs.pack(fill=tk.X)
        self._jobs_frame = jobs
        self.btn_folder = _button(
            jobs, "Choose folder…", self._choose_folder, kind="secondary", icon="folder-plus"
        )
        # Pack later via _sync_chrome_for_route (hidden on cold home; CTA is on landing).
        self.btn_review = _button(jobs, "Open Review", self._open_review_ui, kind="secondary")
        self.btn_html = _button(jobs, "Open review.html", self._open_html, kind="tertiary")
        self.btn_cancel = _button(jobs, "Cancel", self._request_cancel, kind="tertiary")
        self.btn_cancel.configure(state=tk.DISABLED)
        # Pause/Resume live next to the progress bar as a single toggle (§3 / §10).
        self.btn_pause = _button(
            jobs, "Pause", self._toggle_pause_resume, kind="tertiary", icon="pause"
        )
        self.btn_pause.configure(state=tk.DISABLED)
        self.btn_resume = self.btn_pause  # alias: one toggle control
        self.btn_live = _button(jobs, "Live…", self._open_live_overlay, kind="tertiary")
        self.btn_canvas = _button(
            jobs, "Canvas", lambda: self._navigate("canvas"), kind="tertiary", icon="images"
        )
        # Advanced actions stay off the top bar. The menu is on the job row.
        self._overflow = ttk.Menubutton(jobs, text="More")
        self._overflow.pack(side=tk.RIGHT, padx=(SP_8, 0))
        self._overflow_menu = tk.Menu(self._overflow, tearoff=0)
        self._overflow_menu.add_command(label="Open Review", command=self._open_review_ui)
        self._overflow_menu.add_command(label="Live…", command=self._open_live_overlay)
        self._overflow_menu.add_command(label="Open review.html", command=self._open_html)
        self._overflow_menu.add_command(
            label="Browse photos", command=lambda: self._navigate("photos")
        )
        self._overflow_menu.add_command(
            label="Explore workspace", command=lambda: self._navigate("canvas")
        )
        self._overflow.configure(menu=self._overflow_menu)

        # Aliases rebound after sidebar build.
        self.btn_people = self.btn_canvas
        self.btn_unknown = self.btn_canvas
        self.btn_activity = self.btn_canvas

        prog = ttk.Frame(self._main, padding=(12, 0, 12, 6))
        prog.pack(fill=tk.X)
        self._prog_frame = prog
        self.status = tk.StringVar(value=HOME_IDLE_STATUS)
        self._status_label = ttk.Label(
            prog,
            textvariable=self.status,
            wraplength=900,
            justify=tk.LEFT,
            font=BODY_SMALL,
            foreground=TEXT_SECONDARY,
        )
        self._status_label.pack(anchor=tk.W, fill=tk.X)
        self.clock = tk.StringVar(value="")
        self._clock_label = ttk.Label(
            prog,
            textvariable=self.clock,
            wraplength=900,
            justify=tk.LEFT,
            font=CAPTION,
            foreground=INK_TERTIARY,
        )
        self._clock_label.pack(anchor=tk.W, fill=tk.X, pady=(2, SP_8))
        bar_row = ttk.Frame(prog)
        bar_row.pack(fill=tk.X)
        self._bar_row = bar_row
        self.bar = StillProgressBar(bar_row)
        self.bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_pause_toggle = _button(
            bar_row, "Pause", self._toggle_pause_resume, kind="tertiary", icon="pause"
        )
        self.btn_pause_toggle.configure(state=tk.DISABLED)
        # Keep btn_pause pointing at the visible toggle for control-state map.
        self.btn_pause = self.btn_pause_toggle
        self.btn_resume = self.btn_pause_toggle
        self.btn_cancel_prog = _button(bar_row, "Cancel", self._request_cancel, kind="tertiary")
        self.btn_cancel_prog.configure(state=tk.DISABLED)
        # Prefer progress-adjacent Cancel when processing; job-bar Cancel unused on home.
        self.btn_cancel = self.btn_cancel_prog

        # ── Body: Library | Workspace | Inspector ──
        self._library_status = tk.StringVar(value="")
        self._status_bar = ttk.Label(
            self._main,
            textvariable=self._library_status,
            font=META,
            foreground=TEXT_SECONDARY,
            padding=(SP_20, SP_8),
        )
        self._status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        body = ttk.Frame(self._main, padding=(8, 0, 8, 8))
        body.pack(fill=tk.BOTH, expand=True)
        self._body = body
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Library sidebar — navigation, not a diagnostic listing.
        side = tk.Frame(
            self._shell,
            bg=BG_SUBTLE,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            highlightcolor=BORDER_SUBTLE,
        )
        side.pack(side=tk.LEFT, fill=tk.Y)
        self._sidebar = side
        self._sidebar_brand = tk.Label(
            side,
            text="Semblon",
            font=H1,
            bg=BG_SUBTLE,
            fg=TEXT_PRIMARY,
        )
        self._sidebar_brand.pack(anchor=tk.W, padx=SP_16, pady=(SP_16, SP_8))
        self._sidebar_footer = tk.Label(
            side,
            text="Local only — nothing is uploaded",
            font=CAPTION,
            bg=BG_SUBTLE,
            fg=INK_TERTIARY,
            wraplength=200,
            justify=tk.LEFT,
        )
        self._sidebar_footer.pack(side=tk.BOTTOM, anchor=tk.W, padx=SP_16, pady=SP_16)
        _section_labels = {
            "LIBRARY": "Library",
            "PEOPLE": "People",
            "ACTIVITY": "Activity",
        }
        for section, items in HOME_NAV:
            tk.Label(
                side,
                text=_section_labels.get(section, section),
                font=CAPTION,
                bg=BG_SUBTLE,
                fg=INK_TERTIARY,
            ).pack(anchor=tk.W, pady=(SP_24 if section != "LIBRARY" else SP_8, SP_8), padx=(SP_16, SP_8))
            for nav_id, label in items:
                icon_name = "images" if nav_id == "home" else NAV_ICONS.get(nav_id)
                btn = _button(
                    side,
                    label,
                    lambda n=nav_id: self._navigate(n),
                    kind="nav",
                    icon=icon_name,
                    plate=BG_SUBTLE,
                )
                btn.pack(fill=tk.X, pady=1, padx=SP_4)
                self._nav_buttons[nav_id] = btn

        # Keep job-control map keys: people/unknown/activity point at sidebar buttons.
        self.btn_people = self._nav_buttons["people"]
        self.btn_unknown = self._nav_buttons["unknown"]
        self.btn_activity = self._nav_buttons["activity"]

        # Workspace (landing / Canvas / welcome). Role: WORKSPACE / INTELLIGENCE CANVAS.
        work = ttk.Frame(body, padding=(SP_16, SP_8))
        work.grid(row=0, column=0, sticky="nsew", padx=(SP_8, SP_8))
        self._workspace = work
        self._welcome = ttk.Frame(work, padding=(SP_8, SP_16))
        self._welcome_title = tk.StringVar(value="")
        ttk.Label(self._welcome, textvariable=self._welcome_title, font=H1).pack(
            anchor=tk.W, pady=(0, SP_8)
        )
        ttk.Label(
            self._welcome,
            text="Details stay in the panel on the right.",
            wraplength=480,
            font=BODY,
            foreground=TEXT_SECONDARY,
        ).pack(anchor=tk.W)

        # Cold-launch landing / processing / result (state machine — not stacked).
        self._landing = ttk.Frame(work)
        self._processing = ttk.Frame(work)
        self._result_card = ttk.Frame(work)
        self._build_home_landing()
        self._build_processing_home()
        self._build_result_card_shell()

        from semblon.canvas import CanvasWorkspace

        # Defer store load: CanvasWorkspace.reload → on_select must not run before
        # Inspector widgets exist, and before this attribute assignment completes.
        self._canvas_ws = CanvasWorkspace(
            work,
            store=None,
            run_id=None,
            on_select=self._on_canvas_select,
            show_chrome=True,
        )

        # Inspector — contextual result for the current interaction.
        insp = ttk.Frame(body, padding=(SP_16, SP_16))
        insp.grid(row=0, column=1, sticky="nsew")
        self._inspector_frame = insp
        self._inspector_title = tk.StringVar(value="Home")
        ttk.Label(insp, textvariable=self._inspector_title, font=H3).pack(
            anchor=tk.W, pady=(0, SP_16)
        )

        from semblon.product_surface import (
            DETAILS_HEADING,
            SEL_HEADING_IDLE,
            VERB_LABEL_ASSIGN,
            VERB_LABEL_IGNORE,
            VERB_LABEL_MERGE,
            VERB_LABEL_NAME,
            VERB_LABEL_RULE_OUT,
            VERB_LABEL_SPLIT,
        )

        # Heading reflects what was selected — not "Selection" ontology.
        self._sel_heading = tk.StringVar(value=SEL_HEADING_IDLE)
        ttk.Label(insp, textvariable=self._sel_heading, font=CAPTION).pack(
            anchor=tk.W, pady=(6, 0)
        )
        sel_frame = ttk.Frame(insp)
        sel_frame.pack(fill=tk.X, pady=(2, 4))
        self._sel_list = tk.Listbox(
            sel_frame, exportselection=False, selectmode=tk.EXTENDED, height=5
        )
        if style_listbox is not None:
            style_listbox(self._sel_list)
        sel_sb = ttk.Scrollbar(sel_frame, orient=tk.VERTICAL, command=self._sel_list.yview)
        self._sel_list.configure(yscrollcommand=sel_sb.set)
        self._sel_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sel_sb.pack(side=tk.LEFT, fill=tk.Y)
        self._sel_list.bind("<<ListboxSelect>>", lambda _e: self._on_inspector_sel_change())

        ttk.Label(insp, text=DETAILS_HEADING, font=CAPTION).pack(
            anchor=tk.W, pady=(4, 0)
        )
        evid_frame = ttk.Frame(insp)
        evid_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 4))
        self._inspector = tk.Listbox(evid_frame, exportselection=False, height=8)
        if style_listbox is not None:
            style_listbox(self._inspector)
        sb = ttk.Scrollbar(evid_frame, orient=tk.VERTICAL, command=self._inspector.yview)
        self._inspector.configure(yscrollcommand=sb.set)
        self._inspector.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(insp, text="What you can do", font=CAPTION).pack(
            anchor=tk.W, pady=(4, 0)
        )
        ttk.Label(
            insp,
            text="Name someone when you recognise them. Combining groups is separate from naming.",
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=260,
        ).pack(anchor=tk.W)

        actions = ttk.Frame(insp)
        actions.pack(fill=tk.X, pady=(4, 0))
        self._verb_reason = tk.StringVar(value="")

        # Primary action first: name the person you selected.
        name_row = ttk.Frame(actions)
        name_row.pack(fill=tk.X, pady=1)
        ttk.Label(name_row, text=VERB_LABEL_NAME).pack(side=tk.LEFT)
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(name_row, textvariable=self._name_var)
        self._name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self._name_entry.bind("<Return>", lambda _e: self._inspector_name_commit())
        self._name_entry.bind("<Escape>", lambda _e: self._inspector_name_cancel())

        self.btn_assign = _button(
            actions, VERB_LABEL_ASSIGN, self._inspector_assign, kind="primary"
        )
        self.btn_assign.pack(fill=tk.X, pady=1)
        self.btn_merge = _button(
            actions, VERB_LABEL_MERGE, self._inspector_merge, kind="secondary"
        )
        self.btn_merge.pack(fill=tk.X, pady=1)
        self.btn_split = _button(
            actions, VERB_LABEL_SPLIT, self._inspector_split, kind="secondary"
        )
        self.btn_split.pack(fill=tk.X, pady=1)

        self.btn_rule_out = _button(
            actions, VERB_LABEL_RULE_OUT, self._inspector_rule_out, kind="destructive"
        )
        self.btn_rule_out.pack(fill=tk.X, pady=1)
        self.btn_ignore = _button(
            actions, VERB_LABEL_IGNORE, self._inspector_ignore, kind="secondary"
        )
        self.btn_ignore.pack(fill=tk.X, pady=1)
        ttk.Label(insp, textvariable=self._verb_reason, wraplength=260).pack(
            anchor=tk.W, pady=(4, 0)
        )

        # Selection context for Inspector verbs (not identity).
        self._insp_run_id: str | None = None
        self._insp_media_id: str | None = None
        self._insp_available: list[dict] = []
        self._insp_selected: list[dict] = []
        self._insp_target_person_id: str | None = None
        self._insp_target_person_name: str | None = None
        self._verb_states: dict = {}

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_queue)
        self._navigate("home")

    def _set_inspector(self, title: str, lines: list[str]) -> None:
        self._inspector_title.set(title)
        if hasattr(self, "_sel_heading") and title in {
            "Home",
            "Canvas",
            "Photos",
            "Videos",
            "Activity",
            "Recent activity",
            "Settings",
            "Search",
            "To review",
            "People",
        }:
            from semblon.product_surface import SEL_HEADING_IDLE

            self._sel_heading.set(SEL_HEADING_IDLE)
        self._inspector.delete(0, tk.END)
        for line in lines:
            self._inspector.insert(tk.END, line)
        # Non-selection views keep verb disable reasons honest.
        if title in {
            "Home",
            "Canvas",
            "Photos",
            "Videos",
            "Activity",
            "Recent activity",
            "Settings",
            "Search",
            "To review",
        }:
            self._sel_list.bind("<<ListboxSelect>>", lambda _e: self._on_inspector_sel_change())
            if title != "Canvas":
                self._insp_available = []
                self._insp_selected = []
                self._insp_media_id = None
                self._sel_list.delete(0, tk.END)
        self._refresh_inspector_verbs()

    def _set_inspector_selection(
        self,
        *,
        run_id: str | None,
        media_id: str | None,
        available: list[dict],
        evidence_lines: list[str],
        title: str,
        target_person_id: str | None = None,
        target_person_name: str | None = None,
        preselect_all: bool = False,
    ) -> None:
        self._insp_run_id = run_id
        self._insp_media_id = media_id
        self._insp_available = list(available)
        if target_person_id is not None:
            self._insp_target_person_id = target_person_id
            self._insp_target_person_name = target_person_name
        if hasattr(self, "_sel_heading"):
            self._sel_heading.set(title if available else title)
        self._sel_list.delete(0, tk.END)
        for it in self._insp_available:
            self._sel_list.insert(tk.END, _format_sel_item(it))
        if preselect_all and self._insp_available:
            self._sel_list.selection_set(0, tk.END)
        elif len(self._insp_available) == 1:
            self._sel_list.selection_set(0)
        self._on_inspector_sel_change()
        self._set_inspector(title, evidence_lines)
        if hasattr(self, "_sel_heading"):
            self._sel_heading.set(title)

    def _on_inspector_sel_change(self) -> None:
        idxs = list(self._sel_list.curselection())
        self._insp_selected = [
            self._insp_available[i] for i in idxs if 0 <= i < len(self._insp_available)
        ]
        self._refresh_inspector_verbs()

    def _refresh_inspector_verbs(self) -> None:
        from semblon.inspector_verbs import inspector_verb_states

        self._verb_states = inspector_verb_states(
            self._insp_selected,
            run_id=self._insp_run_id or self._last_run_id,
            target_person_id=self._insp_target_person_id,
        )
        buttons = {
            "merge": self.btn_merge,
            "assign": self.btn_assign,
            "split": self.btn_split,
            "rule_out": self.btn_rule_out,
            "ignore": self.btn_ignore,
        }
        reasons: list[str] = []
        for key, btn in buttons.items():
            st = self._verb_states.get(key) or {}
            enabled = bool(st.get("enabled"))
            btn.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            if not enabled and st.get("reason"):
                reasons.append(f"{btn.cget('text')}: {st['reason']}")
        name_st = self._verb_states.get("name") or {}
        name_on = bool(name_st.get("enabled"))
        self._name_entry.configure(state=tk.NORMAL if name_on else tk.DISABLED)
        if not name_on:
            self._name_var.set("")
            if name_st.get("reason"):
                reasons.append(f"Name: {name_st['reason']}")
        self._verb_reason.set(" · ".join(reasons[:3]) if reasons else "")

    def _inspector_run_id(self) -> str | None:
        return self._insp_run_id or self._last_run_id

    def _inspector_after_mutation(self) -> None:
        """Refresh Canvas / Unknown after a successful Inspector verb."""
        rid = self._inspector_run_id()
        if self._nav in {"home", "canvas", "photos", "videos"}:
            types = None
            if self._nav == "photos":
                types = ("folder",)
            elif self._nav == "videos":
                types = ("video",)
            self._show_workspace_canvas(reload=True, source_types=types)
        elif self._nav == "unknown":
            self._show_unknown()
        elif self._nav == "people":
            self._show_people()
        else:
            self._refresh_inspector_verbs()
        if rid:
            self._last_run_id = rid

    def _inspector_merge(self) -> None:
        from semblon.inspector_verbs import apply_inspector_merge
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError

        st = self._verb_states.get("merge") or {}
        if not st.get("enabled"):
            messagebox.showinfo("Semblon", st.get("reason") or "Merge unavailable")
            return
        rid = self._inspector_run_id()
        if not rid:
            return
        try:
            apply_inspector_merge(self.store, rid, list(st.get("cluster_ids") or []))
        except (ReviewError, ReviewUiError) as e:
            messagebox.showerror("Semblon", str(e))
            return
        self.status.set("Combined face groups.")
        self._inspector_after_mutation()

    def _inspector_assign(self) -> None:
        from semblon.inspector_verbs import apply_inspector_assign
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError

        st = self._verb_states.get("assign") or {}
        if not st.get("enabled"):
            messagebox.showinfo("Semblon", st.get("reason") or "Assign unavailable")
            return
        rid = self._inspector_run_id()
        item = st.get("item")
        pid = st.get("person_id") or self._insp_target_person_id
        if not rid or item is None or not pid:
            return
        display = self._insp_target_person_name or pid
        try:
            apply_inspector_assign(
                self.store, rid, item, person_id=pid, display_name=display
            )
        except (ReviewError, ReviewUiError) as e:
            messagebox.showerror("Semblon", str(e))
            return
        self.status.set(f"Added to {display!r}.")
        self._inspector_after_mutation()

    def _inspector_split(self) -> None:
        from semblon.inspector_verbs import apply_inspector_split
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError

        st = self._verb_states.get("split") or {}
        if not st.get("enabled"):
            messagebox.showinfo("Semblon", st.get("reason") or "Split unavailable")
            return
        rid = self._inspector_run_id()
        cid = st.get("cluster_id")
        face_ids = list(st.get("face_ids") or [])
        if not rid or not cid:
            return
        if not face_ids:
            messagebox.showinfo(
                "Semblon",
                "Select faces within the cluster to split (Ctrl+click in Selection).",
            )
            return
        try:
            apply_inspector_split(self.store, rid, cid, face_ids)
        except (ReviewError, ReviewUiError) as e:
            messagebox.showerror("Semblon", str(e))
            return
        self.status.set("Split faces into a new group.")
        self._inspector_after_mutation()

    def _inspector_name_commit(self) -> None:
        from semblon.inspector_verbs import apply_inspector_name
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError

        st = self._verb_states.get("name") or {}
        if not st.get("enabled"):
            return
        rid = self._inspector_run_id()
        item = st.get("item")
        name = (self._name_var.get() or "").strip()
        if not rid or item is None or not name:
            return
        try:
            apply_inspector_name(self.store, rid, item, name)
        except (ReviewError, ReviewUiError) as e:
            messagebox.showerror("Semblon", str(e))
            return
        self._name_var.set("")
        self.status.set(f"Named {name!r}.")
        self._inspector_after_mutation()

    def _inspector_name_cancel(self) -> None:
        self._name_var.set("")
        self._name_entry.selection_clear()
        self.root.focus_set()

    def _inspector_ignore(self) -> None:
        from semblon.inspector_verbs import apply_inspector_ignore
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError

        st = self._verb_states.get("ignore") or {}
        item = st.get("item")
        rid = self._inspector_run_id()
        if not rid or item is None:
            messagebox.showinfo("Semblon", "Select a cluster or face to Ignore.")
            return
        if not messagebox.askyesno(
            "Ignore",
            "Mark as ignore / not a person? Writes a decision (deferral).",
            parent=self.root,
        ):
            return
        try:
            apply_inspector_ignore(self.store, rid, item)
        except (ReviewError, ReviewUiError) as e:
            messagebox.showerror("Semblon", str(e))
            return
        self.status.set("Ignored.")
        self._inspector_after_mutation()

    def _inspector_rule_out(self) -> None:
        from semblon.inspector_verbs import apply_inspector_rule_out
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError

        st = self._verb_states.get("rule_out") or {}
        if not st.get("enabled"):
            messagebox.showinfo("Semblon", st.get("reason") or "Rule out unavailable")
            return
        rid = self._inspector_run_id()
        item = st.get("item")
        if not rid or item is None:
            return
        if not messagebox.askyesno(
            "Rule out",
            "Record durable Ruled out? This is not Ignore.",
            parent=self.root,
        ):
            return
        try:
            apply_inspector_rule_out(self.store, rid, item)
        except (ReviewError, ReviewUiError) as e:
            messagebox.showerror("Semblon", str(e))
            return
        self.status.set("Marked as not this person.")
        self._inspector_after_mutation()

    def _on_canvas_select(
        self,
        media_id: str | None,
        lines: list[str],
        selected_hit: dict | None = None,
    ) -> None:
        # Guard init race: Canvas may fire on_select during construction / early reload
        # before Inspector widgets and _canvas_ws assignment are ready.
        if not hasattr(self, "_sel_list") or not hasattr(self, "_inspector"):
            return
        ws = getattr(self, "_canvas_ws", None)
        board = (getattr(ws, "board", None) or {}) if ws is not None else {}
        run_id = board.get("run_id") or self._last_run_id
        if selected_hit is None and ws is not None:
            selected_hit = getattr(ws, "_selected", None)

        # Soft title from interaction, not "Selection" ontology.
        if selected_hit and selected_hit.get("kind") == "face":
            title = selected_hit.get("label") or "Unknown person"
            face = selected_hit.get("face") or {}
            available = [
                {
                    "kind": "face",
                    "face_id": selected_hit.get("id") or face.get("face_id"),
                    "cluster_id": face.get("cluster_id"),
                    "person_id": face.get("person_id"),
                    "display_name": title if face.get("person_id") else None,
                }
            ]
            preselect = True
            self._set_inspector_collapsed(False)
        elif selected_hit and selected_hit.get("kind") == "region":
            title = "Looking here"
            available = []
            preselect = False
            self._set_inspector_collapsed(False)
        elif selected_hit and selected_hit.get("kind") != "face":
            title = selected_hit.get("label") or "Something in the photo"
            available = []
            preselect = False
            self._set_inspector_collapsed(False)
        elif media_id:
            title = "This photo"
            available = []
            preselect = False
            # Photo open, nothing selected — keep inspector but soft.
            self._set_inspector_collapsed(False)
        else:
            title = "Photos"
            available = []
            preselect = False

        # Soft product lines from Canvas — do not re-wrap with engineering evidence.
        self._set_inspector_selection(
            run_id=run_id,
            media_id=media_id,
            available=available,
            evidence_lines=list(lines),
            title=title,
            preselect_all=preselect,
        )

    def _build_home_landing(self) -> None:
        """Dashboard hero. The sentence is the title. No second wordmark."""
        for child in self._landing.winfo_children():
            child.destroy()
        hero = tk.Frame(self._landing, bg=BG_CANVAS)
        hero.pack(anchor=tk.NW, padx=SP_24, pady=SP_24)
        tk.Label(
            hero,
            text="Find the people in your photos",
            font=DISPLAY,
            bg=BG_CANVAS,
            fg=TEXT_PRIMARY,
            wraplength=560,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor=tk.W)
        tk.Label(
            hero,
            text=(
                "Semblon looks through your photo folder, finds faces, "
                "groups the ones that belong together, and lets you "
                "decide who those people are."
            ),
            font=BODY,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            wraplength=560,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor=tk.W, pady=(SP_12, 0))
        actions = tk.Frame(hero, bg=BG_CANVAS)
        self._landing_actions = actions
        actions.pack(anchor=tk.W, pady=(SP_24, 0))
        self.btn_landing_cta = _button(
            actions,
            "Add a photo folder",
            self._choose_folder,
            kind="primary",
            icon="folder-plus",
            plate=BG_CANVAS,
        )
        self.btn_landing_review = _button(
            actions,
            "Review suggestions",
            lambda: self._navigate("unknown"),
            kind="secondary",
            plate=BG_CANVAS,
        )
        self.btn_landing_browse = _button(
            actions,
            "Browse photos",
            lambda: self._navigate("photos"),
            kind="secondary",
            plate=BG_CANVAS,
        )
        # Pack order and kinds are applied in _refresh_landing_hint.

        steps = tk.Frame(hero, bg=BG_CANVAS)
        self._landing_steps = steps
        steps.pack(anchor=tk.W, pady=(SP_24, 0))
        ui_strong = (DISPLAY[0], 14, "bold")
        self._landing_step_cards: list[dict] = []
        for _ in range(3):
            card = tk.Frame(
                steps,
                bg=BG_CANVAS,
                highlightbackground=BORDER_SUBTLE,
                highlightthickness=1,
                padx=SP_16,
                pady=SP_16,
            )
            card.pack(side=tk.LEFT, anchor=tk.N, padx=(0, SP_12))
            marker = tk.Label(
                card,
                text="",
                font=H2,
                bg=BG_CANVAS,
                fg=TEXT_DISABLED,
                anchor="w",
            )
            marker.pack(anchor=tk.W)
            title_lbl = tk.Label(
                card,
                text="",
                font=ui_strong,
                bg=BG_CANVAS,
                fg=TEXT_PRIMARY,
                wraplength=180,
                anchor="w",
                justify=tk.LEFT,
            )
            title_lbl.pack(anchor=tk.W, pady=(SP_8, 0))
            desc_lbl = tk.Label(
                card,
                text="",
                font=H3,
                bg=BG_CANVAS,
                fg=TEXT_SECONDARY,
                wraplength=180,
                anchor="nw",
                justify=tk.LEFT,
            )
            desc_lbl.pack(anchor=tk.W, pady=(SP_8, 0))
            self._landing_step_cards.append(
                {
                    "card": card,
                    "marker": marker,
                    "title": title_lbl,
                    "desc": desc_lbl,
                }
            )

        privacy = tk.Frame(hero, bg=BG_CANVAS)
        self._landing_privacy = privacy
        privacy.pack(anchor=tk.W, pady=(SP_24, 0))
        if draw_icon is not None:
            icon_px = 18
            mark = tk.Canvas(
                privacy,
                width=icon_px,
                height=icon_px,
                bg=BG_CANVAS,
                highlightthickness=0,
            )
            mark.pack(side=tk.LEFT, padx=(0, SP_8))
            draw_icon(mark, "shield", 0, 0, icon_px, SUCCESS)
        tk.Label(
            privacy,
            text="Everything stays on this computer. Nothing is uploaded.",
            font=META,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            wraplength=560,
            justify=tk.LEFT,
            anchor="w",
        ).pack(side=tk.LEFT)
        self._refresh_landing_hint()

    def _build_processing_home(self) -> None:
        """PROCESSING state — results framing while a job runs (not marketing + telemetry)."""
        for child in self._processing.winfo_children():
            child.destroy()
        from semblon.product_surface import (
            processing_home_activity,
            processing_home_headline,
        )

        shell = ttk.Frame(self._processing, padding=(SP_32, SP_32))
        shell.pack(expand=True, fill=tk.BOTH)
        self._proc_headline = tk.StringVar(value=processing_home_headline())
        self._proc_activity = tk.StringVar(value=processing_home_activity())
        self._proc_progress = tk.StringVar(value="")
        self._proc_faces = tk.StringVar(value="")
        self._proc_eta = tk.StringVar(value="")
        self._proc_folder_note = tk.StringVar(
            value=(
                "Semblon is analysing your library. You can add another folder "
                "when this finishes."
            )
        )
        ttk.Label(
            shell,
            textvariable=self._proc_headline,
            font=H1,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        ttk.Label(
            shell,
            textvariable=self._proc_activity,
            font=BODY,
            foreground=TEXT_SECONDARY,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        ttk.Label(
            shell,
            textvariable=self._proc_progress,
            font=MONO,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_24, 0))
        ttk.Label(
            shell,
            textvariable=self._proc_faces,
            font=BODY,
            foreground=TEXT_SECONDARY,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        ttk.Label(
            shell,
            textvariable=self._proc_eta,
            font=MONO,
            foreground=INK_TERTIARY,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_8, SP_16))

        self._proc_bar = StillProgressBar(shell, width=560, height=16)
        self._proc_bar.pack(anchor=tk.W, fill=tk.X, pady=(0, SP_16))

        controls = ttk.Frame(shell)
        controls.pack(anchor=tk.W, pady=(0, SP_16))
        self.btn_proc_pause = _button(
            controls,
            "Pause",
            self._toggle_pause_resume,
            kind="secondary",
            icon="pause",
            plate=BG_CANVAS,
        )
        self.btn_proc_pause.pack(side=tk.LEFT, padx=(0, SP_8))
        self.btn_proc_cancel = _button(
            controls,
            "Cancel",
            self._request_cancel,
            kind="tertiary",
            plate=BG_CANVAS,
        )
        self.btn_proc_cancel.pack(side=tk.LEFT)

        discovered = ttk.Frame(shell)
        discovered.pack(anchor=tk.W, fill=tk.X, pady=(SP_16, 0))
        ttk.Label(
            discovered,
            text="Already discovered",
            font=H3,
        ).pack(anchor=tk.W)
        self._proc_discovered = tk.StringVar(value="")
        ttk.Label(
            discovered,
            textvariable=self._proc_discovered,
            font=BODY,
            foreground=TEXT_SECONDARY,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        # Optional live face strip — real faces only; filled when store has rows.
        self._proc_thumbs = ttk.Frame(discovered)
        self._proc_thumbs.pack(anchor=tk.W, pady=(SP_12, 0))
        self._proc_thumb_images: list = []

        ttk.Label(
            shell,
            textvariable=self._proc_folder_note,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_24, 0))
        ttk.Label(
            shell,
            text="Everything stays on this computer. Nothing is uploaded.",
            font=CAPTION,
            foreground=TEXT_DISABLED,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_8, 0))

    def _build_result_card_shell(self) -> None:
        """Result summary card shell (UX Rescue §11); content filled on completion."""
        for child in self._result_card.winfo_children():
            child.destroy()
        outer = tk.Frame(
            self._result_card,
            bg=BG_SURFACE,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            padx=SP_32,
            pady=SP_32,
        )
        outer.pack(expand=True, pady=SP_32)
        self._result_headline = tk.StringVar(value="Your photos are ready")
        self._result_body = tk.StringVar(value="")
        ttk.Label(
            outer, textvariable=self._result_headline, font=H1, style="Surface.TLabel"
        ).pack(anchor=tk.W)
        ttk.Label(
            outer,
            textvariable=self._result_body,
            font=BODY,
            style="SurfaceMuted.TLabel",
            wraplength=432,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(SP_12, SP_16))
        self._result_stats = ttk.Frame(outer, style="Surface.TFrame")
        self._result_stats.pack(anchor=tk.W, pady=(0, SP_24))
        btns = ttk.Frame(outer, style="Surface.TFrame")
        btns.pack(anchor=tk.W)
        self.btn_result_primary = _button(
            btns, "Review people", self._open_review_ui, kind="primary", plate=BG_SURFACE
        )
        self.btn_result_primary.pack(side=tk.LEFT, padx=(0, SP_8))
        self.btn_result_secondary = _button(
            btns, "Add another folder", self._choose_folder, kind="secondary", plate=BG_SURFACE
        )
        self.btn_result_secondary.pack(side=tk.LEFT)
        self.btn_result_continue = _button(
            btns, "Continue", self._resume, kind="primary", plate=BG_SURFACE
        )
        self.btn_result_start_over = _button(
            btns, "Start over", self._choose_folder, kind="secondary", plate=BG_SURFACE
        )

    def _hide_workspace_panes(self) -> None:
        self._canvas_ws.pack_forget()
        self._welcome.pack_forget()
        self._landing.pack_forget()
        self._processing.pack_forget()
        self._result_card.pack_forget()

    def _home_state(self) -> str:
        """FIRST_RUN | PROCESSING | READY | EXPLORE — Home hierarchy gate."""
        busy = bool(getattr(self, "engine", None) and self.engine.busy)
        if busy:
            return "PROCESSING"
        if self._completion_kind in {"done", "cancelled"} and self._completion is not None:
            return "READY"
        if self.store.is_file():
            return "EXPLORE"
        return "FIRST_RUN"

    def _show_home_landing(self) -> None:
        """Home route: processing workspace, result card, or marketing landing."""
        self._hide_workspace_panes()
        state = self._home_state()
        if state == "PROCESSING":
            self._refresh_processing_home()
            self._processing.pack(fill=tk.BOTH, expand=True)
            self._set_inspector_collapsed(True)
            self._set_inspector(
                "Home",
                [
                    "Semblon is analysing your photo library.",
                    "Pause stops between files. Cancel stops this job.",
                    "Results appear here when the job finishes.",
                ],
            )
            return
        if state == "READY":
            self._fill_result_card()
            self._result_card.pack(fill=tk.BOTH, expand=True)
        else:
            self._refresh_landing_hint()
            self._landing.pack(fill=tk.BOTH, expand=True)
        self._set_inspector_collapsed(True)
        self._set_inspector("Home", list(INSPECTOR_HOME_EMPTY))

    def _refresh_processing_home(self, ev: ProgressEvent | None = None) -> None:
        """Push soft processing copy into the PROCESSING workspace."""
        from semblon.product_surface import processing_home_snapshot

        paused = bool(getattr(self, "engine", None) and self.engine.paused)
        pace = getattr(self, "_scan_pace", None)
        snap = processing_home_snapshot(ev, paused=paused, pace=pace)
        if hasattr(self, "_proc_headline"):
            self._proc_headline.set(snap["headline"])
            self._proc_activity.set(snap["activity"])
            self._proc_progress.set(snap["progress"])
            self._proc_faces.set(snap["faces"])
            self._proc_eta.set(snap["eta"])
            self._proc_folder_note.set(snap["folder_note"])
            faces_line = snap["faces"]
            if faces_line:
                self._proc_discovered.set(faces_line)
            else:
                self._proc_discovered.set("Faces will appear here as Semblon finds them.")
            if ev is not None and hasattr(self, "_proc_bar"):
                self._proc_bar.set_from_event(ev)
            if hasattr(self, "btn_proc_pause"):
                if paused:
                    self.btn_proc_pause.configure(text="Resume", state=tk.NORMAL)
                else:
                    self.btn_proc_pause.configure(text="Pause", state=tk.NORMAL)
            if hasattr(self, "btn_proc_cancel"):
                self.btn_proc_cancel.configure(state=tk.NORMAL)
            # Cheap live discovery count; thumbs refresh when face count jumps.
            if faces_line:
                faces_n = getattr(ev, "faces_found", None) if ev is not None else None
                if faces_n is None:
                    faces_n = self._last_faces_found
                if faces_n != self._proc_thumbs_faces:
                    self._proc_thumbs_faces = int(faces_n) if faces_n is not None else None
                    self._refresh_processing_thumbs()
            elif not getattr(self, "_proc_thumb_images", None):
                self._refresh_processing_thumbs()

    def _refresh_processing_thumbs(self) -> None:
        """Optional real face strip from the store — skip silently when unavailable."""
        frame = getattr(self, "_proc_thumbs", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        self._proc_thumb_images = []
        store = getattr(self, "store", None)
        if store is None or not Path(store).is_file():
            return
        try:
            rows = _recent_face_paths(Path(store), limit=8)
        except Exception:  # noqa: BLE001 — discovery strip is best-effort
            return
        if not rows:
            return
        try:
            from semblon.review_ui import crop_png_b64
        except Exception:  # noqa: BLE001
            return

        for media_path, bbox in rows:
            try:
                b64 = crop_png_b64(
                    media_path,
                    bbox,
                    max_side=56,
                    frame_id=None,
                )
            except Exception:  # noqa: BLE001
                continue
            if not b64:
                continue
            try:
                img = tk.PhotoImage(data=b64)
            except Exception:  # noqa: BLE001
                continue
            self._proc_thumb_images.append(img)
            lbl = tk.Label(frame, image=img, bg=BG_CANVAS)
            lbl.pack(side=tk.LEFT, padx=(0, SP_8))
            if len(self._proc_thumb_images) >= 8:
                break

    def _refresh_landing_hint(self) -> None:
        """First-run vs returning-user landing from real library counts."""
        summary = self._library_summary()
        files = 0 if summary is None else int(summary.get("files") or 0)
        waiting = 0 if summary is None else int(summary.get("unnamed_groups") or 0)
        plan = landing_cta_plan(files=files, unnamed=waiting)

        add_btn = getattr(self, "btn_landing_cta", None)
        review = getattr(self, "btn_landing_review", None)
        browse = getattr(self, "btn_landing_browse", None)
        for btn in (add_btn, review, browse):
            if btn is not None:
                btn.pack_forget()

        if add_btn is not None:
            add_btn.configure(text=plan["add_label"])
            if hasattr(add_btn, "set_kind"):
                add_btn.set_kind(
                    "primary" if plan["primary"] == "add" else "secondary"
                )
        if review is not None:
            review.configure(text=plan["review_label"])
            if hasattr(review, "set_kind"):
                review.set_kind(
                    "primary" if plan["primary"] == "review" else "secondary"
                )
        if browse is not None and hasattr(browse, "set_kind"):
            browse.set_kind(
                "primary" if plan["primary"] == "browse" else "secondary"
            )

        # Pack primary first, then secondary actions.
        order: list[tuple[object | None, bool]] = []
        if plan["primary"] == "review":
            order = [
                (review, plan["show_review"]),
                (add_btn, True),
                (browse, plan["show_browse"]),
            ]
        elif plan["primary"] == "browse":
            order = [
                (browse, plan["show_browse"]),
                (add_btn, True),
                (review, plan["show_review"]),
            ]
        else:
            order = [
                (add_btn, True),
                (review, plan["show_review"]),
                (browse, plan["show_browse"]),
            ]
        first = True
        for btn, show in order:
            if btn is None or not show:
                continue
            btn.pack(side=tk.LEFT, padx=(0 if first else SP_12, 0))
            first = False

        privacy = getattr(self, "_landing_privacy", None)
        if privacy is not None:
            privacy.pack_forget()
            if plan["show_privacy"]:
                privacy.pack(anchor=tk.W, pady=(SP_24, 0))

        steps = landing_step_states(files=files, unnamed=waiting)
        cards = getattr(self, "_landing_step_cards", None) or []
        for card, step in zip(cards, steps):
            marker = card["marker"]
            marker.configure(text=step["marker"])
            phase = step["phase"]
            if phase == "done":
                marker.configure(fg=SUCCESS)
            elif phase == "current":
                marker.configure(fg=TEXT_PRIMARY)
            else:
                marker.configure(fg=TEXT_DISABLED)
            card["title"].configure(text=step["title"])
            card["desc"].configure(text=step["desc"])
            try:
                thickness = 2 if phase == "current" else 1
                card["card"].configure(highlightthickness=thickness)
            except tk.TclError:
                pass

    def _library_summary(self) -> dict | None:
        from semblon.library_status import library_summary

        try:
            return library_summary(self.store)
        except (OSError, sqlite3.DatabaseError):
            return None

    def _refresh_library_chrome(self) -> None:
        """Status bar and To review badge from the library. Hidden badge at 0."""
        from semblon.library_status import status_bar_text

        summary = self._library_summary()
        if hasattr(self, "_library_status"):
            self._library_status.set(status_bar_text(summary))
        btn = getattr(self, "_nav_buttons", {}).get("unknown")
        waiting = 0 if summary is None else int(summary.get("unnamed_groups") or 0)
        if btn is not None and hasattr(btn, "set_badge"):
            btn.set_badge(waiting)
        self._refresh_search_placeholder(summary)

    def _refresh_search_placeholder(self, summary: dict | None = None) -> None:
        """Placeholder reflects whether any people have been named yet."""
        if summary is None:
            summary = self._library_summary()
        named = 0 if summary is None else int(summary.get("named_people") or 0)
        new_ph = search_placeholder(has_named_people=named > 0)
        old_ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
        current = (self.search_var.get() or "").strip()
        self._search_placeholder = new_ph
        if current in {"", old_ph, SEARCH_PLACEHOLDER, new_ph}:
            self.search_var.set(new_ph)
            try:
                self._search_entry.configure(foreground=INK_TERTIARY)
            except tk.TclError:
                pass

    def _search_focus_in(self, _event=None) -> None:
        ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
        if self.search_var.get() == ph:
            self.search_var.set("")
            try:
                self._search_entry.configure(foreground=TEXT_PRIMARY)
            except tk.TclError:
                pass

    def _search_focus_out(self, _event=None) -> None:
        if not (self.search_var.get() or "").strip():
            ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
            self.search_var.set(ph)
            try:
                self._search_entry.configure(foreground=INK_TERTIARY)
            except tk.TclError:
                pass

    def _apply_saved_theme(self) -> None:
        """Publish the saved appearance before widgets are built."""
        from semblon.ui_prefs import load_theme_mode, resolve_palette
        from semblon.ui_tokens import publish

        publish(resolve_palette(load_theme_mode(self.store)))

    def _set_theme_mode(self, mode: str) -> None:
        from semblon.ui_prefs import resolve_palette, save_theme_mode
        from semblon.ui_theme import apply_theme, reset_theme_for_tests
        from semblon.ui_tokens import publish

        kept = save_theme_mode(mode, self.store)
        publish(resolve_palette(kept))
        if apply_theme is not None:
            reset_theme_for_tests()
            apply_theme(self.root, force=True)
            if self._settings_win is not None:
                try:
                    if self._settings_win.winfo_exists():
                        apply_theme(self._settings_win, force=True)
                except tk.TclError:
                    pass
        self._restyle_chrome()

    def _restyle_chrome(self) -> None:
        """Repaint surfaces that captured colors when they were created."""
        try:
            self.root.configure(bg=BG_CANVAS)
        except tk.TclError:
            pass
        side = getattr(self, "_sidebar", None)
        if side is not None:
            try:
                side.configure(
                    bg=BG_SUBTLE,
                    highlightbackground=BORDER_SUBTLE,
                    highlightcolor=BORDER_SUBTLE,
                )
            except tk.TclError:
                pass
            for child in side.winfo_children():
                if isinstance(child, tk.Label):
                    try:
                        fg = TEXT_PRIMARY if child is getattr(self, "_sidebar_brand", None) else INK_TERTIARY
                        child.configure(bg=BG_SUBTLE, fg=fg)
                    except tk.TclError:
                        pass
                elif hasattr(child, "_kind"):
                    child._plate = BG_SUBTLE
                    try:
                        child.configure(bg=BG_SUBTLE)
                    except tk.TclError:
                        pass
                    if hasattr(child, "_redraw"):
                        child._redraw()
        footer = getattr(self, "_sidebar_footer", None)
        if footer is not None:
            try:
                footer.configure(bg=BG_SUBTLE, fg=INK_TERTIARY)
            except tk.TclError:
                pass
        self._build_home_landing()
        self._build_processing_home()
        self._build_result_card_shell()
        self._navigate(self._nav)
        self._refresh_job_controls()

    def _open_command_palette(self, _event=None):
        """Jump to a real destination. Not a second navigation model."""
        if tk is None:
            return "break"
        win = tk.Toplevel(self.root)
        win.title("Semblon")
        win.transient(self.root)
        win.geometry("360x280")
        if apply_theme is not None:
            apply_theme(win)
        try:
            win.configure(bg=BG_CANVAS)
        except tk.TclError:
            pass
        ttk.Label(win, text="Go to", font=H3).pack(anchor=tk.W, padx=SP_16, pady=(SP_16, SP_8))
        box = tk.Listbox(win, exportselection=False, activestyle="none")
        if style_listbox is not None:
            style_listbox(box)
        commands: list[tuple[str, str]] = []
        for _section, items in HOME_NAV:
            for nav_id, label in items:
                commands.append((label, nav_id))
        commands.append(("Settings", "settings"))
        for label, _nav in commands:
            box.insert(tk.END, label)
        box.pack(fill=tk.BOTH, expand=True, padx=SP_16, pady=(0, SP_16))

        def _go(_e=None) -> None:
            sel = box.curselection()
            if not sel:
                return
            _label, nav_id = commands[sel[0]]
            win.destroy()
            if nav_id == "settings":
                self._show_settings()
            else:
                self._navigate(nav_id)

        box.bind("<Return>", _go)
        box.bind("<Double-Button-1>", _go)
        box.bind("<Escape>", lambda _e: win.destroy())
        if commands:
            box.selection_set(0)
            box.focus_set()
        return "break"

    def _fill_result_card(self) -> None:
        kind = self._completion_kind
        data = self._completion or {}
        # Reset button packing
        for b in (
            self.btn_result_primary,
            self.btn_result_secondary,
            self.btn_result_continue,
            self.btn_result_start_over,
        ):
            b.pack_forget()
        self._fill_result_stats(data if kind == "done" else None)
        if kind == "cancelled":
            self._result_headline.set("Processing stopped")
            done = data.get("files_processed")
            total = data.get("files_total")
            if done is not None and total is not None:
                body = (
                    f"Semblon checked {done} of {total} photos before you cancelled."
                )
            elif done is not None:
                body = f"Semblon checked {done} photos before you cancelled."
            else:
                body = "Processing stopped before Semblon finished this folder."
            self._result_body.set(body)
            self.btn_result_continue.pack(side=tk.LEFT, padx=(0, SP_8), ipady=4, ipadx=8)
            self.btn_result_start_over.pack(side=tk.LEFT, ipady=2, ipadx=6)
            return
        # done
        photos = int(data.get("photos") or 0)
        faces = int(data.get("faces") or 0)
        groups = int(data.get("groups") or 0)
        self._result_headline.set("Your photos are ready")
        if faces <= 0:
            self._result_body.set(
                f"Semblon checked {photos} photos but didn't find any faces to group."
                if photos
                else "Semblon finished this folder but didn't find any faces to group."
            )
            self.btn_result_secondary.pack(side=tk.LEFT, ipady=4, ipadx=8)
        else:
            self._result_body.set(
                f"Semblon checked {photos} photos and found {faces} faces "
                f"across {groups} groups."
                if photos
                else f"Semblon found {faces} faces across {groups} groups."
            )
            self.btn_result_primary.pack(side=tk.LEFT, padx=(0, SP_8), ipady=4, ipadx=8)
            self.btn_result_secondary.pack(side=tk.LEFT, ipady=2, ipadx=6)

    def _fill_result_stats(self, data: dict | None) -> None:
        """Three quiet counts under the summary. Hidden when there is nothing to count."""
        frame = getattr(self, "_result_stats", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        if not data:
            return
        tiles = (
            ("Photos", data.get("photos")),
            ("Faces", data.get("faces")),
            ("Groups", data.get("groups")),
        )
        for label, value in tiles:
            if value is None:
                continue
            cell = ttk.Frame(frame, style="Surface.TFrame", padding=(0, 0, SP_24, 0))
            cell.pack(side=tk.LEFT)
            ttk.Label(cell, text=str(value), font=H2, style="Surface.TLabel").pack(anchor=tk.W)
            ttk.Label(
                cell, text=label, font=CAPTION, style="SurfaceMuted.TLabel"
            ).pack(anchor=tk.W)

    @staticmethod
    def _counts_from_done_payload(payload: dict) -> dict[str, int]:
        ing = payload.get("ingest") if isinstance(payload.get("ingest"), dict) else {}
        clu = payload.get("cluster") if isinstance(payload.get("cluster"), dict) else {}
        photos = int(ing.get("files") or ing.get("new_media") or payload.get("files") or 0)
        faces = int(ing.get("faces") or payload.get("faces") or 0)
        groups = int(clu.get("clusters") or payload.get("clusters") or 0)
        return {"photos": photos, "faces": faces, "groups": groups}

    def _set_inspector_collapsed(self, collapsed: bool) -> None:
        """Collapse Inspector column on cold home; expand for other routes."""
        self._inspector_collapsed = collapsed
        if collapsed:
            self._inspector_frame.grid_remove()
            self._body.columnconfigure(1, weight=0, minsize=0)
            self._body.columnconfigure(0, weight=5)
        else:
            self._inspector_frame.grid()
            self._body.columnconfigure(1, weight=1)
            self._body.columnconfigure(0, weight=5)

    def _mark_nav_active(self, nav_id: str) -> None:
        """Best-effort active nav styling in ttk (underline / state)."""
        for nid, btn in self._nav_buttons.items():
            try:
                if nid == nav_id:
                    btn.state(["pressed"])
                else:
                    btn.state(["!pressed"])
            except tk.TclError:
                pass

    def _sync_chrome_for_route(self) -> None:
        """Demote job bar on home; restore contextual controls elsewhere (§3)."""
        # Clear job frame children packing
        for w in (
            self.btn_folder,
            self.btn_review,
            self.btn_html,
            self.btn_live,
            self.btn_canvas,
        ):
            try:
                w.pack_forget()
            except tk.TclError:
                pass
        busy = bool(getattr(self, "engine", None) and self.engine.busy)
        on_home = self._nav == "home"
        processing_home = on_home and busy
        if on_home:
            # Primary CTA lives on the landing. More stays in the top bar.
            # PROCESSING Home owns Pause/Cancel inside the workspace — hide telemetry strip.
            self._jobs_frame.pack_forget()
            if self._completion_kind == "done" and not busy:
                self._jobs_frame.pack(fill=tk.X, before=self._body)
                self.btn_review.pack(side=tk.LEFT, padx=(SP_8, 0))
        else:
            try:
                self._jobs_frame.pack(fill=tk.X, before=self._body)
            except tk.TclError:
                self._jobs_frame.pack(fill=tk.X)
            # Photos/Videos: folder only — Review/Canvas live under More (not primary chrome).
            self.btn_folder.pack(side=tk.LEFT)
            if self._nav not in {"photos", "videos"}:
                self.btn_review.pack(side=tk.LEFT, padx=(SP_8, 0))
                self.btn_canvas.pack(side=tk.LEFT, padx=(SP_8, 0))
            # else: browsing photos — no Review/Canvas escape hatch in the job bar.
        # Pause toggle + Cancel sit next to the progress bar when busy off-Home.
        # Idle home has no status strip. Processing Home replaces the strip entirely.
        if busy and not processing_home:
            try:
                self._prog_frame.pack(fill=tk.X, before=self._body)
            except tk.TclError:
                self._prog_frame.pack(fill=tk.X)
            self.bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.btn_pause_toggle.pack(side=tk.LEFT, padx=(SP_8, 0))
            self.btn_cancel_prog.pack(side=tk.LEFT, padx=(SP_8, 0))
        else:
            self.btn_pause_toggle.pack_forget()
            self.btn_cancel_prog.pack_forget()
            self.bar.pack_forget()
            if on_home or not busy:
                self._prog_frame.pack_forget()
            else:
                try:
                    self._prog_frame.pack(fill=tk.X, before=self._body)
                except tk.TclError:
                    self._prog_frame.pack(fill=tk.X)

    def _toggle_pause_resume(self) -> None:
        """Single Pause/Resume control adjacent to the progress bar."""
        if self.engine.paused:
            self._resume()
            return
        if self.engine.busy:
            self._request_pause()
            return
        # Idle resume-after-cancel
        self._resume()

    def _show_workspace_canvas(
        self,
        *,
        reload: bool = True,
        source_types: tuple[str, ...] | None = None,
    ) -> None:
        self._hide_workspace_panes()
        self._set_inspector_collapsed(False)
        self._canvas_ws.pack(fill=tk.BOTH, expand=True)
        if reload:
            try:
                self._canvas_ws.reload(
                    self.store, self._last_run_id, source_types=source_types
                )
            except Exception as e:  # noqa: BLE001 — surface in inspector
                self._set_inspector("Canvas", [f"Canvas unavailable: {e}"])

    def _show_workspace_welcome(self) -> None:
        self._hide_workspace_panes()
        self._set_inspector_collapsed(False)
        self._welcome.pack(fill=tk.BOTH, expand=True, anchor=tk.NW)

    def _navigate(self, nav_id: str) -> None:
        self._nav = nav_id
        self._mark_nav_active(nav_id)
        self._refresh_library_chrome()
        if nav_id == "home":
            self._show_home_landing()
            self._sync_chrome_for_route()
            self._refresh_job_controls()
            return
        if nav_id == "canvas":
            self._show_workspace_canvas(reload=True, source_types=None)
            self._set_inspector("Canvas", list(INSPECTOR_EMPTY))
            self._sync_chrome_for_route()
            self._refresh_job_controls()
            return
        if nav_id == "photos":
            # Stills are typically source_type=folder; exclude video assets.
            # Canvas reload emits soft inspector via on_select — do not dump library log rows.
            self._show_workspace_canvas(reload=True, source_types=("folder",))
            lib = format_library_lines(self.store, source_type="folder")
            if not library_has_media_lines(lib):
                self._set_inspector("Photos", photos_empty().as_lines())
            # else: leave soft canvas inspector (photo / tip) in place
            self._sync_chrome_for_route()
            self._refresh_job_controls()
            return
        if nav_id == "videos":
            self._show_workspace_canvas(reload=True, source_types=("video",))
            lib = format_library_lines(self.store, source_type="video")
            if not library_has_media_lines(lib):
                self._set_inspector("Videos", videos_empty().as_lines())
            self._sync_chrome_for_route()
            self._refresh_job_controls()
            return
        if nav_id == "people":
            self._welcome_title.set("People")
            self._show_workspace_welcome()
            self._show_people()
            self._sync_chrome_for_route()
            self._refresh_job_controls()
            return
        if nav_id == "unknown":
            self._welcome_title.set("To review")
            self._show_workspace_welcome()
            self._show_unknown()
            self._sync_chrome_for_route()
            self._refresh_job_controls()
            return
        if nav_id == "activity":
            self._welcome_title.set("Recent activity")
            self._show_workspace_welcome()
            self._show_activity()
            self._sync_chrome_for_route()
            self._refresh_job_controls()
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
        # Pause + Resume share one toggle widget adjacent to the progress bar.
        if busy:
            if self.engine.paused:
                self.btn_pause_toggle.configure(text="Resume", state=tk.NORMAL)
            else:
                self.btn_pause_toggle.configure(text="Pause", state=tk.NORMAL)
            self.btn_cancel.configure(state=tk.NORMAL)
        else:
            if self._resume_ready:
                self.btn_pause_toggle.configure(text="Resume", state=tk.NORMAL)
            else:
                self.btn_pause_toggle.configure(text="Pause", state=tk.DISABLED)
            self.btn_cancel.configure(state=tk.DISABLED)
        buttons = {
            "folder": self.btn_folder,
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
        # Landing CTA tracks folder availability; processing Home has no Add-folder CTA.
        if hasattr(self, "btn_landing_cta"):
            self.btn_landing_cta.configure(
                state=tk.NORMAL if states["folder"] == "normal" else tk.DISABLED
            )
        if hasattr(self, "btn_proc_pause"):
            if busy:
                if self.engine.paused:
                    self.btn_proc_pause.configure(text="Resume", state=tk.NORMAL)
                else:
                    self.btn_proc_pause.configure(text="Pause", state=tk.NORMAL)
            else:
                self.btn_proc_pause.configure(text="Pause", state=tk.DISABLED)
        if hasattr(self, "btn_proc_cancel"):
            self.btn_proc_cancel.configure(
                state=tk.NORMAL if busy else tk.DISABLED
            )
        self._sync_chrome_for_route()
        if self._nav == "home" and busy:
            try:
                mapped = bool(self._processing.winfo_ismapped())
            except tk.TclError:
                mapped = False
            if not mapped:
                self._show_home_landing()

    def _request_pause(self) -> None:
        if not self.engine.busy or self.engine.paused:
            return
        self.engine.pause()
        self.status.set("Paused")
        self._refresh_job_controls()
        self._refresh_processing_home(getattr(self, "_last_progress_event", None))

    def _request_cancel(self) -> None:
        if not self.engine.busy:
            return
        self.engine.cancel()
        self.status.set("Cancelling…")
        self._refresh_job_controls()

    def _effective_prefer_gpu(self) -> bool:
        if self._prefer_gpu_user is not None:
            return bool(self._prefer_gpu_user)
        return resolve_home_prefer_gpu()

    def _start_process(self, path: Path, *, resume: bool) -> None:
        self._last_folder = path
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._resume_ready = False
        self._completion = None
        self._completion_kind = None
        self._last_progress_files = (None, None)
        self._last_faces_found = None
        self._proc_thumbs_faces = None
        self._last_progress_event = None
        if getattr(self, "_scan_pace", None) is not None:
            self._scan_pace.reset()
        self.bar.reset()
        if hasattr(self, "_proc_bar"):
            self._proc_bar.reset()
        self.clock.set("")
        from semblon.product_surface import product_status_text, processing_home_snapshot

        queued = make_event(STAGE_PROCESS, KIND_QUEUED, path=str(path), outcome="resumed" if resume else None)
        self.status.set(product_status_text(queued))
        self._set_busy(True)
        if self._nav == "home":
            self._show_home_landing()
            snap = processing_home_snapshot(queued, paused=False)
            self._proc_headline.set(snap["headline"])
            self._proc_activity.set(snap["activity"])
            self._proc_eta.set(snap["eta"])
            self._proc_folder_note.set(snap["folder_note"])
        observers = resolve_home_observers()
        prefer_gpu = self._effective_prefer_gpu()

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
                    from semblon.product_surface import (
                        product_status_text,
                        soft_progress_counts,
                    )
                    from semblon.scan_present import scan_card

                    paused = bool(self.engine.paused)
                    self._last_progress_event = payload
                    if not paused and getattr(self, "_scan_pace", None) is not None:
                        self._scan_pace.observe(payload.files_processed, payload.elapsed_s)
                    self.status.set(product_status_text(payload, paused=paused))
                    self.bar.set_from_event(payload)
                    self._last_progress_files = (
                        payload.files_processed,
                        payload.files_total,
                    )
                    self._last_faces_found = payload.faces_found
                    # Counts stay available for the header. The clock is the
                    # scan meta line (percent / elapsed / ETA) and only when real.
                    counts = soft_progress_counts(
                        files_processed=payload.files_processed,
                        files_total=payload.files_total,
                    )
                    card = scan_card(
                        stage=payload.stage,
                        kind=payload.kind,
                        paused=paused,
                        files_processed=payload.files_processed,
                        files_total=payload.files_total,
                        faces_found=payload.faces_found,
                        elapsed_s=payload.elapsed_s,
                        pace=getattr(self, "_scan_pace", None),
                    )
                    self.clock.set(card["meta"] or counts)
                    if self._nav == "home":
                        self._refresh_processing_home(payload)
                elif kind == "done":
                    self._last_run_id = payload.get("run_id")
                    out = payload.get("out")
                    self._last_review_html = Path(out) if out else None
                    self._resume_ready = False
                    self._set_busy(False)
                    counts = self._counts_from_done_payload(
                        payload if isinstance(payload, dict) else {}
                    )
                    self._completion = counts
                    self._completion_kind = "done"
                    self._refresh_library_chrome()
                    # §10/§11 — status stays plain; card owns messaging (no run_id / elapsed).
                    photos = int(counts.get("photos") or 0)
                    if photos > 0:
                        self.status.set(
                            f"Your photos are ready. {photos} photo{'s' if photos != 1 else ''} added."
                        )
                    else:
                        self.status.set("Your photos are ready.")
                    self.clock.set("")
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
                    if self._nav == "home":
                        self._show_home_landing()
                        self._sync_chrome_for_route()
                    elif self._nav in {"canvas", "photos", "videos"}:
                        types = None
                        if self._nav == "photos":
                            types = ("folder",)
                        elif self._nav == "videos":
                            types = ("video",)
                        self._show_workspace_canvas(reload=True, source_types=types)
                elif kind == "cancelled":
                    self._resume_ready = self._last_folder is not None
                    self._set_busy(False)
                    done, total = self._last_progress_files
                    self._completion = {
                        "files_processed": done,
                        "files_total": total,
                        "run_id": payload or None,
                    }
                    self._completion_kind = "cancelled"
                    self._refresh_library_chrome()
                    self.status.set(
                        "Processing stopped. Any partial results have been retained."
                    )
                    self.clock.set("")
                    if self._nav == "home":
                        self._show_home_landing()
                        self._sync_chrome_for_route()
                    if self._exit_after_cancel and self.root.winfo_exists():
                        self.root.destroy()
                        return
                elif kind == "error":
                    self._resume_ready = self._last_folder is not None
                    self._set_busy(False)
                    self.clock.set("")
                    if isinstance(payload, BaseException):
                        if is_expected_condition(payload):
                            self.status.set("Processing stopped.")
                        else:
                            self._show_failure(payload)
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
                self.status.set("Paused")
                if self._nav == "home":
                    self._refresh_processing_home()
            stalled = self._wd.check()
            if stalled is not None and stalled.kind == KIND_STALLED and not self.engine.paused:
                from semblon.product_surface import product_status_text

                self.status.set(product_status_text(stalled))
            self._refresh_job_controls()
        if self.root.winfo_exists():
            self.root.after(100, self._drain_queue)

    def _show_failure(self, exc: BaseException) -> None:
        """§17 — friendly failure dialog; never title the dialog bare 'Error'."""
        dialog = failure_dialog_for(exc)
        self.status.set(dialog.headline)
        show_failure_dialog(self.root, exc, tk_mod=tk, ttk_mod=ttk)

    def _open_review_ui(self) -> None:
        from semblon.review_ui import ReviewUiError, run_review_ui

        try:
            # Toplevel on Home's root. Home keeps pumping events. No nested mainloop.
            run_review_ui(
                store=self.store,
                run_id=self._last_run_id,
                parent=self.root,
                on_add_folder=self._choose_folder,
            )
        except ReviewUiError as e:
            # Expected empty (no store / no runs) is handled inside run_review_ui.
            if is_expected_condition(e, has_store=self.store.is_file()):
                if not self.store.is_file():
                    self._set_inspector(
                        "To review", to_review_empty(has_store=False).as_lines()
                    )
                else:
                    self._set_inspector(
                        "To review",
                        to_review_empty(has_store=True, has_faces=False).as_lines(),
                    )
                return
            self._show_failure(e)

    def _open_html(self) -> None:
        path = self._last_review_html
        if path is None or not path.is_file():
            from semblon.process import default_review_out

            path = default_review_out(self.store)
        if not path.is_file():
            messagebox.showinfo(
                "Semblon", "No review page yet. Add a photo folder first."
            )
            return
        webbrowser.open(path.resolve().as_uri())

    def _list_window(self, title: str, lines: list[str]) -> None:
        """Legacy helper: route into Inspector (no floating list-only windows)."""
        self._set_inspector(title, lines)

    def _show_people(self) -> None:
        from semblon.inspector_verbs import evidence_lines_for_selection
        from semblon.search import SearchError, search_people

        if not self.store.is_file():
            self._set_inspector_selection(
                run_id=None,
                media_id=None,
                available=[],
                evidence_lines=people_empty().as_lines(),
                title="People",
            )
            return
        try:
            rec = search_people(self.store)
        except SearchError as e:
            if is_expected_condition(e):
                self._set_inspector("People", people_empty().as_lines())
            else:
                self._show_failure(e)
            return
        # People rows are assign targets, not Merge observations.
        people_items = []
        for i in rec.get("items") or []:
            people_items.append(
                {
                    "kind": "person",
                    "person_id": i.get("person_id"),
                    "display_name": i.get("display_name"),
                    "faces": i.get("faces"),
                }
            )
        if not people_items:
            self._set_inspector_selection(
                run_id=self._last_run_id,
                media_id=None,
                available=[],
                evidence_lines=people_empty().as_lines(),
                title="People",
            )
            return
        # Selecting a person sets Assign target; observations come from Unknown/Canvas.
        self._insp_available = []
        self._sel_list.delete(0, tk.END)
        for p in people_items:
            label = (
                f"person {p.get('display_name') or p.get('person_id')}  "
                f"({p.get('faces', 0)} photos)"
            )
            self._sel_list.insert(tk.END, label)
        self._people_items = people_items
        self._sel_list.bind("<<ListboxSelect>>", self._on_people_sel_change)
        evid = evidence_lines_for_selection(
            run_id=self._last_run_id,
            selected=[],
            board_lines=format_people_lines(rec),
            candidate_person=self._insp_target_person_name,
        )
        evid.insert(
            1,
            "Select a person here, then a face under To review or in Photos to add them.",
        )
        self._insp_run_id = self._last_run_id
        self._insp_selected = []
        self._set_inspector("People", evid)

    def _on_people_sel_change(self, _event=None) -> None:
        idxs = list(self._sel_list.curselection())
        people = getattr(self, "_people_items", None) or []
        if len(idxs) == 1 and 0 <= idxs[0] < len(people):
            p = people[idxs[0]]
            self._insp_target_person_id = p.get("person_id")
            self._insp_target_person_name = p.get("display_name") or p.get("person_id")
            self.status.set(
                f"Ready to add faces to {self._insp_target_person_name!r}."
            )
        self._refresh_inspector_verbs()

    def _show_unknown(self) -> None:
        from semblon.inbox import InboxError, inbox
        from semblon.inspector_verbs import evidence_lines_for_selection
        from semblon.process import latest_run_id
        from semblon.review_ui import load_board

        # Display label "To review"; route id remains ``unknown``.
        title = "To review"
        if not self.store.is_file():
            self._set_inspector_selection(
                run_id=None,
                media_id=None,
                available=[],
                evidence_lines=to_review_empty(has_store=False).as_lines(),
                title=title,
            )
            return
        rid = latest_run_id(self.store, with_faces=True)
        if rid is None:
            self._set_inspector_selection(
                run_id=None,
                media_id=None,
                available=[],
                evidence_lines=to_review_empty(
                    has_store=True, has_faces=False
                ).as_lines(),
                title=title,
            )
            return
        try:
            rec = inbox(self.store, rid)
        except InboxError as e:
            if is_expected_condition(e):
                self._set_inspector(
                    title,
                    to_review_empty(has_store=True, has_faces=False).as_lines(),
                )
            else:
                self._show_failure(e)
            return
        # Restore selection binding (People overrides it).
        self._sel_list.bind("<<ListboxSelect>>", lambda _e: self._on_inspector_sel_change())
        available: list[dict] = []
        try:
            from semblon.inspector_verbs import flatten_board_items_for_inspector

            board = load_board(self.store, rid)
            raw = []
            for it in board.get("items") or []:
                if it.get("kind") == "cluster" and not it.get("named"):
                    raw.append(it)
                elif it.get("kind") == "face":
                    raw.append(it)
            available = flatten_board_items_for_inspector(raw)
        except Exception:  # noqa: BLE001 — Unknown still shows inbox counts
            available = []
        evid = evidence_lines_for_selection(
            run_id=rid,
            selected=available,
            board_lines=format_unknown_lines(rec, rid),
            candidate_person=self._insp_target_person_name,
        )
        self._set_inspector_selection(
            run_id=rid,
            media_id=None,
            available=available,
            evidence_lines=evid,
            title=title,
            preselect_all=False,
        )

    def _activity_soft_stats(self, run_id: str) -> dict:
        """Plain-language counts for Recent activity rows (no integrity jargon)."""
        conn = sqlite3.connect(f"file:{self.store.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            photos = int(
                conn.execute(
                    "SELECT COUNT(*) FROM media "
                    "WHERE source_type != 'video' OR source_type IS NULL"
                ).fetchone()[0]
            )
            run_media = conn.execute(
                """
                SELECT COUNT(DISTINCT o.media_id) AS n
                FROM observations o
                WHERE o.run_id=?
                """,
                (run_id,),
            ).fetchone()
            if run_media and int(run_media["n"] or 0) > 0:
                photos = int(run_media["n"])
            faces = int(
                conn.execute(
                    "SELECT COUNT(*) FROM faces WHERE run_id=?", (run_id,)
                ).fetchone()[0]
            )
            groups = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM clusters
                    WHERE run_id=? AND (status IS NULL OR status != 'ignored')
                    """,
                    (run_id,),
                ).fetchone()[0]
            )
            unnamed = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM clusters c
                    WHERE c.run_id=?
                      AND NOT EXISTS (
                        SELECT 1 FROM faces f
                        WHERE f.cluster_id = c.cluster_id AND f.person_id IS NOT NULL
                      )
                    """,
                    (run_id,),
                ).fetchone()[0]
            )
            row = conn.execute(
                "SELECT finished_at, started_at FROM runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            stamped = None
            if row is not None:
                stamped = row["finished_at"] or row["started_at"]
                if stamped:
                    stamped = str(stamped)[:10]
        except sqlite3.OperationalError:
            return {
                "photos": None,
                "faces": None,
                "groups": None,
                "has_unnamed": False,
                "stamped": None,
            }
        finally:
            conn.close()
        return {
            "photos": photos,
            "faces": faces,
            "groups": groups,
            "has_unnamed": unnamed > 0,
            "stamped": stamped,
        }

    def _show_activity(self) -> None:
        from semblon.process import latest_run_id

        title = "Recent activity"
        if not self.store.is_file():
            self._set_inspector(title, activity_empty().as_lines())
            return
        rid = latest_run_id(self.store)
        if not rid:
            self._set_inspector(title, activity_empty().as_lines())
            return

        try:
            from semblon.application import activity

            rec = activity(self.store, rid)
        except (sqlite3.DatabaseError, OSError, ValueError) as e:
            if is_expected_condition(e):
                self._set_inspector(title, activity_empty().as_lines())
            else:
                self._show_failure(e)
            return

        stats = self._activity_soft_stats(rid)
        self._set_inspector(
            title,
            format_activity_lines(
                run_line="Recent run",
                integrity_line="",
                groups=rec.get("groups") or [],
                relationships=rec.get("relationships") or [],
                events=rec.get("events") or [],
                track_count=int(rec.get("track_count") or 0),
                photos=stats.get("photos"),
                faces=stats.get("faces"),
                stamped=stats.get("stamped"),
                has_unnamed=bool(stats.get("has_unnamed")),
                group_count=stats.get("groups"),
                advanced=False,
            ),
        )

    def _open_canvas(self) -> None:
        """First-class canvas is the Home workspace; keep Toplevel as escape hatch."""
        self._navigate("home")

    def _search_person(self) -> None:
        from semblon.gates import MODALITY_PRODUCT, enabled
        from semblon.search import SearchError, search_people, search_person, search_text

        q = (self.search_var.get() or "").strip()
        ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
        if q in {ph, SEARCH_PLACEHOLDER, SEARCH_PLACEHOLDER_PHOTOS}:
            q = ""
        if not q:
            messagebox.showinfo("Semblon", "Type a person name or text to search.")
            return
        if self.engine.busy:
            # State-aware: library still analysing — don't fail silently.
            self._set_inspector("Search", search_library_analysing().as_lines())
            if not self.store.is_file():
                return
            # Fall through only when a store already has named people to try.
        if not self.store.is_file():
            self._set_inspector("Search", search_no_store().as_lines())
            return
        try:
            named = search_people(self.store)
        except SearchError as e:
            if is_expected_condition(e):
                self._set_inspector("Search", search_no_store().as_lines())
            else:
                self._show_failure(e)
            return
        if not (named.get("items") or []):
            if self.engine.busy:
                self._set_inspector("Search", search_library_analysing().as_lines())
            else:
                self._set_inspector("Search", search_no_named_people().as_lines())
            return
        try:
            rec = search_person(self.store, q)
        except SearchError as e:
            if is_expected_condition(e):
                lines = search_no_matches(q).as_lines()
                if self.engine.busy:
                    lines = search_library_analysing().as_lines() + [""] + lines
                self._set_inspector("Search", lines)
            else:
                self._show_failure(e)
            return
        lines = format_search_lines(rec)
        if self.engine.busy and int(rec.get("count") or 0) == 0:
            lines = search_library_analysing().as_lines() + [""] + lines
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
        """User Settings panel (UX Rescue §6). Diagnostics live in Advanced."""
        if self._settings_win is not None:
            try:
                if self._settings_win.winfo_exists():
                    self._settings_win.lift()
                    self._settings_win.focus_force()
                    return
            except tk.TclError:
                self._settings_win = None

        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title("Settings")
        win.geometry("640x560")
        win.minsize(480, 420)
        if apply_theme is not None:
            apply_theme(win)
        try:
            win.transient(self.root)
            win.configure(bg=BG_CANVAS)
        except tk.TclError:
            pass

        pad = ttk.Frame(win, padding=(SP_32, SP_24))
        pad.pack(fill=tk.BOTH, expand=True)

        head = ttk.Frame(pad)
        head.pack(fill=tk.X)
        ttk.Label(head, text="Settings", font=H2).pack(side=tk.LEFT)
        _button(head, "Close", win.destroy, kind="tertiary", icon="x").pack(side=tk.RIGHT)

        # Library
        ttk.Label(pad, text="Library", font=BODY_STRONG).pack(anchor=tk.W, pady=(SP_16, SP_8))
        ttk.Label(pad, text="Library location", font=BODY).pack(anchor=tk.W)
        loc_row = ttk.Frame(pad)
        loc_row.pack(fill=tk.X, pady=(SP_8, 0))
        self._settings_lib_var = tk.StringVar(value=str(self.store))
        ttk.Label(
            loc_row,
            textvariable=self._settings_lib_var,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=240,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        _button(
            loc_row, "Change…", self._settings_change_library, kind="secondary"
        ).pack(side=tk.RIGHT)

        # Processing — GPU toggle (session prefer path; no engine redesign)
        ttk.Label(pad, text="Processing", font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
        gpu_available = False
        try:
            from semblon.engine import select_execution_provider

            gpu_available = bool(select_execution_provider(prefer_gpu=True).get("gpu"))
        except Exception:  # noqa: BLE001 — display-only
            gpu_available = False
        if gpu_available:
            initial = (
                self._prefer_gpu_user
                if self._prefer_gpu_user is not None
                else resolve_home_prefer_gpu()
            )
            self._gpu_var = tk.BooleanVar(value=bool(initial))

            def _on_gpu() -> None:
                self._prefer_gpu_user = bool(self._gpu_var.get())

            ttk.Checkbutton(
                pad,
                text="Use GPU when available",
                variable=self._gpu_var,
                command=_on_gpu,
            ).pack(anchor=tk.W)
        else:
            ttk.Label(
                pad,
                text="Processing on this computer.",
                font=CAPTION,
                foreground=TEXT_SECONDARY,
            ).pack(anchor=tk.W)

        ttk.Label(pad, text="Appearance", font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
        from semblon.ui_prefs import load_theme_mode

        self._theme_var = tk.StringVar(value=load_theme_mode(self.store))
        for mode, label in (
            ("system", "System"),
            ("light", "Light"),
            ("dark", "Dark"),
        ):
            ttk.Radiobutton(
                pad,
                text=label,
                value=mode,
                variable=self._theme_var,
                command=lambda m=mode: self._set_theme_mode(m),
            ).pack(anchor=tk.W)

        ttk.Label(pad, text="Shortcuts", font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
        for shortcut, keys in (
            (
                getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER),
                "Ctrl+F",
            ),
            ("Go to", "Ctrl+K"),
            ("Photos", "Ctrl+1"),
            ("Videos", "Ctrl+2"),
            ("People", "Ctrl+3"),
            ("To review", "Ctrl+4"),
            ("Recent activity", "Ctrl+5"),
        ):
            row = ttk.Frame(pad)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=shortcut, font=BODY).pack(side=tk.LEFT)
            ttk.Label(
                row, text=keys, font=META, foreground=TEXT_SECONDARY
            ).pack(side=tk.RIGHT)

        # About
        ttk.Label(pad, text="About", font=BODY_STRONG).pack(anchor=tk.W, pady=(SP_24, SP_8))
        try:
            from semblon import __version__ as _ver
        except Exception:  # noqa: BLE001
            _ver = "1.4.0"
        ttk.Label(pad, text="Semblon", font=H2).pack(anchor=tk.W)
        ttk.Label(
            pad, text=f"Version {_ver}", font=CAPTION, foreground=TEXT_SECONDARY
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        ttk.Label(
            pad,
            text="All processing stays on this computer. Nothing is uploaded.",
            font=BODY,
            wraplength=300,
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        _button(
            pad,
            "Advanced diagnostics…",
            self._open_advanced_diagnostics,
            kind="tertiary",
        ).pack(anchor=tk.W, pady=(SP_16, 0))

        def _on_close() -> None:
            self._settings_win = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _settings_change_library(self) -> None:
        """Pick an existing store.sqlite — presentation path only; no ingest change."""
        if self.engine.busy:
            messagebox.showinfo("Semblon", "Finish or cancel processing before changing the library.")
            return
        path = filedialog.askopenfilename(
            title="Choose Semblon library (store.sqlite)",
            filetypes=[("SQLite", "*.sqlite"), ("All files", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        self.store = Path(path)
        self.engine = JobEngine(self.store)
        if hasattr(self, "_settings_lib_var"):
            self._settings_lib_var.set(str(self.store))

    # UX-RESCUE S7 — Settings (§6) wires Advanced diagnostics entry.
    def _open_advanced_diagnostics(self) -> None:
        try:
            from semblon.advanced_diagnostics import open_advanced_diagnostics
        except ImportError:
            messagebox.showinfo("Semblon", "Advanced diagnostics is not available yet.")
            return
        open_advanced_diagnostics(self.root, self.store)

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
