"""Legacy Tk Home shell.

Not the application architecture. PySide6 (`semblon shell`) is the forward
shell. This window is a client of Application: it submits jobs and draws
widgets. It does not construct a second JobEngine and it does not monkeypatch
its own class.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except (ModuleNotFoundError, ImportError):  # pragma: no cover - host without libtk
    tk = None
    filedialog = messagebox = simpledialog = ttk = None

from semblon.ui_copy import friendly_exception
from semblon.jobs import JobBusy
from semblon.job_controls import HOME_CONTROLS_ALWAYS_ON, home_control_states
from semblon.activity_surface import read_activity_snapshot
from semblon.ui_prefs import (
    load_library_filter,
    load_prefer_gpu,
    load_search_mode,
    load_window_geometry,
    resolve_home_store,
    save_last_store,
    save_library_filter,
    save_prefer_gpu,
    save_search_mode,
    save_window_geometry,
)
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
    is_expected_condition,
    lens_empty,
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
        BORDER_DEFAULT,
        BORDER_SUBTLE,
        CAPTION,
        DISPLAY,
        HERO,
        META,
        MONO,
        H1,
        H2,
        H3,
        INK_SECONDARY,
        INK_TERTIARY,
        INSPECTOR_WIDTH,
        REVIEW_NAV_ACTIVE_BG,
        REVIEW_NAV_ACTIVE_FG,
        SIDEBAR_WIDTH,
        SP_4,
        SP_8,
        SP_12,
        SP_16,
        SP_20,
        SP_24,
        SP_32,
        SP_48,
        STAT,
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
    BODY = ("Segoe UI", 12)
    BODY_SMALL = ("Segoe UI", 11)
    BODY_STRONG = ("Segoe UI", 12, "bold")
    BORDER_DEFAULT = "#E4E4E2"
    BORDER_SUBTLE = "#E4E4E2"
    CAPTION = ("Segoe UI", 10)
    DISPLAY = ("Segoe UI", 22, "bold")
    HERO = DISPLAY
    H1 = ("Segoe UI", 15, "bold")
    H2 = ("Segoe UI", 15, "bold")
    H3 = ("Segoe UI", 12)
    INK_SECONDARY = "#565656"
    INK_TERTIARY = "#8A8A8A"
    META = ("Segoe UI", 11)
    MONO = ("Cascadia Code", 11)
    INSPECTOR_WIDTH = 320
    REVIEW_NAV_ACTIVE_BG = "#12343A"
    REVIEW_NAV_ACTIVE_FG = "#5EEAD4"
    SIDEBAR_WIDTH = 228
    SP_4 = 4
    SP_8 = 8
    SP_12 = 12
    SP_16 = 16
    SP_20 = 20
    SP_24 = 24
    SP_32 = 32
    SP_48 = 48
    STAT = ("Segoe UI", 20, "bold")
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
    "refresh_home_nav",
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

# Product Library is route id "library". Compatibility aliases: home, photos, videos.
# Model D: HOME_NAV lists compact/palette destinations — not a MAIN sidebar.
HOME_NAV: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()


def _product_home_nav() -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """Compact destination list from the feature registry (keeps HOME_NAV in sync)."""
    from semblon.gui_registry import default_registry

    return default_registry().home_nav_tuple()


def refresh_home_nav() -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """Rebuild module HOME_NAV from the current default registry."""
    global HOME_NAV
    HOME_NAV = _product_home_nav()
    return HOME_NAV


# Seed at import — registry describes today's routes.
refresh_home_nav()

# Legacy width helper — Model D has no left rail; kept for tests.
CONDENSED_BELOW = 1100


def shell_is_condensed(width: int) -> bool:
    """Historical condensed-rail probe. Model D uses compact header only."""
    return int(width) < CONDENSED_BELOW


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
    First-run marketing only. Populated libraries use ``_show_library_home``.
    """
    from semblon.library_status import review_people_cta

    if files <= 0:
        return {
            "primary": "add",
            "show_review": False,
            "show_browse": False,
            "show_privacy": True,
            "add_label": "Add a photo folder",
            "review_label": review_people_cta(0),
        }
    if unnamed > 0:
        return {
            "primary": "review",
            "show_review": True,
            "show_browse": True,
            "show_privacy": False,
            "add_label": "Add a photo folder",
            "review_label": review_people_cta(unnamed),
        }
    return {
        "primary": "browse",
        "show_review": False,
        "show_browse": True,
        "show_privacy": False,
        "add_label": "Add another folder",
        "review_label": review_people_cta(0),
    }


def resolve_home_prefer_gpu() -> bool:
    """Product GPU prefer flag from honest ORT EP detection."""
    from semblon.engine import product_prefer_gpu

    return product_prefer_gpu()


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
    from semblon.product_surface import soft_people_header_lines

    items = rec.get("items") or []
    if not items:
        return people_empty().as_lines()
    lines = soft_people_header_lines()
    for i in items:
        name = (i.get("display_name") or "").strip() or "Named person"
        faces = int(i.get("faces") or 0)
        lines.append(f"{name}  ({faces} photos)" if faces else name)
    return lines


def format_unknown_lines(
    rec: dict, run_id: str, *, advanced: bool = False
) -> list[str]:
    """People to name — soft coaching by default; KNOWN=/UNKNOWN= only when advanced."""
    from semblon.product_surface import soft_unknown_coach_lines

    c = rec.get("counts") or {}
    waiting = int(c.get("UNKNOWN", 0) or 0) + int(c.get("REVIEW_REQUIRED", 0) or 0)
    lines = soft_unknown_coach_lines(waiting=waiting)
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


def _unnamed_cluster_face_paths(
    store: Path, *, limit: int = 12
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """One representative face per unnamed cluster — the review queue, visually."""
    if limit <= 0 or not store.is_file():
        return []
    conn = sqlite3.connect(str(store))
    try:
        conn.execute("PRAGMA busy_timeout=2000")
        rows = conn.execute(
            """
            SELECT m.path, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2
            FROM clusters c
            JOIN faces f ON f.cluster_id = c.cluster_id AND f.status = 'ok'
            JOIN observations o ON o.observation_id = f.observation_id
            JOIN media m ON m.media_id = o.media_id
            WHERE (c.status IS NULL OR c.status != 'ignored')
              AND NOT EXISTS (
                SELECT 1 FROM faces fx
                WHERE fx.cluster_id = c.cluster_id
                  AND fx.person_id IS NOT NULL
              )
            GROUP BY c.cluster_id
            ORDER BY COUNT(f.face_id) DESC, c.cluster_id
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
    """Production Home shell: Model D Memory-first Stage dissolve.

    Empty → Home Stage (capability introduction). Media → Memory Canvas with
    compact contextual chrome. No permanent MAIN sidebar. Inspector on demand.
    """

    _PANE_WORKSPACE = "WORKSPACE / INTELLIGENCE CANVAS"
    _PANE_INSPECTOR = "INSPECTOR"

    def __init__(self, store: Path | None = None):
        if tk is None or ttk is None or filedialog is None or messagebox is None:
            raise RuntimeError("tkinter is required for home-ui")
        self.store = resolve_home_store(store)
        try:
            save_last_store(self.store)
        except Exception:  # noqa: BLE001 — continuity must not block launch
            pass
        from semblon.application import Application

        self.app = Application(self.store)
        self.engine = self.app.engine
        from semblon.gui_registry import default_registry

        self._registry = default_registry()
        refresh_home_nav()
        self._busy = False
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._last_run_id: str | None = None
        self._last_review_html: Path | None = None
        self._last_folder: Path | None = None
        self._resume_ready = False
        self._q: queue.Queue = queue.Queue()
        self._nav = "library"
        self._nav_buttons: dict[str, ttk.Button] = {}
        try:
            self._prefer_gpu_user = load_prefer_gpu(self.store)
        except Exception:  # noqa: BLE001
            self._prefer_gpu_user = None
        self._completion: dict | None = None  # last done/cancelled summary for §11 card
        self._completion_kind: str | None = None  # "done" | "cancelled" | None
        self._last_progress_files: tuple[int | None, int | None] = (None, None)
        self._last_faces_found: int | None = None
        self._proc_thumbs_faces: int | None = None
        self._inspector_collapsed = False
        self._last_progress_event: ProgressEvent | None = None
        try:
            self._library_filter = load_library_filter(self.store)
        except Exception:  # noqa: BLE001
            self._library_filter = "all"
        self._browse_facet: str | None = None  # timeline | folders | moments
        self._browse_buckets: list[dict] = []
        self._browse_bucket_index: int = 0
        try:
            self._search_mode = load_search_mode(self.store)
        except Exception:  # noqa: BLE001
            self._search_mode = "people"
        try:
            from semblon.ui_prefs import load_grid_density as _load_dens

            self._grid_density = _load_dens(self.store)
        except Exception:  # noqa: BLE001
            self._grid_density = "comfortable"
        self._similar_media_ids: list[str] | None = None
        self._library_return: dict | None = None
        from semblon.culling_compare import CompareSession
        from semblon.discovery_loop import DiscoverySession

        self._discovery = DiscoverySession()
        self._compare = CompareSession()
        self._result_kind: str | None = None  # "similar" | "duplicates" | None
        self._duplicate_groups: list[dict] = []
        self._duplicate_group_index: int = 0
        self._duplicate_scan: dict | None = None
        self._dup_thread: threading.Thread | None = None
        self._dup_cancel = threading.Event()
        self._saved_regions: list[dict] = []
        self._saved_region_index: int = 0
        from semblon.scan_present import ScanPace

        self._scan_pace = ScanPace()
        self._apply_saved_theme()

        self.root = tk.Tk()
        self.root.title("Semblon")
        # Paint the shell before the first map so startup is not a white frame.
        try:
            self.root.configure(bg=BG_CANVAS)
            self.root.option_add("*Background", BG_CANVAS)
        except tk.TclError:
            pass
        from semblon.ui_theme import px

        self.root.minsize(px(self.root, WINDOW_MIN[0]), px(self.root, WINDOW_MIN[1]))
        saved_geom = None
        try:
            saved_geom = load_window_geometry()
        except Exception:  # noqa: BLE001
            saved_geom = None
        if saved_geom:
            try:
                self.root.geometry(saved_geom)
            except tk.TclError:
                saved_geom = None
        if not saved_geom:
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

        # Model D — full-bleed main; compact header chrome (no MAIN sidebar).
        try:
            from semblon.atmosphere_render import GradientBackdrop

            self._gradient = GradientBackdrop(self.root)
        except Exception:  # noqa: BLE001
            self._gradient = None
        self._shell = tk.Frame(self.root, bg=BG_CANVAS)
        self._shell.pack(fill=tk.BOTH, expand=True)
        self._theme_band = tk.Canvas(self._shell, height=72, highlightthickness=0, bd=0, bg=BG_CANVAS)
        self._theme_band.pack(fill=tk.X)
        self._theme_band.bind("<Configure>", self._on_theme_band_configure)
        self._theme_band_width = 0
        self._main = ttk.Frame(self._shell)
        self._main.pack(fill=tk.BOTH, expand=True)
        try:
            from semblon.atmosphere_render import active_atmosphere_id

            self._paint_theme_gradient(active_atmosphere_id())
        except Exception:  # noqa: BLE001
            pass
        self._sidebar = None  # no permanent MAIN sidebar (docs/SHELL-IA.md)
        self._rail = None
        self._nav_rows: list[tuple[str, object]] = []
        self._condensed: bool | None = None
        self._stage_forced = False

        top = ttk.Frame(self._main, padding=(SP_20, SP_16, SP_20, SP_12))
        top.pack(fill=tk.X)
        self._top = top
        self._to_name = tk.StringVar(value="")

        self.btn_brand = _button(
            top, "Semblon", self._open_home_stage, kind="tertiary", plate=BG_CANVAS
        )
        self.btn_brand.pack(side=tk.LEFT, padx=(0, SP_12))

        search_row = ttk.Frame(top)
        search_row.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, SP_12))
        self.search_var = tk.StringVar()
        mode_row = ttk.Frame(search_row)
        mode_row.pack(side=tk.TOP, anchor=tk.W, fill=tk.X)
        self._search_mode_buttons: dict[str, object] = {}
        from semblon.ui_primitives import SEARCH_MODES

        for key, label in SEARCH_MODES:
            btn = _button(
                mode_row,
                label,
                lambda k=key: self._set_search_mode(k),
                kind="secondary" if key == self._search_mode else "tertiary",
                plate=BG_CANVAS,
            )
            btn.pack(side=tk.LEFT, padx=(0, SP_4))
            self._search_mode_buttons[key] = btn
        entry_row = ttk.Frame(search_row)
        entry_row.pack(side=tk.TOP, fill=tk.X, pady=(SP_4, 0))
        self._search_entry = ttk.Entry(entry_row, textvariable=self.search_var, width=28)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        try:
            self._search_entry.configure(takefocus=True)
        except tk.TclError:
            pass
        self._search_placeholder = SEARCH_PLACEHOLDER_PHOTOS
        self._search_entry.insert(0, self._search_placeholder)
        try:
            self._search_entry.configure(foreground=INK_TERTIARY)
        except tk.TclError:
            pass
        self._search_entry.bind("<FocusIn>", self._search_focus_in)
        self._search_entry.bind("<FocusOut>", self._search_focus_out)
        self.btn_search = _button(
            entry_row, "Search", self._run_unified_search, kind="tertiary", icon="search"
        )
        self.btn_search.pack(side=tk.LEFT, padx=(SP_8, 0))
        self._search_entry.bind("<Return>", lambda _e: self._run_unified_search())
        self.root.bind("<Control-f>", lambda _e: self._search_entry.focus_set())
        self.root.bind("<Control-k>", self._open_command_palette)
        self.root.bind("<Control-Key-0>", lambda _e: self._open_home_stage())
        self.root.bind("<Control-Key-4>", lambda _e: self._navigate("lens"))
        self.root.bind("<Escape>", self._on_discovery_escape)
        self.root.bind("<Left>", lambda e: self._on_compare_arrow(-1, e))
        self.root.bind("<Right>", lambda e: self._on_compare_arrow(1, e))
        self.root.bind("<Return>", self._on_discovery_return)
        self.root.bind("<Key-k>", lambda e: self._on_compare_hotkey("keep", e))
        self.root.bind("<Key-K>", lambda e: self._on_compare_hotkey("keep", e))
        self.root.bind("<Key-x>", lambda e: self._on_compare_hotkey("reject", e))
        self.root.bind("<Key-X>", lambda e: self._on_compare_hotkey("reject", e))
        for nav in self._registry.nav_contributions():
            if not nav.shortcut:
                continue
            key = nav.shortcut
            self.root.bind(
                f"<Control-Key-{key}>",
                lambda _e, n=nav.route_id: self._navigate(n),
            )

        # Compact contextual modes — Discover / People / Activity (not MAIN destinations).
        modes = ttk.Frame(top)
        modes.pack(side=tk.RIGHT, padx=(0, SP_8))
        self._modes = modes
        self.btn_discover = _button(
            modes, "Discover", lambda: self._navigate("lens"), kind="tertiary", icon="lens"
        )
        self.btn_discover.pack(side=tk.LEFT, padx=(0, SP_4))
        self.btn_people = _button(
            modes, "People", self._open_people_mode, kind="tertiary"
        )
        self.btn_people.pack(side=tk.LEFT, padx=(0, SP_4))
        self.btn_activity = _button(
            modes, "Activity", lambda: self._navigate("activity"), kind="tertiary"
        )
        self.btn_activity.pack(side=tk.LEFT)
        self.btn_unknown = self.btn_people
        self._nav_buttons = {
            "lens": self.btn_discover,
            "people": self.btn_people,
            "activity": self.btn_activity,
            "library": self.btn_brand,
            "home": self.btn_brand,
        }

        self.btn_folder = _button(
            top, "Add Folder", self._choose_folder, kind="secondary", icon="folder-plus"
        )
        self.btn_folder.pack(side=tk.RIGHT, padx=(SP_8, 0))
        self.btn_settings = _button(
            top, "Settings", lambda: self._navigate("settings"), kind="tertiary", icon="settings"
        )
        self.btn_settings.pack(side=tk.RIGHT)
        self._nav_buttons["settings"] = self.btn_settings

        # ── Job controls (demoted — processing Pause/Cancel) ──
        jobs = ttk.Frame(self._main, padding=(12, 0, 12, 4))
        jobs.pack(fill=tk.X)
        self._jobs_frame = jobs
        # Kept for control-state map; never packed as a competing naming CTA.
        self.btn_review = _button(
            jobs, "Start naming", lambda: self._navigate("unknown"), kind="secondary"
        )
        self.btn_cancel = _button(jobs, "Cancel", self._request_cancel, kind="tertiary")
        self.btn_cancel.configure(state=tk.DISABLED)
        self.btn_pause = _button(
            jobs, "Pause", self._toggle_pause_resume, kind="tertiary", icon="pause"
        )
        self.btn_pause.configure(state=tk.DISABLED)
        self.btn_resume = self.btn_pause  # alias: one toggle control
        self.btn_live = _button(jobs, "Live…", self._open_live_overlay, kind="tertiary")
        self.btn_canvas = _button(
            jobs, "Canvas", lambda: self._navigate("canvas"), kind="tertiary", icon="images"
        )
        self._overflow = ttk.Menubutton(jobs, text="More")
        self._overflow.pack(side=tk.RIGHT, padx=(SP_8, 0))
        self._rebuild_overflow_menu()
        self._overflow.configure(menu=self._overflow_menu)

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

        # ── Body: Memory Canvas | Details ──
        self._library_status = tk.StringVar(value="")
        self._footer_local = tk.StringVar(value="● Local")
        self._footer_counts = tk.StringVar(value="")
        self._footer_ready = tk.StringVar(value="Ready")
        foot = ttk.Frame(self._main, padding=(SP_20, SP_8))
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        self._status_bar = foot
        self._footer_local_lbl = tk.Label(
            foot,
            textvariable=self._footer_local,
            font=META,
            fg=TEXT_SECONDARY,
            bg=BG_CANVAS,
        )
        self._footer_local_lbl.pack(side=tk.LEFT)
        self._footer_counts_lbl = tk.Label(
            foot,
            textvariable=self._footer_counts,
            font=META,
            fg=TEXT_SECONDARY,
            bg=BG_CANVAS,
        )
        self._footer_counts_lbl.pack(side=tk.LEFT, padx=(SP_12, 0))
        # Keep _library_status for older refresh paths; mirror into counts when set.
        self._footer_ready_lbl = tk.Label(
            foot,
            textvariable=self._footer_ready,
            font=META,
            fg=TEXT_SECONDARY,
            bg=BG_CANVAS,
        )
        self._footer_ready_lbl.pack(side=tk.RIGHT)
        self._footer_pulse_color = TEXT_SECONDARY
        self._processing_cue = None
        try:
            from semblon.atmosphere_render import ProcessingCue

            self._processing_cue = ProcessingCue(
                self.root, on_tick=self._on_processing_cue_tick
            )
        except Exception:  # noqa: BLE001
            self._processing_cue = None
        body = ttk.Frame(self._main, padding=(8, 0, 8, 8))
        body.pack(fill=tk.BOTH, expand=True)
        self._body = body
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=1, minsize=0)
        body.rowconfigure(0, weight=1)

        # Workspace (Stage / Memory Canvas / welcome). Role: WORKSPACE / INTELLIGENCE CANVAS.
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
        self._library_home = ttk.Frame(work)
        self._library_chrome = ttk.Frame(work)
        self._lens = ttk.Frame(work)
        self._activity = ttk.Frame(work)
        self._settings = ttk.Frame(work)
        self._atmosphere_tiles: list = []
        self._build_home_landing()
        self._build_processing_home()
        self._build_result_card_shell()
        self._build_library_home()
        self._build_library_chrome()
        self._build_lens_workspace()
        self._build_activity_workspace()
        self._build_settings_workspace()

        from semblon.canvas import CanvasWorkspace

        # Defer store load: CanvasWorkspace.reload → on_select must not run before
        # Inspector widgets exist, and before this attribute assignment completes.
        try:
            from semblon.media_grid import load_grid_density

            self._grid_density = load_grid_density(self.store)
        except Exception:  # noqa: BLE001
            self._grid_density = "comfortable"
        self._canvas_ws = CanvasWorkspace(
            work,
            store=None,
            run_id=None,
            on_select=self._on_canvas_select,
            show_chrome=True,
            on_image_open=self._on_image_open,
            application=self.app,
        )
        self._canvas_ws._on_compare_toggle = self._toggle_compare_candidate
        if hasattr(self._canvas_ws, "set_density"):
            self._canvas_ws.set_density(self._grid_density)
        try:
            self._canvas_ws._thumb_canvas.bind(
                "<Button-3>", self._on_library_context_menu, add="+"
            )
            self._canvas_ws.preview.bind(
                "<Button-3>", self._on_library_context_menu, add="+"
            )
        except (tk.TclError, AttributeError):
            pass
        self._compare_pane = tk.Frame(work, bg=BG_CANVAS)
        self._compare_tiles = tk.Frame(self._compare_pane, bg=BG_CANVAS)
        self._compare_tiles.pack(fill=tk.BOTH, expand=True, padx=SP_8, pady=SP_8)
        self._compare_photos: list = []

        # Inspector — contextual result for the current interaction.
        insp = ttk.Frame(body, padding=(SP_16, SP_16))
        insp.grid(row=0, column=1, sticky="nsew")
        self._inspector_frame = insp
        self._inspector_title = tk.StringVar(value="Details")
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
            anchor=tk.W, pady=(SP_8, 0)
        )
        evid_frame = ttk.Frame(insp)
        evid_frame.pack(fill=tk.BOTH, expand=True, pady=(SP_4, SP_8))
        from semblon.ui_primitives import ActionGroup, InspectorBody

        self._inspector_body = InspectorBody(evid_frame, width=260)
        self._inspector_body.pack(fill=tk.BOTH, expand=True)
        # Compatibility alias — older helpers still say self._inspector.
        self._inspector = self._inspector_body

        ttk.Label(insp, text="What you can do", font=CAPTION).pack(
            anchor=tk.W, pady=(SP_4, 0)
        )
        ttk.Label(
            insp,
            text="Name someone when you recognise them. Combining groups is separate from naming.",
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=260,
        ).pack(anchor=tk.W)

        actions = ttk.Frame(insp)
        actions.pack(fill=tk.X, pady=(SP_4, 0))
        self._verb_reason = tk.StringVar(value="")

        # Primary: type a name and save it. Add-to-person is for an existing person.
        identity = ActionGroup(actions, "Identity")
        identity.pack(fill=tk.X)
        name_row = ttk.Frame(identity.body)
        name_row.pack(fill=tk.X, pady=1)
        ttk.Label(name_row, text=VERB_LABEL_NAME).pack(side=tk.LEFT)
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(name_row, textvariable=self._name_var)
        self._name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(SP_8, 0))
        self._name_entry.bind("<Return>", lambda _e: self._inspector_name_commit())
        self._name_entry.bind("<Escape>", lambda _e: self._inspector_name_cancel())
        self._name_var.trace_add("write", lambda *_a: self._sync_name_save_button())

        # Item 22: Inspector verbs are registry commands. Labels and click
        # dispatch come from GuiCommand; enablement stays inspector_verb_states.
        # Name entry stays here — it is an input, not a command button.
        from semblon.product_features import INSPECTOR_VERB_SPECS

        verb_cmds = {
            c.id: c for c in self._registry.commands(surface="inspector")
        }
        self._verb_buttons: dict[str, object] = {}
        _verb_kind = {
            "name": "primary",
            "rule_out": "destructive",
        }
        for key, cmd_id, fallback, _method in INSPECTOR_VERB_SPECS:
            cmd = verb_cmds.get(cmd_id)
            label = cmd.label if cmd is not None else fallback
            btn = _button(
                identity.body,
                label,
                lambda c=cmd, k=key: self._run_inspector_verb(k, c),
                kind=_verb_kind.get(key, "secondary"),
            )
            btn.pack(fill=tk.X, pady=1)
            setattr(self, f"btn_{key}", btn)
            self._verb_buttons[key] = btn

        discover = ActionGroup(actions, "Discover")
        discover.pack(fill=tk.X)
        self.btn_region = _button(
            discover.body, "Select a region", self._open_region_select, kind="secondary"
        )
        self.btn_region.pack(fill=tk.X, pady=1)
        self.btn_find_similar = _button(
            discover.body, "Find Similar", self._find_similar_in_workspace, kind="secondary"
        )
        self.btn_find_similar.pack(fill=tk.X, pady=1)
        self.btn_ask_selection = _button(
            discover.body, "Ask about this selection", self._ask_about_selection, kind="secondary"
        )
        self.btn_ask_selection.pack(fill=tk.X, pady=1)
        self.btn_name_region = _button(
            discover.body, "Name this region", self._name_saved_region, kind="secondary"
        )
        self.btn_name_region.pack(fill=tk.X, pady=1)
        self.btn_duplicates = _button(
            discover.body, "Find Duplicates", self._scan_duplicates, kind="secondary"
        )
        self.btn_duplicates.pack(fill=tk.X, pady=1)
        self.btn_open_dup_group = _button(
            discover.body,
            "Open Duplicate Group",
            self._open_selected_duplicate_group,
            kind="secondary",
        )
        self.btn_open_dup_group.pack(fill=tk.X, pady=1)
        self.btn_saved_regions = _button(
            discover.body, "Saved Regions", self._show_saved_regions, kind="secondary"
        )
        self.btn_saved_regions.pack(fill=tk.X, pady=1)
        self.btn_ask_lens = _button(
            discover.body, "Ask about this photo", self._ask_with_lens, kind="secondary", icon="lens"
        )
        self.btn_ask_lens.pack(fill=tk.X, pady=1)

        compare_grp = ActionGroup(actions, "Compare")
        compare_grp.pack(fill=tk.X)
        self.btn_compare = _button(
            compare_grp.body, "Compare", self._enter_compare, kind="secondary"
        )
        self.btn_compare.pack(fill=tk.X, pady=1)
        self.btn_keep = _button(
            compare_grp.body, "Keep", lambda: self._compare_decide("keep"), kind="secondary"
        )
        self.btn_keep.pack(fill=tk.X, pady=1)
        self.btn_reject = _button(
            compare_grp.body, "Reject", lambda: self._compare_decide("reject"), kind="secondary"
        )
        self.btn_reject.pack(fill=tk.X, pady=1)
        # Registry contextual commands (person.history, identify, Leave Compare, …).
        # compare.exit is packed here so Leave Compare is an Inspector control.
        self._registry_cmd_buttons: dict[str, object] = {}
        _verb_ids = {spec[1] for spec in INSPECTOR_VERB_SPECS}
        for cmd in self._registry.commands(surface="inspector"):
            if cmd.id in _verb_ids or cmd.id in {
                "lens.select_region",
                "lens.ask",
                "lens.ask_selection",
                "lens.name_region",
                "lens.find_similar",
                "compare.enter",
                "media.keep",
                "media.reject",
                "library.duplicates",
                "duplicates.open_group",
            }:
                # Verbs packed from INSPECTOR_VERB_SPECS / discovery / duplicates above.
                continue
            parent = compare_grp.body if cmd.id == "compare.exit" else actions
            btn = _button(
                parent,
                cmd.label,
                lambda c=cmd: self._run_registry_command(c),
                kind="secondary",
            )
            btn.pack(fill=tk.X, pady=1)
            self._registry_cmd_buttons[cmd.id] = btn
            if cmd.id == "compare.exit":
                self.btn_leave_compare = btn
        ttk.Label(insp, textvariable=self._verb_reason, wraplength=260).pack(
            anchor=tk.W, pady=(SP_4, 0)
        )

        # Selection context for Inspector verbs (not identity).
        self._insp_run_id: str | None = None
        self._insp_media_id: str | None = None
        self._insp_available: list[dict] = []
        self._insp_selected: list[dict] = []
        self._insp_target_person_id: str | None = None
        self._insp_target_person_name: str | None = None
        self._last_user_region_id: str | None = None
        self._verb_states: dict = {}

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_queue)
        self._restyle_native_surfaces()
        self._restore_home_lifecycle()

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
            "People to name",
            "People",
            "Lens",
        }:
            from semblon.product_surface import SEL_HEADING_IDLE

            self._sel_heading.set(SEL_HEADING_IDLE)
        body = getattr(self, "_inspector_body", None) or self._inspector
        if hasattr(body, "set_lines"):
            body.set_lines(lines, default_title=title if title else "Details")
        else:
            body.delete(0, tk.END)
            for line in lines:
                body.insert(tk.END, line)
        # Non-selection views keep verb disable reasons honest.
        # Lens keeps the current media_id — clearing it would break the workspace.
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
            "People to name",
            "Lens",
        }:
            self._sel_list.bind("<<ListboxSelect>>", lambda _e: self._on_inspector_sel_change())
            if title not in {"Canvas", "Lens"}:
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

    def _open_region_select(self) -> None:
        """Draw a region, persist the box, and find similar photos.

        This is the production region command. It is a real method — nothing
        replaces it on the class at launch.
        """
        from semblon.lens_release import remember_selection
        from semblon.selection import LENS_BUSY, media_file, open_region_window

        path = media_file(self.store, getattr(self, "_insp_media_id", None))
        if path is None:
            self._set_inspector(
                "Details",
                [
                    "Open a photo first.",
                    "Then select something to look at.",
                    "Nothing was searched.",
                ],
            )
            self._set_inspector_collapsed(False)
            return

        def done(lines: list[str]) -> None:
            try:
                self._set_inspector("Details", lines or ["Nothing was searched."])
                self._set_inspector_collapsed(False)
            except Exception:  # noqa: BLE001
                pass
            summary = getattr(self, "_last_lens_result", None)
            if summary:
                try:
                    self._apply_find_similar_result(summary)
                except Exception:  # noqa: BLE001
                    pass

        def on_rect(rect: dict) -> None:
            media_id = getattr(self, "_insp_media_id", None)
            if not media_id:
                done(["Open a photo first.", "Nothing was searched."])
                return
            rec = remember_selection(
                self.store,
                media_id=str(media_id),
                image_path=path,
                x=int(rect["x"]),
                y=int(rect["y"]),
                w=int(rect["w"]),
                h=int(rect["h"]),
                app=self.app,
            )
            self._last_lens_result = rec.get("summary") or {}
            self._last_lens_rect = {
                "x": int(rect["x"]),
                "y": int(rect["y"]),
                "w": int(rect["w"]),
                "h": int(rect["h"]),
                "kept": True,
            }
            self._remember_user_region_id(rec)
            done(rec.get("lines") or ["No similar images found yet."])
            try:
                self._sync_discovery_actions()
            except Exception:  # noqa: BLE001
                pass

        def on_busy(flag: bool) -> None:
            self._lens_busy = bool(flag)
            if hasattr(self, "_lens_status"):
                try:
                    self._lens_status.set(LENS_BUSY if flag else "")
                except Exception:  # noqa: BLE001
                    pass

        open_region_window(
            self.root,
            path,
            done,
            on_busy=on_busy,
            schedule=lambda fn: self.root.after(0, fn),
            on_rect=on_rect,
        )

    def _set_lens_processing(self, busy: bool) -> None:
        """Drive Find Similar / Lens controls into PROCESSING visual state."""
        for name in ("btn_lens_region", "btn_lens_whole", "btn_lens_browse"):
            btn = getattr(self, name, None)
            if btn is None:
                continue
            if hasattr(btn, "set_processing"):
                try:
                    btn.set_processing(busy)
                except Exception:  # noqa: BLE001
                    pass

    def _ask_with_lens(self) -> None:
        """Inspector: ask about the open photo. Runs the whole-frame query."""
        media_id = getattr(self, "_insp_media_id", None)
        if not media_id:
            self._set_inspector(
                "Lens",
                [
                    "Open a photo first.",
                    "Then use Ask with Lens. Nothing was searched.",
                ],
            )
            return
        self._open_lens()
        self._lens_ask_whole()

    def _selection_query_rect(self) -> dict | None:
        """Current Discover/Canvas/last-remembered rectangle, if any."""
        from semblon.discovery_loop import image_rect_from_selection
        from semblon.selection import media_file

        media_id = getattr(self, "_insp_media_id", None)
        if media_file(self.store, media_id) is None:
            return None
        session = getattr(self, "_discovery", None)
        if session is not None and session.query_rect and (
            not session.query_media_id or str(session.query_media_id) == str(media_id)
        ):
            return dict(session.query_rect)
        ws = getattr(self, "_canvas_ws", None)
        sel = getattr(ws, "_selected", None) if ws is not None else None
        rect = image_rect_from_selection(sel)
        if rect:
            return rect
        last = getattr(self, "_last_lens_rect", None)
        if isinstance(last, dict) and last.get("kept"):
            return {
                "x": int(last["x"]),
                "y": int(last["y"]),
                "w": int(last["w"]),
                "h": int(last["h"]),
            }
        return None

    def _ask_about_selection(self) -> None:
        """Capability query on the selected region — distinct from Find Similar."""
        from semblon.selection import LENS_BUSY, media_file

        media_id = getattr(self, "_insp_media_id", None)
        path = media_file(self.store, media_id)
        rect = self._selection_query_rect()
        if path is None or rect is None:
            self._set_inspector(
                "Ask",
                [
                    "Select a region on a photo first.",
                    "Ask understands that selection. Find Similar searches for matches.",
                    "Nothing was searched.",
                ],
            )
            self._set_inspector_collapsed(False)
            return

        def done(lines: list[str], summary: dict | None) -> None:
            try:
                self._set_inspector("Ask", lines or ["Nothing was searched."])
                self._set_inspector_collapsed(False)
            except Exception:  # noqa: BLE001
                pass
            if summary is not None:
                self._last_lens_result = summary

        def work() -> None:
            try:
                if hasattr(self, "_lens_status"):
                    self.root.after(0, lambda: self._lens_status.set(LENS_BUSY))
                rec = self.app.query_media(str(media_id), dict(rect))
            except Exception as exc:  # noqa: BLE001
                self.root.after(
                    0,
                    lambda: done(
                        ["Semblon could not finish looking.", "Nothing was searched.", str(exc)],
                        None,
                    ),
                )
                return
            lines = list(rec.get("lines") or ["Nothing was searched."])
            self.root.after(0, lambda: done(lines, rec))

        threading.Thread(target=work, name="semblon-lens-query", daemon=True).start()

    def _name_saved_region(self) -> None:
        """Human label on a persisted user region — not a person."""
        from tkinter import simpledialog

        from semblon.user_region import RegionError

        item_id = getattr(self, "_last_user_region_id", None)
        if not item_id:
            messagebox.showinfo(
                "Semblon",
                "Select a region and run Find Similar (or remember it) first.",
            )
            return
        label = simpledialog.askstring(
            "Name this region",
            "Label for this selection (not a person name):",
            parent=self.root,
        )
        if not label or not str(label).strip():
            return
        try:
            rec = self.app.name_region(str(item_id), str(label).strip())
        except RegionError as e:
            messagebox.showerror("Semblon", str(e))
            return
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Semblon", f"Could not name region: {e}")
            return
        named = rec.get("named") or label
        self._set_inspector(
            "Region",
            [
                f"Named this region: {named}",
                "This is a label on a saved selection — not a person.",
            ],
        )
        self._set_inspector_collapsed(False)
        self.status.set(f"Region labeled {named!r}.")
        self._sync_discovery_actions()

    def _remember_user_region_id(self, rec: dict | None) -> None:
        region = (rec or {}).get("region") if isinstance(rec, dict) else None
        if isinstance(region, dict) and region.get("item_id"):
            try:
                self._last_user_region_id = str(region["item_id"])
            except Exception:  # noqa: BLE001 — stubs / FakeHome
                pass

    def _open_lens(self) -> None:
        """Lens route: coherent Inspect workspace inside Home (not a second app)."""
        self._nav = "lens"
        self._mark_nav_active("lens")
        self._show_lens_workspace()
        self._sync_chrome_for_route()

    def _build_lens_workspace(self) -> None:
        """Lens / Inspect pane — open photo → select → soft results."""
        from semblon.home_shell import LENS_UNDERSTANDING_TITLE
        from semblon.selection import LENS_HEADLINE, LENS_SUBCOPY

        if self._pane_is_ready("lens"):
            return
        for child in self._lens.winfo_children():
            child.destroy()
        shell = ttk.Frame(self._lens, padding=(SP_24, SP_20))
        shell.pack(fill=tk.BOTH, expand=True)
        ttk.Label(shell, text=LENS_HEADLINE, font=H1).pack(anchor=tk.W)
        ttk.Label(
            shell,
            text=LENS_SUBCOPY,
            font=BODY,
            foreground=TEXT_SECONDARY,
            wraplength=560,
        ).pack(anchor=tk.W, pady=(SP_4, SP_16))

        self._lens_asset = tk.StringVar(value="")
        ttk.Label(
            shell, textvariable=self._lens_asset, font=BODY_STRONG, wraplength=560
        ).pack(anchor=tk.W)

        self._lens_status = tk.StringVar(value="")
        ttk.Label(
            shell,
            textvariable=self._lens_status,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
        ).pack(anchor=tk.W, pady=(SP_4, 0))

        actions = ttk.Frame(shell)
        actions.pack(anchor=tk.W, pady=(SP_12, SP_8))
        self.btn_lens_region = _button(
            actions, "Select a region", self._open_region_select, kind="primary"
        )
        self.btn_lens_region.pack(side=tk.LEFT, padx=(0, SP_8))
        self.btn_lens_whole = _button(
            actions, "Ask about this photo", self._lens_ask_whole, kind="secondary"
        )
        self.btn_lens_whole.pack(side=tk.LEFT, padx=(0, SP_8))
        self.btn_lens_browse = _button(
            actions, "Browse photos", lambda: self._navigate("photos"), kind="tertiary"
        )
        self.btn_lens_browse.pack(side=tk.LEFT)

        ttk.Label(shell, text=LENS_UNDERSTANDING_TITLE, font=CAPTION).pack(
            anchor=tk.W, pady=(SP_16, SP_4)
        )
        self._lens_understanding = ttk.Frame(shell)
        self._lens_understanding.pack(anchor=tk.W, fill=tk.X)

        ttk.Label(shell, text="Results", font=CAPTION).pack(
            anchor=tk.W, pady=(SP_16, SP_4)
        )
        self._lens_result_var = tk.StringVar(value="Nothing has been asked yet.")
        ttk.Label(
            shell,
            textvariable=self._lens_result_var,
            font=BODY,
            wraplength=560,
            foreground=TEXT_SECONDARY,
        ).pack(anchor=tk.W)

        # Stage hosts the embedded region canvas (or empty guide).
        self._lens_stage = ttk.Frame(shell)
        self._lens_stage.pack(fill=tk.BOTH, expand=True, pady=(SP_16, 0))
        self._lens_busy = False
        self._last_lens_result: dict | None = getattr(self, "_last_lens_result", None)

    def _lens_ask_whole(self) -> None:
        """Query the full image through Application.query_media."""
        from semblon.selection import LENS_BUSY, media_file

        media_id = getattr(self, "_insp_media_id", None)
        path = media_file(self.store, media_id)
        if path is None:
            self._set_inspector(
                "Lens",
                [
                    "Open a photo first.",
                    "Then ask about it. Nothing was searched.",
                ],
            )
            return

        def done(lines: list[str], summary: dict | None) -> None:
            try:
                self._set_inspector("Lens", lines or ["Nothing was searched."])
            except Exception:  # noqa: BLE001
                pass
            if summary is not None:
                self._last_lens_result = summary
                if hasattr(self, "_refresh_library_shell"):
                    try:
                        self._refresh_library_shell()
                    except Exception:  # noqa: BLE001
                        pass
            self._lens_busy = False
            self._set_lens_processing(False)
            try:
                if hasattr(self, "_lens_status"):
                    self._lens_status.set("")
                self.btn_lens_region.configure(state=tk.NORMAL)
                self.btn_lens_whole.configure(state=tk.NORMAL)
            except Exception:  # noqa: BLE001
                pass
            self._refresh_lens_workspace()

        def work() -> None:
            try:
                rec = self.app.query_media(str(media_id))
            except Exception as exc:  # noqa: BLE001
                self.root.after(
                    0,
                    lambda: self._set_inspector(
                        "Lens",
                        ["Semblon could not finish looking.", "Nothing was searched.", str(exc)],
                    ),
                )
                return
            lines = list(rec.get("lines") or ["Nothing was searched."])
            self.root.after(0, lambda: done(lines, rec))

        self._lens_busy = True
        self._set_lens_processing(True)
        try:
            if hasattr(self, "_lens_status"):
                self._lens_status.set(LENS_BUSY)
            self.btn_lens_region.configure(state=tk.DISABLED)
            self.btn_lens_whole.configure(state=tk.DISABLED)
        except Exception:  # noqa: BLE001
            pass
        threading.Thread(target=work, name="semblon-lens-query", daemon=True).start()

    def _refresh_lens_workspace(self) -> None:
        """Repaint Lens pane from current media + last result + honesty rows."""
        if not hasattr(self, "_lens_stage"):
            return
        from semblon.empty_states import mount_empty_state
        from semblon.home_shell import last_result_copy, lens_understanding_rows
        from semblon.selection import LENS_EMPTY_GUIDE, media_basename, media_file

        media_id = getattr(self, "_insp_media_id", None)
        path = media_file(self.store, media_id)
        name = media_basename(self.store, media_id)

        for child in self._lens_understanding.winfo_children():
            child.destroy()
        for row in lens_understanding_rows():
            line = ttk.Frame(self._lens_understanding)
            line.pack(anchor=tk.W, fill=tk.X, pady=1)
            ttk.Label(line, text=row["label"], font=BODY).pack(side=tk.LEFT)
            ttk.Label(
                line, text=row["state"], font=CAPTION, foreground=TEXT_SECONDARY
            ).pack(side=tk.RIGHT)

        body, _hint = last_result_copy(getattr(self, "_last_lens_result", None))
        self._lens_result_var.set(body)

        for child in self._lens_stage.winfo_children():
            child.destroy()

        if path is None:
            self._lens_asset.set(LENS_EMPTY_GUIDE)
            try:
                self.btn_lens_region.configure(state=tk.DISABLED)
                self.btn_lens_whole.configure(state=tk.DISABLED)
            except tk.TclError:
                pass
            empty = lens_empty()
            mount_empty_state(
                self._lens_stage,
                empty,
                on_primary=lambda: self._navigate("photos"),
                tk_mod=tk,
                ttk_mod=ttk,
            ).pack(fill=tk.BOTH, expand=True)
            self._set_inspector("Lens", empty.as_lines())
            return

        self._lens_asset.set(f"Looking at · {name}")
        try:
            busy = bool(getattr(self, "_lens_busy", False))
            state = tk.DISABLED if busy else tk.NORMAL
            self.btn_lens_region.configure(state=state)
            self.btn_lens_whole.configure(state=state)
        except tk.TclError:
            pass
        ttk.Label(
            self._lens_stage,
            text="Select a region on the photo, or ask about the whole picture.",
            font=BODY,
            foreground=TEXT_SECONDARY,
            wraplength=560,
        ).pack(anchor=tk.W)
        last = getattr(self, "_last_lens_result", None)
        if last:
            lines = [body]
            if last.get("reason") and str(last.get("status") or "").upper() != "SUCCESS":
                lines = [str(last.get("reason"))]
            self._set_inspector("Lens", lines)
        else:
            self._set_inspector(
                "Lens",
                [
                    "Lens",
                    f"Photo · {name}",
                    "Select a region, or ask about this photo.",
                    "Semblon uses available understanding — missing models say so.",
                ],
            )
        self._mark_pane_ready("lens")

    def _show_lens_workspace(self) -> None:
        self._hide_workspace_panes()
        self._set_inspector_collapsed(False)
        self._lens.pack(fill=tk.BOTH, expand=True)
        self._refresh_lens_workspace()

    def _library_has_media(self) -> bool:
        summary = self._library_summary()
        return bool(summary and int(summary.get("files") or 0) > 0)

    def _rebuild_overflow_menu(self) -> None:
        """More menu from registry overflow commands (deduped labels)."""
        self._overflow_menu = tk.Menu(self._overflow, tearoff=0)
        seen: set[str] = set()
        # P2 — advanced surfaces stay out of the first-success path.
        advanced_ids = {
            "shell.live",
            "library.duplicates",
            "library.explore",
            "shell.open_canvas",
        }
        has_media = self._library_has_media()
        for cmd in self._registry.commands(surface="overflow"):
            if cmd.label in seen:
                continue
            if not has_media and cmd.id in advanced_ids:
                continue
            if not has_media and cmd.label in {"Live…", "Find Duplicates", "Explore", "Canvas"}:
                continue
            seen.add(cmd.label)
            self._overflow_menu.add_command(
                label=cmd.label,
                command=lambda c=cmd: self._run_registry_command(c),
            )
        if hasattr(self, "_overflow"):
            self._overflow.configure(menu=self._overflow_menu)

    def _inspector_context(self) -> dict:
        return {
            "selected": list(getattr(self, "_insp_selected", []) or []),
            "run_id": getattr(self, "_insp_run_id", None),
            "media_id": getattr(self, "_insp_media_id", None),
        }

    def _run_registry_command(self, cmd) -> None:
        cmd.execute(self, self._inspector_context())

    def _run_inspector_verb(self, key: str, cmd) -> None:
        """Dispatch a registry Inspector verb. Review remains the mutation path."""
        if cmd is not None:
            cmd.execute(self, self._inspector_context())
            return
        fallback = {
            "name": self._inspector_name_commit,
            "assign": self._inspector_assign,
            "merge": self._inspector_merge,
            "split": self._inspector_split,
            "rule_out": self._inspector_rule_out,
            "ignore": self._inspector_ignore,
            "note": self._inspector_note,
        }.get(key)
        if fallback is not None:
            fallback()

    def _sync_registry_inspector_commands(self) -> None:
        ctx = self._inspector_context()
        for cmd_id, btn in list(getattr(self, "_registry_cmd_buttons", {}).items()):
            cmd = self._registry.get_command(cmd_id)
            if cmd is None:
                continue
            ok = cmd.is_available(self, ctx)
            try:
                btn.configure(state=tk.NORMAL if ok else tk.DISABLED)
            except tk.TclError:
                pass

    def _build_activity_workspace(self) -> None:
        """Activity / Memory pane — soft history, not the database model."""
        from semblon.features.activity_feature import build_activity_workspace

        build_activity_workspace(self)

    def _refresh_activity_workspace(self, view: dict | None = None) -> None:
        from semblon.features.activity_feature import refresh_activity_workspace

        refresh_activity_workspace(self, view)

    def _show_activity_workspace(self) -> None:
        self._hide_workspace_panes()
        self._set_inspector_collapsed(False)
        self._activity.pack(fill=tk.BOTH, expand=True)

    def _open_command_palette(self, _event=None):
        """Jump to a real destination. Not a second navigation model."""
        if tk is None:
            return "break"
        win = tk.Toplevel(self.root)
        win.title("Semblon")
        win.transient(self.root)
        win.geometry("360x320")
        if apply_theme is not None:
            apply_theme(win)
        try:
            win.configure(bg=BG_CANVAS)
        except tk.TclError:
            pass
        ttk.Label(win, text="Go to", font=H3).pack(anchor=tk.W, padx=SP_16, pady=(SP_16, SP_8))
        filter_var = tk.StringVar()
        entry = ttk.Entry(win, textvariable=filter_var)
        entry.pack(fill=tk.X, padx=SP_16, pady=(0, SP_8))
        box = tk.Listbox(win, exportselection=False, activestyle="none")
        if style_listbox is not None:
            style_listbox(box)
        box.pack(fill=tk.BOTH, expand=True, padx=SP_16, pady=(0, SP_16))

        # Destinations from nav + Settings + palette commands (dedupe by label).
        rows: list[tuple[str, str, object | None]] = []
        for nav in self._registry.nav_contributions():
            rows.append((nav.label, "nav", nav.route_id))
        rows.append(("Settings", "nav", "settings"))
        seen_labels = {r[0] for r in rows}
        for cmd in self._registry.commands(surface="palette"):
            if cmd.label in seen_labels:
                continue
            if cmd.requires_context and not cmd.is_available(self, self._inspector_context()):
                continue
            seen_labels.add(cmd.label)
            rows.append((cmd.label, "cmd", cmd))

        def _repaint(*_a) -> None:
            q = (filter_var.get() or "").strip().lower()
            box.delete(0, tk.END)
            box._palette_rows = []  # type: ignore[attr-defined]
            for label, kind, payload in rows:
                if q and q not in label.lower():
                    continue
                box.insert(tk.END, label)
                box._palette_rows.append((kind, payload))  # type: ignore[attr-defined]

        def _go(_e=None) -> None:
            sel = box.curselection()
            if not sel:
                return
            kind, payload = box._palette_rows[sel[0]]  # type: ignore[attr-defined]
            win.destroy()
            if kind == "nav":
                self._navigate(str(payload))
            else:
                self._run_registry_command(payload)

        filter_var.trace_add("write", lambda *_a: _repaint())
        _repaint()
        box.bind("<Return>", _go)
        box.bind("<Double-Button-1>", _go)
        box.bind("<Escape>", lambda _e: win.destroy())
        entry.bind("<Return>", _go)
        entry.bind("<Escape>", lambda _e: win.destroy())
        entry.focus_set()
        return "break"

    def _navigate(self, nav_id: str) -> None:
        if nav_id not in {"library", "home"}:
            self._stage_forced = False
        self._nav = nav_id
        self._mark_nav_active(nav_id)
        self._refresh_library_chrome()
        page = self._registry.resolve_route(nav_id)
        if page is not None:
            page(self)
            self._sync_chrome_for_route()
            self._refresh_job_controls()
            return
        # Compatibility fallback for any route not yet registered.
        if nav_id == "home":
            self._show_home_landing()
        elif nav_id == "canvas":
            self._show_workspace_canvas(reload=True, source_types=None)
            self._set_inspector("Canvas", list(INSPECTOR_EMPTY))
        elif nav_id == "photos":
            self._show_workspace_canvas(reload=True, source_types=("folder",))
            lib = format_library_lines(self.store, source_type="folder")
            if not library_has_media_lines(lib):
                self._set_inspector("Photos", photos_empty().as_lines())
        elif nav_id == "videos":
            self._show_workspace_canvas(reload=True, source_types=("video",))
            lib = format_library_lines(self.store, source_type="video")
            if not library_has_media_lines(lib):
                self._set_inspector("Videos", videos_empty().as_lines())
        elif nav_id == "lens":
            self._open_lens()
            self._refresh_job_controls()
            return
        elif nav_id == "people":
            self._welcome_title.set("People")
            self._show_workspace_welcome()
            self._show_people()
        elif nav_id == "unknown":
            self._welcome_title.set("People to name")
            self._show_workspace_welcome()
            self._show_unknown()
        elif nav_id == "activity":
            self._show_activity()
        self._sync_chrome_for_route()
        self._refresh_job_controls()

    def _show_activity(self) -> None:
        """Canonical Activity / Memory workspace — soft history, not schema dump."""
        from semblon.features.activity_feature import show_activity_page

        show_activity_page(self)

    def _on_inspector_sel_change(self) -> None:
        idxs = list(self._sel_list.curselection())
        self._insp_selected = [
            self._insp_available[i] for i in idxs if 0 <= i < len(self._insp_available)
        ]
        # Cluster row alone: point the user at full-face comparison in Review.
        if (
            len(self._insp_selected) == 1
            and self._insp_selected[0].get("kind") == "cluster"
        ):
            members = self._insp_selected[0].get("members") or []
            n = len(members)
            if n > 1:
                self.status.set(
                    f"{n} faces in this group — open To name to compare and name."
                )
        self._refresh_inspector_verbs()

    def _refresh_inspector_verbs(self) -> None:
        from semblon.inspector_verbs import inspector_verb_states

        self._verb_states = inspector_verb_states(
            self._insp_selected,
            run_id=self._insp_run_id or self._last_run_id,
            target_person_id=self._insp_target_person_id,
        )
        buttons = dict(getattr(self, "_verb_buttons", {}) or {})
        buttons.pop("name", None)
        if not buttons:
            buttons = {
                "merge": self.btn_merge,
                "assign": self.btn_assign,
                "split": self.btn_split,
                "rule_out": self.btn_rule_out,
                "ignore": self.btn_ignore,
                "note": getattr(self, "btn_note", None),
            }
            buttons = {k: v for k, v in buttons.items() if v is not None}
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
        self._sync_name_save_button()
        self._verb_reason.set(" · ".join(reasons[:3]) if reasons else "")
        self._sync_discovery_actions()
        self._sync_registry_inspector_commands()

    def _sync_discovery_actions(self) -> None:
        """Enable Select a region / Find Similar / Compare when appropriate."""
        from semblon.selection import media_file

        has_media = media_file(self.store, getattr(self, "_insp_media_id", None)) is not None
        cmp = getattr(self, "_compare", None)
        comparing = bool(cmp and cmp.active)
        for attr in ("btn_region", "btn_find_similar"):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.configure(state=tk.NORMAL if has_media and not comparing else tk.DISABLED)
            except tk.TclError:
                pass
        has_rect = self._selection_query_rect() is not None
        ask_sel = getattr(self, "btn_ask_selection", None)
        if ask_sel is not None:
            try:
                ask_sel.configure(
                    state=tk.NORMAL if has_rect and not comparing else tk.DISABLED
                )
            except tk.TclError:
                pass
        name_reg = getattr(self, "btn_name_region", None)
        if name_reg is not None:
            try:
                name_reg.configure(
                    state=tk.NORMAL
                    if getattr(self, "_last_user_region_id", None) and not comparing
                    else tk.DISABLED
                )
            except tk.TclError:
                pass
        can_compare = bool(cmp and cmp.can_enter()[0])
        for attr in ("btn_compare", "btn_bar_compare"):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.configure(state=tk.NORMAL if can_compare else tk.DISABLED)
            except tk.TclError:
                pass
        for attr in ("btn_keep", "btn_reject"):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.configure(
                    state=tk.NORMAL if comparing and cmp.focused_id() else tk.DISABLED
                )
            except tk.TclError:
                pass
        back = getattr(self, "btn_discovery_back", None)
        if back is not None:
            hist = bool(
                comparing
                or (getattr(self, "_discovery", None) and self._discovery.has_history())
            )
            try:
                back.configure(state=tk.NORMAL if hist else tk.DISABLED)
            except tk.TclError:
                pass
        n_sel = len(cmp.selected_ids) if cmp else 0
        kind = getattr(self, "_result_kind", None)
        if getattr(self, "_similar_title", None) is not None and (
            getattr(self, "_similar_media_ids", None) or kind == "duplicates"
        ):
            if kind == "duplicates":
                n_groups = len(getattr(self, "_duplicate_groups", None) or [])
                base = f"Exact duplicates · {n_groups} group{'s' if n_groups != 1 else ''}"
            else:
                base = "Similar to selected region"
            if comparing:
                self._similar_title.set("Comparing candidates")
            elif n_sel:
                self._similar_title.set(f"{base} · {n_sel} selected")
            else:
                self._similar_title.set(base)
        lib_ready = self._library_has_media()
        dup_busy = self._duplicate_scan_busy()
        for attr in ("btn_duplicates",):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.configure(
                    state=tk.NORMAL
                    if lib_ready and not comparing and not dup_busy
                    else tk.DISABLED
                )
            except tk.TclError:
                pass
        open_g = getattr(self, "btn_open_dup_group", None)
        if open_g is not None:
            can_open = bool(
                kind == "duplicates"
                and (getattr(self, "_duplicate_groups", None) or [])
                and not comparing
            )
            try:
                open_g.configure(state=tk.NORMAL if can_open else tk.DISABLED)
            except tk.TclError:
                pass
        # Leave Compare (compare.exit) and other registry inspector cmds.
        self._sync_registry_inspector_commands()

    def _sync_name_save_button(self) -> None:
        """Name this person is enabled when a nameable selection has typed text."""
        btn = getattr(self, "btn_name", None)
        if btn is None:
            return
        name_st = (getattr(self, "_verb_states", None) or {}).get("name") or {}
        name_on = bool(name_st.get("enabled"))
        typed = bool((self._name_var.get() or "").strip())
        btn.configure(state=tk.NORMAL if (name_on and typed) else tk.DISABLED)

    def _inspector_run_id(self) -> str | None:
        return self._insp_run_id or self._last_run_id

    def _inspector_after_mutation(self) -> None:
        """Refresh Canvas / Unknown after a successful Inspector verb."""
        rid = self._inspector_run_id()
        if self._nav in {"home", "library"}:
            self._show_library_or_onboard()
        elif self._nav in {"canvas", "photos", "videos"}:
            if self._nav == "photos":
                self._show_library(filter_key="photos")
            elif self._nav == "videos":
                self._show_library(filter_key="videos")
            else:
                self._show_workspace_canvas(reload=True, source_types=None)
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
            messagebox.showinfo(
                "Semblon", st.get("reason") or "Select a face or cluster to name."
            )
            return
        rid = self._inspector_run_id()
        item = st.get("item")
        name = (self._name_var.get() or "").strip()
        if not name:
            messagebox.showinfo("Semblon", "Type a name, then click Name this person.")
            return
        if not rid or item is None:
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

    def _inspector_note(self) -> None:
        """Home Inspector note — same persistence as Review (decisions.kind=note)."""
        from tkinter import simpledialog

        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError, apply_note

        rid = self._inspector_run_id()
        items = list(getattr(self, "_insp_selected", None) or [])
        item = None
        for it in items:
            kind = it.get("kind")
            if kind == "cluster" and it.get("cluster_id"):
                item = {"kind": "cluster", "cluster_id": it["cluster_id"]}
                break
            if kind in {"face", "unassigned"} and it.get("face_id"):
                item = {"kind": "face", "face_id": it["face_id"]}
                break
        if not rid or item is None:
            messagebox.showinfo(
                "Semblon", "Select a face or group to add a note."
            )
            return
        text = simpledialog.askstring("Note", "Review note:", parent=self.root)
        if not text:
            return
        try:
            apply_note(self.store, rid, item, text)
        except (ReviewError, ReviewUiError) as e:
            messagebox.showerror("Semblon", str(e))
            return
        self.status.set("Note saved.")
        self._inspector_after_mutation()

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
        from semblon.discovery_loop import image_rect_from_selection, with_discovery_prompt

        ws = getattr(self, "_canvas_ws", None)
        board = (getattr(ws, "board", None) or {}) if ws is not None else {}
        run_id = board.get("run_id") or self._last_run_id
        if selected_hit is None and ws is not None:
            selected_hit = getattr(ws, "_selected", None)

        query_rect = image_rect_from_selection(selected_hit)
        if hasattr(self, "_discovery"):
            if query_rect and media_id:
                self._discovery.set_query(media_id, query_rect)
            elif selected_hit is None:
                # Media-only selection clears a prior region query for this step.
                self._discovery.clear_query()

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
            self._set_inspector_collapsed(False)
        else:
            title = "Details"
            available = []
            preselect = False
            self._set_inspector_collapsed(True)

        evidence = list(lines)
        # Structured Inspector depth for open media (wireable fields only).
        if media_id and not selected_hit and self.store.is_file():
            try:
                from semblon.inspector_present import (
                    inspector_section_lines,
                    media_detail_record,
                )

                rec = media_detail_record(self.store, media_id)
                if rec:
                    evidence = inspector_section_lines(rec)
            except Exception:  # noqa: BLE001
                pass
        if media_id and title != "Details":
            evidence = with_discovery_prompt(evidence, has_query_rect=bool(query_rect))

        # Soft product lines from Canvas — do not re-wrap with engineering evidence.
        self._set_inspector_selection(
            run_id=run_id,
            media_id=media_id,
            available=available,
            evidence_lines=evidence,
            title=title,
            preselect_all=preselect,
        )
        self._sync_discovery_actions()

    def _build_home_landing(self) -> None:
        """Library home: one next step, then recent activity. Packs stay in Settings."""
        from semblon.home_shell import SHELL_ACTIVITY_TITLE, SHELL_HEADLINE, SHELL_SUBCOPY

        for child in self._landing.winfo_children():
            child.destroy()
        root = tk.Frame(self._landing, bg=BG_CANVAS)
        root.pack(fill=tk.BOTH, expand=True, padx=SP_24, pady=SP_20)
        self._shell_root = root

        tk.Label(
            root,
            text=SHELL_HEADLINE,
            font=DISPLAY,
            bg=BG_CANVAS,
            fg=TEXT_PRIMARY,
            wraplength=640,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        tk.Label(
            root,
            text=SHELL_SUBCOPY,
            font=BODY,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            wraplength=640,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor=tk.W, pady=(SP_8, 0))

        actions = tk.Frame(root, bg=BG_CANVAS)
        self._landing_actions = actions
        actions.pack(anchor=tk.W, pady=(SP_16, 0))
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
            "Review people",
            lambda: self._navigate("unknown"),
            kind="secondary",
            plate=BG_CANVAS,
        )
        self.btn_landing_browse = _button(
            actions,
            "Browse photos",
            lambda: self._navigate("photos"),
            kind="tertiary",
            plate=BG_CANVAS,
        )

        tk.Label(
            root,
            text=SHELL_ACTIVITY_TITLE,
            font=BODY_STRONG,
            bg=BG_CANVAS,
            fg=TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor=tk.W, pady=(SP_20, 0))
        self._shell_activity = tk.Frame(root, bg=BG_CANVAS)
        self._shell_activity.pack(anchor=tk.W, fill=tk.X, pady=(SP_8, 0))

        privacy = tk.Frame(root, bg=BG_CANVAS)
        self._landing_privacy = privacy
        privacy.pack(anchor=tk.W, pady=(SP_20, 0))
        tk.Label(
            privacy,
            text="Everything stays on this computer. Nothing is uploaded.",
            font=CAPTION,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            wraplength=640,
            justify=tk.LEFT,
            anchor="w",
        ).pack(side=tk.LEFT)

        # Kept for _refresh_landing_hint compatibility (first-run step cards unused).
        self._landing_steps = tk.Frame(root, bg=BG_CANVAS)
        self._landing_step_cards = []
        self._last_lens_result: dict | None = getattr(self, "_last_lens_result", None)
        self._refresh_landing_hint()
        self._refresh_library_shell()

    def _refresh_library_shell(self, summary: dict | None = None) -> None:
        """Recent activity on Home. Capability lists are not drawn here."""
        from semblon.home_shell import recent_activity_lines

        frame = getattr(self, "_shell_activity", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        for line in recent_activity_lines(self.store):
            tk.Label(
                frame,
                text=line,
                font=BODY,
                bg=BG_CANVAS,
                fg=TEXT_SECONDARY,
                wraplength=640,
                justify=tk.LEFT,
                anchor="w",
            ).pack(anchor=tk.W, pady=(0, SP_4))

    def _build_processing_home(self) -> None:
        """PROCESSING state — results framing while a job runs (not marketing + telemetry)."""
        if self._pane_is_ready("processing"):
            return
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
                "Getting your library ready. You can add another folder "
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

        self._mark_pane_ready("processing")

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
            btns,
            "Start naming",
            self._ack_completion_go_to_name,
            kind="primary",
            plate=BG_SURFACE,
        )
        self.btn_result_primary.pack(side=tk.LEFT, padx=(0, SP_8))
        self.btn_result_secondary = _button(
            btns,
            "Add another folder",
            self._ack_completion_go_library_then_folder,
            kind="secondary",
            plate=BG_SURFACE,
        )
        self.btn_result_secondary.pack(side=tk.LEFT)
        self.btn_result_continue = _button(
            btns, "Continue", self._resume, kind="primary", plate=BG_SURFACE
        )
        self.btn_result_start_over = _button(
            btns, "Select Different Folder", self._choose_folder, kind="secondary", plate=BG_SURFACE
        )
        self.btn_result_browse = _button(
            btns,
            "Browse library",
            self._ack_completion_go_library,
            kind="secondary",
            plate=BG_SURFACE,
        )


    def _pane_is_ready(self, key: str) -> bool:
        return key in getattr(self, "_pane_ready", set())

    def _mark_pane_ready(self, key: str) -> None:
        ready = getattr(self, "_pane_ready", None)
        if ready is None:
            self._pane_ready = set()
            ready = self._pane_ready
        ready.add(key)

    def _invalidate_panes(self) -> None:
        """Drop mounted pages so the next visit rebuilds offscreen after a theme change."""
        self._pane_ready = set()
        self._settings_pad = None

    def _hide_workspace_panes(self) -> None:
        self._canvas_ws.pack_forget()
        self._welcome.pack_forget()
        self._landing.pack_forget()
        self._processing.pack_forget()
        self._result_card.pack_forget()
        if hasattr(self, "_library_home"):
            self._library_home.pack_forget()
        if hasattr(self, "_library_chrome"):
            self._library_chrome.pack_forget()
        if hasattr(self, "_compare_pane"):
            try:
                self._compare_pane.pack_forget()
            except tk.TclError:
                pass
        if hasattr(self, "_lens"):
            self._lens.pack_forget()
        if hasattr(self, "_activity"):
            self._activity.pack_forget()
        if hasattr(self, "_settings"):
            self._settings.pack_forget()

    def _ingest_running(self) -> bool:
        engine = getattr(self, "engine", None)
        if engine is None:
            return False
        return bool(getattr(engine, "ingest_busy", False))

    def _home_state(self) -> str:
        """FIRST_RUN | PROCESSING | READY | EXPLORE — launch gate for Library."""
        busy = self._ingest_running()
        if busy:
            return "PROCESSING"
        if self._completion_kind in {"done", "cancelled"} and self._completion is not None:
            return "READY"
        summary = self._library_summary()
        files = 0 if summary is None else int(summary.get("files") or 0)
        if files > 0:
            return "EXPLORE"
        if self.store.is_file():
            return "EXPLORE"
        return "FIRST_RUN"

    def _show_library_or_onboard(self) -> None:
        """Processing while ingesting; result when unseen; Library or Stage otherwise."""
        if self._ingest_running():
            self._show_processing_home()
            return
        if self._completion_kind in {
            "done",
            "cancelled",
            "interrupted",
            "empty",
            "partial",
        } and self._completion is not None:
            self._show_result_card()
            return
        summary = self._library_summary()
        files = 0 if summary is None else int(summary.get("files") or 0)
        if getattr(self, "_stage_forced", False):
            self._show_stage()
            return
        if files <= 0:
            from semblon.home_completion import latest_unfinished_run_info

            info = latest_unfinished_run_info(self.store)
            if info is not None:
                self._apply_interrupted_run(info)
                self._show_result_card()
                return
            self._show_stage()
            return
        self._stage_forced = False
        self._show_library(filter_key=getattr(self, "_library_filter", "all") or "all")

    def _restore_home_lifecycle(self) -> None:
        """Cold launch: unfinished ingest / unseen completion / normal Library|Stage."""
        from semblon.home_completion import (
            latest_unfinished_run_info,
            load_unseen_completion,
        )

        if self._ingest_running():
            self._nav = "library"
            self._mark_nav_active("library")
            self._show_processing_home()
            return
        unfinished = latest_unfinished_run_info(self.store)
        if unfinished is not None:
            self._apply_interrupted_run(unfinished)
            self._nav = "library"
            self._mark_nav_active("library")
            self._show_result_card()
            return
        unseen = load_unseen_completion(self.store)
        if unseen is not None:
            self._completion_kind = str(unseen.get("kind") or "done")
            self._completion = dict(unseen.get("payload") or {})
            self._nav = "library"
            self._mark_nav_active("library")
            self._show_result_card()
            return
        self._navigate("library")

    def _apply_interrupted_run(self, info: dict) -> None:
        """Partial restart-during-ingest state — not Stage, not a false completion."""
        self._last_run_id = info.get("run_id")
        folder = info.get("folder")
        if folder:
            self._last_folder = Path(folder)
            self._resume_ready = True
        summary = self._library_summary() or {}
        self._completion_kind = "interrupted"
        self._completion = {
            "run_id": info.get("run_id"),
            "photos": int(summary.get("files") or 0),
            "faces": int(summary.get("faces") or 0),
            "groups": int(summary.get("unnamed_groups") or 0),
        }

    def _show_processing_home(self) -> None:
        """Pack the existing PROCESSING pane (even when indexed files == 0)."""
        self._stage_forced = False
        self._hide_workspace_panes()
        self._set_inspector_collapsed(True)
        self._processing.pack(fill=tk.BOTH, expand=True)
        self._refresh_processing_home(getattr(self, "_last_progress_event", None))
        self._refresh_footer()
        self._sync_chrome_for_route()
        self._sync_processing_cue()

    def _show_result_card(self) -> None:
        """Pack the existing completion/result card from persisted or live summary."""
        self._stage_forced = False
        self._hide_workspace_panes()
        self._set_inspector_collapsed(True)
        self._fill_result_card()
        self._result_card.pack(fill=tk.BOTH, expand=True)
        self._refresh_footer()
        self._sync_chrome_for_route()

    def _open_people_mode(self) -> None:
        """People chrome: To name when unnamed groups wait; else People."""
        summary = self._library_summary()
        waiting = 0 if summary is None else int(summary.get("unnamed_groups") or 0)
        self._navigate("unknown" if waiting > 0 else "people")

    def _ack_completion_go_to_name(self) -> None:
        self._acknowledge_completion()
        self._navigate("unknown")

    def _ack_completion_go_library(self) -> None:
        self._acknowledge_completion()
        self._show_library(filter_key=getattr(self, "_library_filter", "all") or "all")

    def _ack_completion_go_library_then_folder(self) -> None:
        self._acknowledge_completion()
        self._choose_folder()

    def _acknowledge_completion(self) -> None:
        from semblon.home_completion import acknowledge_completion

        run_id = None
        if isinstance(self._completion, dict):
            run_id = self._completion.get("run_id")
        acknowledge_completion(self.store, run_id)
        self._completion = None
        self._completion_kind = None

    def _open_home_stage(self) -> None:
        """Brand mark — return to capability Stage (intent map)."""
        self._stage_forced = True
        self._nav = "library"
        self._mark_nav_active("home")
        self._show_stage()

    def _dissolve_to_memory(self, *, filter_key: str = "all") -> None:
        """Stage dissolves into Memory Canvas — atmosphere transition, not a hard swap."""
        self._stage_forced = False
        self._library_filter = filter_key
        self._mark_nav_active("library")
        self._stage_cards = []

        def _arrive() -> None:
            try:
                from semblon.ui_tokens import BG_CANVAS

                self.root.configure(bg=BG_CANVAS)
            except Exception:  # noqa: BLE001
                pass
            self._show_library(filter_key=filter_key)

        try:
            from semblon.atmosphere_render import active_atmosphere_id, dissolve_stage

            dissolve_stage(
                self.root,
                on_done=_arrive,
                atmosphere_id=active_atmosphere_id(),
                duration_ms=250,
            )
        except Exception:  # noqa: BLE001
            _arrive()

    def _stage_explore(self) -> None:
        summary = self._library_summary()
        files = 0 if summary is None else int(summary.get("files") or 0)
        if files <= 0:
            self._set_inspector(
                "Explore",
                [
                    "Explore shows your photos and videos here.",
                    "Add a photo folder to build your local visual memory.",
                ],
            )
            return
        self._dissolve_to_memory(filter_key="all")

    def _stage_discover(self) -> None:
        summary = self._library_summary()
        files = 0 if summary is None else int(summary.get("files") or 0)
        if files <= 0:
            self._set_inspector(
                "Discover",
                [
                    "Open a photo, then select a region or find similar content.",
                    "Add a photo folder first so there is something to discover.",
                ],
            )
            return
        self._stage_forced = False
        self._navigate("lens")

    def _show_stage(self) -> None:
        """Home Stage — capability introduction with Atmosphere illumination (Model D)."""
        from semblon.atmosphere_render import StageCapabilityCard, active_atmosphere_id
        from semblon.fluid_shell import (
            STAGE_CTA,
            STAGE_DISCOVER_BODY,
            STAGE_DISCOVER_TITLE,
            STAGE_EXPLORE_BODY,
            STAGE_EXPLORE_TITLE,
            STAGE_HEADLINE,
            STAGE_PEOPLE_BODY,
            STAGE_PEOPLE_TITLE,
            STAGE_PRIVACY,
            STAGE_SUBCOPY,
        )

        self._hide_workspace_panes()
        self._set_inspector_collapsed(True)
        if self._pane_is_ready("stage"):
            self._landing.pack(fill=tk.BOTH, expand=True)
            self._refresh_footer()
            self._sync_activity_chrome()
            return
        for child in self._landing.winfo_children():
            child.destroy()
        root = tk.Frame(self._landing, bg=BG_CANVAS)
        root.pack(fill=tk.BOTH, expand=True, padx=SP_24, pady=SP_32)
        aid = active_atmosphere_id()

        tk.Label(
            root,
            text=STAGE_HEADLINE,
            font=DISPLAY,
            bg=BG_CANVAS,
            fg=TEXT_PRIMARY,
            wraplength=720,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor=tk.W)
        tk.Label(
            root,
            text=STAGE_SUBCOPY,
            font=BODY,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            wraplength=720,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor=tk.W, pady=(SP_8, 0))

        grid = tk.Frame(root, bg=BG_CANVAS)
        grid.pack(anchor=tk.W, fill=tk.BOTH, expand=True, pady=(SP_24, 0))
        self._stage_cards: list = []

        explore = StageCapabilityCard(
            grid,
            title=STAGE_EXPLORE_TITLE,
            body=STAGE_EXPLORE_BODY,
            command=self._stage_explore,
            primary=True,
            atmosphere_id=aid,
        )
        explore.widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, SP_12))
        self._stage_cards.append(explore)

        side_col = tk.Frame(grid, bg=BG_CANVAS)
        side_col.pack(side=tk.LEFT, fill=tk.Y)
        for title, body, cmd in (
            (STAGE_DISCOVER_TITLE, STAGE_DISCOVER_BODY, self._stage_discover),
            (STAGE_PEOPLE_TITLE, STAGE_PEOPLE_BODY, lambda: self._navigate("people")),
        ):
            card = StageCapabilityCard(
                side_col,
                title=title,
                body=body,
                command=cmd,
                primary=False,
                atmosphere_id=aid,
            )
            card.widget().pack(fill=tk.X, pady=(0, SP_12))
            self._stage_cards.append(card)

        actions = tk.Frame(root, bg=BG_CANVAS)
        actions.pack(anchor=tk.W, pady=(SP_16, 0))
        self.btn_landing_cta = _button(
            actions,
            STAGE_CTA,
            self._choose_folder,
            kind="primary",
            icon="folder-plus",
            plate=BG_CANVAS,
        )
        self.btn_landing_cta.pack(side=tk.LEFT)
        tk.Label(
            root,
            text=STAGE_PRIVACY,
            font=CAPTION,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            wraplength=640,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor=tk.W, pady=(SP_16, 0))
        self._mark_pane_ready("stage")
        self._landing.pack(fill=tk.BOTH, expand=True)
        self._refresh_footer()
        self._sync_activity_chrome()

    def _show_onboarding(self) -> None:
        """Compatibility alias — Model D Stage."""
        self._show_stage()

    def _build_library_chrome(self) -> None:
        """Filter chips + browse facets + density + Clear Search for Library."""
        bar = self._library_chrome
        for child in bar.winfo_children():
            child.destroy()
        shell = tk.Frame(bar, bg=BG_CANVAS)
        shell.pack(fill=tk.X, padx=SP_8, pady=(SP_8, SP_4))
        self._lib_banner = tk.Frame(shell, bg=BG_CANVAS)
        self._lib_banner.pack(anchor=tk.W, fill=tk.X)
        self._lib_banner_text = tk.StringVar(value="")
        tk.Label(
            self._lib_banner,
            textvariable=self._lib_banner_text,
            font=BODY,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            anchor="w",
        ).pack(side=tk.LEFT)
        self.btn_lib_banner_review = _button(
            self._lib_banner,
            "Start naming",
            lambda: self._navigate("unknown"),
            kind="tertiary",
            plate=BG_CANVAS,
        )
        filters = tk.Frame(shell, bg=BG_CANVAS)
        filters.pack(anchor=tk.W, pady=(SP_8, 0))
        self._lib_filter_buttons: dict[str, object] = {}
        from semblon.fluid_shell import BROWSE_FACETS, LIBRARY_FILTERS

        for key, label in LIBRARY_FILTERS:
            btn = _button(
                filters,
                label,
                lambda k=key: self._set_library_filter(k),
                kind="tertiary",
                plate=BG_CANVAS,
            )
            btn.pack(side=tk.LEFT, padx=(0, SP_8))
            self._lib_filter_buttons[key] = btn
        facets = tk.Frame(shell, bg=BG_CANVAS)
        facets.pack(anchor=tk.W, pady=(SP_4, 0))
        self._browse_facet_buttons: dict[str, object] = {}
        for key, label in BROWSE_FACETS:
            btn = _button(
                facets,
                label,
                lambda k=key: self._open_browse_facet(k),
                kind="tertiary",
                plate=BG_CANVAS,
            )
            btn.pack(side=tk.LEFT, padx=(0, SP_8))
            self._browse_facet_buttons[key] = btn
        density = tk.Frame(shell, bg=BG_CANVAS)
        density.pack(anchor=tk.W, pady=(SP_4, 0))
        self._density_buttons: dict[str, object] = {}
        for key, label in (("comfortable", "Comfortable"), ("compact", "Compact")):
            btn = _button(
                density,
                label,
                lambda k=key: self._set_grid_density(k),
                kind="secondary"
                if key == getattr(self, "_grid_density", "comfortable")
                else "tertiary",
                plate=BG_CANVAS,
            )
            btn.pack(side=tk.LEFT, padx=(0, SP_8))
            self._density_buttons[key] = btn
        self._result_count_var = tk.StringVar(value="")
        tk.Label(
            density,
            textvariable=self._result_count_var,
            font=BODY,
            bg=BG_CANVAS,
            fg=TEXT_SECONDARY,
            anchor="w",
        ).pack(side=tk.LEFT, padx=(SP_8, 0))
        self._similar_bar = tk.Frame(shell, bg=BG_CANVAS)
        self._similar_title = tk.StringVar(value="")
        tk.Label(
            self._similar_bar,
            textvariable=self._similar_title,
            font=BODY_STRONG,
            bg=BG_CANVAS,
            fg=TEXT_PRIMARY,
            anchor="w",
        ).pack(side=tk.LEFT)
        self.btn_discovery_back = _button(
            self._similar_bar,
            "Back",
            self._discovery_back,
            kind="secondary",
            plate=BG_CANVAS,
        )
        self.btn_discovery_back.pack(side=tk.LEFT, padx=(SP_12, 0))
        self.btn_bar_compare = _button(
            self._similar_bar,
            "Compare",
            self._enter_compare,
            kind="secondary",
            plate=BG_CANVAS,
        )
        self.btn_bar_compare.pack(side=tk.LEFT, padx=(SP_12, 0))
        self.btn_clear_similar = _button(
            self._similar_bar,
            "Clear Search",
            self._clear_similar_search,
            kind="secondary",
            plate=BG_CANVAS,
        )
        self.btn_clear_similar.pack(side=tk.LEFT, padx=(SP_12, 0))

    def _set_library_filter(self, key: str) -> None:
        self._library_filter = key or "all"
        try:
            save_library_filter(self._library_filter, self.store)
        except Exception:  # noqa: BLE001
            pass
        self._browse_facet = None
        self._browse_buckets = []
        self._browse_bucket_index = 0
        self._similar_media_ids = None
        if hasattr(self, "_discovery"):
            self._discovery.clear()
        if hasattr(self, "_compare"):
            self._compare.clear()
        self._result_kind = None
        self._duplicate_groups = []
        self._duplicate_group_index = 0
        self._duplicate_scan = None
        self._library_return = None
        self._exit_compare(silent=True)
        self._show_library(filter_key=self._library_filter)

    def _set_grid_density(self, density: str) -> None:
        from semblon.media_grid import DENSITIES, save_grid_density

        dens = (density or "comfortable").strip().lower()
        if dens not in DENSITIES:
            dens = "comfortable"
        self._grid_density = dens
        try:
            save_grid_density(dens, self.store)
        except Exception:  # noqa: BLE001
            pass
        try:
            if getattr(self, "_settings_density_var", None) is not None:
                self._settings_density_var.set(dens)
        except Exception:  # noqa: BLE001
            pass
        for key, btn in (getattr(self, "_density_buttons", {}) or {}).items():
            if hasattr(btn, "set_kind"):
                btn.set_kind("secondary" if key == dens else "tertiary")
        ws = getattr(self, "_canvas_ws", None)
        if ws is not None and hasattr(ws, "set_density"):
            ws.set_density(dens)
            if hasattr(ws, "_rebuild_thumbs") and not getattr(ws, "_open", False):
                ws._rebuild_thumbs()

    def _open_browse_facet(self, facet: str) -> None:
        """Timeline / Folders / Moments → bucket list → Canvas media_ids filter."""
        from semblon.library_browse import (
            bucket_lines,
            folder_buckets,
            moment_buckets,
            timeline_buckets,
        )

        key = (facet or "").strip().lower()
        self._browse_facet = key
        if key == "timeline":
            self._browse_buckets = timeline_buckets(self.store)
        elif key == "folders":
            self._browse_buckets = folder_buckets(self.store)
        elif key == "moments":
            self._browse_buckets = moment_buckets(
                self.store, run_id=getattr(self, "_last_run_id", None)
            )
        else:
            self._browse_buckets = []
        self._browse_bucket_index = 0
        for fk, btn in (getattr(self, "_browse_facet_buttons", {}) or {}).items():
            if hasattr(btn, "set_kind"):
                btn.set_kind("secondary" if fk == key else "tertiary")
        self._set_inspector(key.title() if key else "Browse", bucket_lines(self._browse_buckets, facet=key))
        self._set_inspector_collapsed(False)
        if self._browse_buckets:
            self._apply_browse_bucket(0)

    def _apply_browse_bucket(self, index: int) -> None:
        buckets = list(getattr(self, "_browse_buckets", None) or [])
        if not buckets:
            return
        idx = max(0, min(int(index), len(buckets) - 1))
        self._browse_bucket_index = idx
        bucket = buckets[idx]
        media_ids = [str(m) for m in (bucket.get("media_ids") or []) if m]
        filt = getattr(self, "_library_filter", "all") or "all"
        if media_ids:
            self._show_library(filter_key=filt, similar_media_ids=media_ids)
        label = bucket.get("label") or "Group"
        self._set_inspector(
            (self._browse_facet or "Browse").title(),
            [
                str(label),
                f"{len(media_ids)} photo{'s' if len(media_ids) != 1 else ''}",
                "",
                f"Group {idx + 1} of {len(buckets)} · ← / → to move · Esc clears filter.",
            ],
        )
        self._set_inspector_collapsed(False)

    def _show_library(
        self,
        *,
        filter_key: str = "all",
        similar_media_ids: list[str] | None = None,
    ) -> None:
        """Unified photos/videos Library surface."""
        from semblon.fluid_shell import library_source_types, people_review_banner
        from semblon.empty_states import library_has_media_lines, photos_empty
        from semblon.home_shell import enrich_summary_counts

        self._library_filter = filter_key or "all"
        self._stage_forced = False
        if similar_media_ids is not None:
            self._similar_media_ids = list(similar_media_ids)
            if hasattr(self, "_compare"):
                self._compare.set_result_ids(self._similar_media_ids)
        self._hide_workspace_panes()
        self._set_inspector_collapsed(True)

        summary = enrich_summary_counts(self.store, self._library_summary())
        waiting = 0 if summary is None else int(summary.get("unnamed_groups") or 0)
        banner = people_review_banner(waiting)
        if hasattr(self, "_lib_banner_text"):
            self._lib_banner_text.set(banner or "")
        review_btn = getattr(self, "btn_lib_banner_review", None)
        if review_btn is not None:
            try:
                review_btn.pack_forget()
            except tk.TclError:
                pass
            if banner:
                review_btn.pack(side=tk.LEFT, padx=(SP_12, 0))

        for key, btn in (getattr(self, "_lib_filter_buttons", {}) or {}).items():
            if hasattr(btn, "set_kind"):
                btn.set_kind("secondary" if key == self._library_filter else "tertiary")

        similar = getattr(self, "_similar_bar", None)
        if similar is not None:
            try:
                similar.pack_forget()
            except tk.TclError:
                pass
            if self._similar_media_ids or getattr(self, "_result_kind", None) == "duplicates":
                similar.pack(anchor=tk.W, fill=tk.X, pady=(SP_8, 0))

        self._library_chrome.pack(fill=tk.X, anchor=tk.N)
        comparing = bool(getattr(self, "_compare", None) and self._compare.active)
        if comparing:
            self._render_compare_pane()
            try:
                self._compare_pane.pack(fill=tk.BOTH, expand=True)
            except tk.TclError:
                pass
        else:
            try:
                self._compare_pane.pack_forget()
            except (tk.TclError, AttributeError):
                pass
            self._canvas_ws.pack(fill=tk.BOTH, expand=True)
        source_types = library_source_types(self._library_filter)
        show_ids = None
        if self._similar_media_ids:
            show_ids = (
                self._compare.visible_result_ids()
                if hasattr(self, "_compare")
                else list(self._similar_media_ids)
            )
        try:
            if not comparing:
                if hasattr(self._canvas_ws, "set_density"):
                    self._canvas_ws.set_density(
                        getattr(self, "_grid_density", "comfortable")
                    )
                self._canvas_ws.reload(
                    self.store,
                    self._last_run_id,
                    source_types=source_types,
                    media_ids=show_ids,
                    clear_media_ids=not bool(show_ids),
                )
                if hasattr(self._canvas_ws, "set_compare_marks") and hasattr(
                    self, "_compare"
                ):
                    self._canvas_ws.set_compare_marks(self._compare.selected_ids)
                n = len(getattr(self._canvas_ws, "_media", None) or [])
                if hasattr(self, "_result_count_var"):
                    self._result_count_var.set(
                        f"{n:,} shown" if n else "No photos in this view"
                    )
        except Exception as e:  # noqa: BLE001
            self._set_inspector("Details", [f"Library unavailable: {e}"])
            self._set_inspector_collapsed(False)
            return
        lib = format_library_lines(
            self.store,
            source_type=None
            if source_types is None
            else ("folder" if "folder" in source_types else "video"),
        )
        if not library_has_media_lines(lib) and not self._similar_media_ids:
            empty = photos_empty()
            self._set_inspector("Details", empty.as_lines())
            # Actionable control lives in header Add Folder when Library is shown.
            if not self._library_has_media():
                # No media at all — Stage owns Add Folder; keep inspector honest.
                pass
        self._refresh_footer(summary)
        self._nav = "library"
        self._mark_nav_active("library")
        self._sync_discovery_actions()

    def _apply_find_similar_result(self, summary: dict | None) -> None:
        """Show Similar results on Memory Canvas; push discovery stack for Back."""
        from semblon.discovery_loop import DiscoveryFrame, result_set_lines

        summary = summary or {}
        items = list(summary.get("items") or [])
        media_ids = [
            str(it.get("media_id"))
            for it in items
            if it.get("media_id")
        ]
        status = str(summary.get("status") or "").upper()
        lines = result_set_lines(summary)
        if status in {"UNAVAILABLE", "ERROR"}:
            self._set_inspector("Details", lines)
            self._set_inspector_collapsed(False)
            self._sync_discovery_actions()
            return
        if not media_ids:
            self._set_inspector("Details", lines)
            self._set_inspector_collapsed(False)
            self._sync_discovery_actions()
            return
        filt = getattr(self, "_library_filter", "all") or "all"
        focus = getattr(self, "_insp_media_id", None)
        if getattr(self, "_library_return", None) is None:
            self._library_return = {"filter": filt, "media_id": focus}
        if hasattr(self, "_discovery"):
            self._discovery.push(
                DiscoveryFrame(
                    filter_key=filt,
                    similar_media_ids=(
                        list(self._similar_media_ids)
                        if self._similar_media_ids
                        else None
                    ),
                    query_media_id=focus,
                    focus_media_id=focus,
                )
            )
        if hasattr(self, "_compare"):
            self._compare.clear()
            self._compare.set_result_ids(media_ids)
        self._result_kind = "similar"
        self._duplicate_groups = []
        self._duplicate_group_index = 0
        lines = list(lines) + [
            "",
            "Ctrl+click candidates (2–4), then Compare.",
            "Keep / Reject are session decisions — not identity, not delete.",
        ]
        self._show_library(filter_key=filt, similar_media_ids=media_ids)
        self._set_inspector("Details", lines)
        self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _focus_library_media(self, media_id: str | None) -> None:
        if not media_id:
            return
        ws = getattr(self, "_canvas_ws", None)
        if ws is None:
            return
        for row in getattr(ws, "_media", None) or []:
            if str(row.get("media_id")) == str(media_id):
                try:
                    ws.show_media(row)
                except Exception:  # noqa: BLE001
                    return
                return

    def _discovery_back(self) -> None:
        """Pop one discovery/compare step; stay in Memory Canvas."""
        cmp = getattr(self, "_compare", None)
        if cmp is not None and cmp.active:
            self._exit_compare()
            return
        session = getattr(self, "_discovery", None)
        frame = session.pop() if session is not None else None
        if frame is None:
            self._clear_similar_search()
            return
        filt = frame.filter_key or getattr(self, "_library_filter", "all") or "all"
        if frame.similar_media_ids:
            self._show_library(
                filter_key=filt, similar_media_ids=list(frame.similar_media_ids)
            )
        else:
            self._similar_media_ids = None
            if cmp is not None:
                cmp.clear()
            self._show_library(filter_key=filt)
        self._focus_library_media(frame.focus_media_id)
        self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _find_similar_in_workspace(self) -> None:
        """Discovery loop: use Canvas selection when present; else region window."""
        from semblon.discovery_loop import image_rect_from_selection
        from semblon.lens_release import remember_selection
        from semblon.selection import media_file

        media_id = getattr(self, "_insp_media_id", None)
        path = media_file(self.store, media_id)
        if path is None:
            self._set_inspector(
                "Details",
                [
                    "Open a photo first.",
                    "Then select something to look at.",
                    "Nothing was searched.",
                ],
            )
            self._set_inspector_collapsed(False)
            return

        rect = None
        session = getattr(self, "_discovery", None)
        if session is not None and session.query_rect and (
            not session.query_media_id or str(session.query_media_id) == str(media_id)
        ):
            rect = dict(session.query_rect)
        if rect is None:
            ws = getattr(self, "_canvas_ws", None)
            sel = getattr(ws, "_selected", None) if ws is not None else None
            rect = image_rect_from_selection(sel)
            if rect and session is not None:
                session.set_query(media_id, rect)

        if rect is None:
            self._open_region_select()
            return

        try:
            rec = remember_selection(
                self.store,
                media_id=str(media_id),
                image_path=path,
                x=int(rect["x"]),
                y=int(rect["y"]),
                w=int(rect["w"]),
                h=int(rect["h"]),
            )
        except Exception as e:  # noqa: BLE001
            self._set_inspector(
                "Details",
                [
                    "Find Similar could not run.",
                    str(e),
                    "Your library stays open.",
                ],
            )
            self._set_inspector_collapsed(False)
            return

        self._last_lens_result = rec.get("summary") or {}
        self._last_lens_rect = {
            "x": int(rect["x"]),
            "y": int(rect["y"]),
            "w": int(rect["w"]),
            "h": int(rect["h"]),
            "kept": True,
        }
        remember = getattr(self, "_remember_user_region_id", None)
        if callable(remember):
            remember(rec)
        summary = rec.get("summary") or {}
        # Prefer product lines from lens_release; fall back to result_set_lines via apply.
        try:
            self._set_inspector("Details", rec.get("lines") or ["Nothing was searched."])
            self._set_inspector_collapsed(False)
        except Exception:  # noqa: BLE001
            pass
        self._apply_find_similar_result(summary)
        sync = getattr(self, "_sync_discovery_actions", None)
        if callable(sync):
            sync()

    def _clear_similar_search(self) -> None:
        prior = getattr(self, "_library_return", None) or {}
        self._similar_media_ids = None
        self._library_return = None
        if hasattr(self, "_discovery"):
            self._discovery.clear()
        if hasattr(self, "_compare"):
            self._compare.clear()
        self._result_kind = None
        self._duplicate_groups = []
        self._duplicate_group_index = 0
        self._duplicate_scan = None
        self._exit_compare(silent=True)
        filt = prior.get("filter") or getattr(self, "_library_filter", "all") or "all"
        self._show_library(filter_key=filt)
        self._focus_library_media(prior.get("media_id"))
        self._set_inspector_collapsed(True)
        self._sync_discovery_actions()

    def _duplicate_scan_busy(self) -> bool:
        t = getattr(self, "_dup_thread", None)
        return t is not None and t.is_alive()

    def _scan_duplicates(self) -> None:
        """Integrity (A) Exact + Near scan → grouped results on Memory Canvas.

        Expensive Exact/Near work runs on a worker thread (same pattern as Live).
        Results are applied on the Tk thread via ``root.after``. JobEngine has no
        duplicates slot; backend ``want_cancel`` is wired to Home Cancel.
        """
        from semblon.discovery_loop import DiscoveryFrame

        if self._duplicate_scan_busy():
            try:
                self.status.set("Duplicate scan already running…")
            except Exception:  # noqa: BLE001
                pass
            return

        filt = getattr(self, "_library_filter", "all") or "all"
        focus = getattr(self, "_insp_media_id", None)
        if getattr(self, "_library_return", None) is None:
            self._library_return = {"filter": filt, "media_id": focus}
        if hasattr(self, "_discovery"):
            self._discovery.push(
                DiscoveryFrame(
                    filter_key=filt,
                    similar_media_ids=(
                        list(self._similar_media_ids)
                        if self._similar_media_ids
                        else None
                    ),
                    query_media_id=focus,
                    focus_media_id=focus,
                )
            )
        self._set_inspector(
            "Duplicates",
            [
                "Scanning Exact (SHA-256) and Near match (aHash/dHash)…",
                "",
                "Exact and Near are integrity similarity (A).",
                "Not Find Similar (region) and not whole-image search.",
            ],
        )
        self._set_inspector_collapsed(False)
        root = getattr(self, "root", None)
        if root is not None:
            try:
                root.update_idletasks()
            except tk.TclError:
                pass
        try:
            self.status.set("Scanning duplicates…")
        except Exception:  # noqa: BLE001
            pass

        self._dup_cancel = threading.Event()
        store = Path(self.store)

        def on_progress(done: int, total: int) -> None:
            # Real scan counts only — never invent a percentage.
            if root is None:
                return
            msg = f"Scanning duplicates… {int(done):,} of {int(total):,}"
            try:
                root.after(0, lambda m=msg: self.status.set(m))
            except Exception:  # noqa: BLE001
                pass

        def _run() -> None:
            try:
                from semblon.duplicates import find_integrity_groups

                result = find_integrity_groups(
                    store,
                    want_cancel=self._dup_cancel.is_set,
                    on_progress=on_progress,
                )
            except Exception as exc:  # noqa: BLE001 — surface on UI thread
                err = exc

                def _fail() -> None:
                    self._dup_thread = None
                    try:
                        self.status.set(friendly_exception(err))
                    except Exception:  # noqa: BLE001
                        pass
                    self._set_inspector("Duplicates", [friendly_exception(err)])
                    if hasattr(self, "_refresh_job_controls"):
                        try:
                            self._refresh_job_controls()
                        except Exception:  # noqa: BLE001
                            pass
                    if hasattr(self, "_sync_discovery_actions"):
                        try:
                            self._sync_discovery_actions()
                        except Exception:  # noqa: BLE001
                            pass

                if root is not None:
                    try:
                        root.after(0, _fail)
                        return
                    except Exception:  # noqa: BLE001
                        pass
                _fail()
                return

            def _done() -> None:
                self._dup_thread = None
                if (result or {}).get("status") == "CANCELLED":
                    try:
                        self.status.set("Duplicate scan cancelled.")
                    except Exception:  # noqa: BLE001
                        pass
                    self._set_inspector(
                        "Duplicates",
                        [
                            "Duplicate scan cancelled.",
                            "",
                            "Exact and Near are integrity similarity (A).",
                        ],
                    )
                    if hasattr(self, "_refresh_job_controls"):
                        try:
                            self._refresh_job_controls()
                        except Exception:  # noqa: BLE001
                            pass
                    if hasattr(self, "_sync_discovery_actions"):
                        try:
                            self._sync_discovery_actions()
                        except Exception:  # noqa: BLE001
                            pass
                    return
                self._apply_duplicate_result(result)
                if hasattr(self, "_refresh_job_controls"):
                    try:
                        self._refresh_job_controls()
                    except Exception:  # noqa: BLE001
                        pass

            if root is not None:
                try:
                    root.after(0, _done)
                    return
                except Exception:  # noqa: BLE001
                    pass
            _done()

        self._dup_thread = threading.Thread(
            target=_run, name="semblon-home-duplicates", daemon=True
        )
        self._dup_thread.start()
        if hasattr(self, "_refresh_job_controls"):
            try:
                self._refresh_job_controls()
            except Exception:  # noqa: BLE001 — headless Fake hosts
                pass
        if hasattr(self, "_sync_discovery_actions"):
            try:
                self._sync_discovery_actions()
            except Exception:  # noqa: BLE001
                pass

    def _apply_duplicate_result(self, result: dict | None) -> None:
        from semblon.duplicates import group_lines

        result = result or {}
        self._duplicate_scan = result
        self._result_kind = "duplicates"
        self._duplicate_groups = list(result.get("groups") or [])
        self._duplicate_group_index = 0
        if hasattr(self, "_compare"):
            self._compare.clear()
        media_ids: list[str] = []
        seen: set[str] = set()
        for g in self._duplicate_groups:
            for mid in g.get("media_ids") or []:
                if mid and mid not in seen:
                    seen.add(str(mid))
                    media_ids.append(str(mid))
        filt = getattr(self, "_library_filter", "all") or "all"
        if media_ids:
            self._show_library(filter_key=filt, similar_media_ids=media_ids)
        else:
            self._similar_media_ids = None
            self._show_library(filter_key=filt)
        lines = group_lines(result)
        if self._duplicate_groups:
            lines = lines + [
                "",
                "← / → choose group · Enter or Open Duplicate Group · then Compare.",
            ]
        self._set_inspector("Duplicates", lines)
        self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _open_selected_duplicate_group(self) -> None:
        from semblon.discovery_loop import DiscoveryFrame
        from semblon.duplicates import open_group_lines

        groups = list(getattr(self, "_duplicate_groups", None) or [])
        if not groups:
            self._set_inspector(
                "Duplicates",
                ["No duplicate groups to open.", "", "Run Find Duplicates first."],
            )
            self._set_inspector_collapsed(False)
            return
        idx = max(0, min(int(self._duplicate_group_index), len(groups) - 1))
        group = groups[idx]
        media_ids = [str(m) for m in (group.get("media_ids") or []) if m]
        filt = getattr(self, "_library_filter", "all") or "all"
        if hasattr(self, "_discovery"):
            self._discovery.push(
                DiscoveryFrame(
                    filter_key=filt,
                    similar_media_ids=(
                        list(self._similar_media_ids)
                        if self._similar_media_ids
                        else None
                    ),
                    query_media_id=getattr(self, "_insp_media_id", None),
                    focus_media_id=getattr(self, "_insp_media_id", None),
                )
            )
        self._result_kind = "duplicates"
        lines = open_group_lines(group, index=idx + 1)
        if not media_ids:
            self._set_inspector(
                "Duplicates",
                lines
                + [
                    "",
                    "None of these paths are in the library index yet.",
                    "They are exact byte duplicates on disk — not deleted.",
                ],
            )
            self._set_inspector_collapsed(False)
            self._sync_discovery_actions()
            return
        if hasattr(self, "_compare"):
            self._compare.clear()
            self._compare.set_result_ids(media_ids)
            for mid in media_ids[:4]:
                self._compare.toggle_selected(mid)
        self._show_library(filter_key=filt, similar_media_ids=media_ids)
        self._set_inspector("Duplicates", lines)
        self._set_inspector_collapsed(False)
        if len(media_ids) >= 2:
            self._enter_compare()
        else:
            self._sync_discovery_actions()

    def _move_duplicate_group(self, delta: int) -> None:
        groups = list(getattr(self, "_duplicate_groups", None) or [])
        if not groups or getattr(self, "_result_kind", None) != "duplicates":
            return
        if getattr(self, "_compare", None) and self._compare.active:
            return
        self._duplicate_group_index = max(
            0, min(self._duplicate_group_index + int(delta), len(groups) - 1)
        )
        from semblon.duplicates import open_group_lines

        g = groups[self._duplicate_group_index]
        self._set_inspector(
            "Duplicates",
            open_group_lines(g, index=self._duplicate_group_index + 1)
            + ["", "Enter opens this group for Compare."],
        )
        self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _toggle_compare_candidate(self, media_id: str) -> None:
        cmp = getattr(self, "_compare", None)
        if cmp is None or not self._similar_media_ids:
            return
        if cmp.active:
            return
        cmp.set_result_ids(list(self._similar_media_ids))
        selected = cmp.toggle_selected(media_id)
        if hasattr(self._canvas_ws, "set_compare_marks"):
            self._canvas_ws.set_compare_marks(selected)
        from semblon.culling_compare import compare_unavailable_lines

        ok, _reason = cmp.can_enter()
        if ok:
            lines = [
                f"{len(selected)} candidates selected.",
                "",
                "Compare to inspect side by side.",
                "Keep / Reject are session decisions — not identity, not delete.",
            ]
        else:
            lines = compare_unavailable_lines(
                selected_count=len(selected),
                result_count=len(cmp.visible_result_ids()),
            )
        self._set_inspector("Details", lines)
        self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _enter_compare(self) -> None:
        from semblon.culling_compare import compare_unavailable_lines

        cmp = getattr(self, "_compare", None)
        if cmp is None:
            return
        if self._similar_media_ids:
            cmp.set_result_ids(list(self._similar_media_ids))
        ok, reason = cmp.enter()
        if not ok:
            self._set_inspector(
                "Details",
                compare_unavailable_lines(
                    selected_count=len(cmp.selected_ids),
                    result_count=len(cmp.visible_result_ids()),
                ),
            )
            self._set_inspector_collapsed(False)
            self._sync_discovery_actions()
            return
        self._show_library(
            filter_key=getattr(self, "_library_filter", "all") or "all",
            similar_media_ids=list(self._similar_media_ids or cmp.result_ids),
        )
        self._set_inspector(
            "Details",
            [
                f"Comparing {len(cmp.compare_ids)} candidates.",
                "",
                "← / → move · K Keep · X Reject · Esc leave Compare",
                "Decisions are for this discovery session only.",
                "This is not a person identity decision.",
            ],
        )
        self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _exit_compare(self, *, silent: bool = False) -> None:
        cmp = getattr(self, "_compare", None)
        if cmp is not None:
            cmp.exit()
        if silent:
            try:
                self._compare_pane.pack_forget()
            except (tk.TclError, AttributeError):
                pass
            return
        ids = list(self._similar_media_ids or (cmp.visible_result_ids() if cmp else []))
        self._show_library(
            filter_key=getattr(self, "_library_filter", "all") or "all",
            similar_media_ids=ids if ids else None,
        )
        if ids:
            self._set_inspector(
                "Details",
                [
                    f"{len(cmp.visible_result_ids()) if cmp else len(ids)} similar results.",
                    "",
                    "Ctrl+click to select candidates, or open a photo to continue discovering.",
                ],
            )
            self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _compare_decide(self, decision: str) -> None:
        from semblon.culling_compare import decision_lines

        cmp = getattr(self, "_compare", None)
        if cmp is None or not cmp.active:
            return
        mid = cmp.focused_id()
        if not mid:
            return
        rec = cmp.decide(mid, decision)
        if not rec.get("ok"):
            self._set_inspector("Details", [rec.get("reason") or "Decision failed."])
            self._set_inspector_collapsed(False)
            return
        visible = list(rec.get("visible_ids") or [])
        self._similar_media_ids = list(cmp.result_ids)
        lines = decision_lines(decision, remaining=len(visible))
        if cmp.active:
            self._render_compare_pane()
            self._set_inspector("Details", lines)
            self._set_inspector_collapsed(False)
        else:
            self._show_library(
                filter_key=getattr(self, "_library_filter", "all") or "all",
                similar_media_ids=list(cmp.result_ids),
            )
            self._set_inspector("Details", lines)
            self._set_inspector_collapsed(False)
        self._sync_discovery_actions()

    def _render_compare_pane(self) -> None:
        from semblon.canvas import load_bgr, _png_photo
        from semblon.product_surface import basename_path
        from semblon.store import connect

        cmp = getattr(self, "_compare", None)
        tiles = getattr(self, "_compare_tiles", None)
        if cmp is None or tiles is None:
            return
        for child in tiles.winfo_children():
            child.destroy()
        self._compare_photos = []
        paths: dict[str, str] = {}
        try:
            con = connect(self.store)
            try:
                for mid in cmp.compare_ids:
                    row = con.execute(
                        "SELECT path FROM media WHERE media_id=?", (mid,)
                    ).fetchone()
                    if row:
                        paths[mid] = row["path"] if hasattr(row, "keys") else row[0]
            finally:
                con.close()
        except Exception:  # noqa: BLE001
            paths = {}
        focus = cmp.focused_id()
        for mid in cmp.compare_ids:
            col = tk.Frame(tiles, bg=BG_CANVAS, highlightthickness=2)
            col.configure(
                highlightbackground=ACCENT if mid == focus else BG_SUBTLE,
                highlightcolor=ACCENT if mid == focus else BG_SUBTLE,
            )
            col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=SP_4)
            path = paths.get(mid)
            img = load_bgr(path) if path else None
            if img is not None:
                try:
                    b64, _s, nw, nh = _png_photo(img, max_side=280)
                    photo = tk.PhotoImage(data=b64)
                    self._compare_photos.append(photo)
                    tk.Label(col, image=photo, bg=BG_CANVAS).pack(pady=(SP_8, SP_4))
                except Exception:  # noqa: BLE001
                    tk.Label(col, text="(preview unavailable)", bg=BG_CANVAS, fg=TEXT_SECONDARY).pack()
            else:
                tk.Label(col, text="(unreadable)", bg=BG_CANVAS, fg=TEXT_SECONDARY).pack()
            tk.Label(
                col,
                text=basename_path(path) if path else mid,
                bg=BG_CANVAS,
                fg=TEXT_PRIMARY,
                font=CAPTION,
                wraplength=200,
            ).pack()
            btns = tk.Frame(col, bg=BG_CANVAS)
            btns.pack(pady=SP_8)
            _button(
                btns,
                "Keep",
                lambda m=mid: self._compare_decide_media(m, "keep"),
                kind="secondary",
                plate=BG_CANVAS,
            ).pack(side=tk.LEFT, padx=2)
            _button(
                btns,
                "Reject",
                lambda m=mid: self._compare_decide_media(m, "reject"),
                kind="secondary",
                plate=BG_CANVAS,
            ).pack(side=tk.LEFT, padx=2)
            col.bind("<Button-1>", lambda _e, m=mid: self._compare_focus(m))

    def _compare_focus(self, media_id: str) -> None:
        cmp = getattr(self, "_compare", None)
        if cmp is None or not cmp.active or media_id not in cmp.compare_ids:
            return
        cmp.focus_index = cmp.compare_ids.index(media_id)
        self._render_compare_pane()
        self._sync_discovery_actions()

    def _compare_decide_media(self, media_id: str, decision: str) -> None:
        cmp = getattr(self, "_compare", None)
        if cmp is None or not cmp.active:
            return
        if media_id in cmp.compare_ids:
            cmp.focus_index = cmp.compare_ids.index(media_id)
        self._compare_decide(decision)

    def _on_discovery_escape(self, _event=None):
        if self._hotkey_blocked(_event):
            return None
        if getattr(self, "_compare", None) and self._compare.active:
            self._exit_compare()
            return "break"
        return None

    def _on_discovery_return(self, event=None):
        if self._hotkey_blocked(event):
            return None
        if getattr(self, "_compare", None) and self._compare.active:
            return None
        if getattr(self, "_result_kind", None) == "duplicates" and (
            getattr(self, "_duplicate_groups", None) or []
        ):
            self._open_selected_duplicate_group()
            return "break"
        return None

    def _on_compare_arrow(self, delta: int, event=None):
        if self._hotkey_blocked(event):
            return None
        cmp = getattr(self, "_compare", None)
        if cmp is not None and cmp.active:
            mid = cmp.move_focus(delta)
            if mid:
                self._render_compare_pane()
                self._sync_discovery_actions()
            return "break"
        if getattr(self, "_result_kind", None) == "duplicates":
            self._move_duplicate_group(delta)
            return "break"
        return None

    def _on_compare_hotkey(self, decision: str, event=None):
        if self._hotkey_blocked(event):
            return None
        cmp = getattr(self, "_compare", None)
        if cmp is None or not cmp.active:
            return None
        self._compare_decide(decision)
        return "break"

    def _hotkey_blocked(self, event=None) -> bool:
        w = getattr(event, "widget", None) if event is not None else None
        if w is None:
            try:
                w = self.root.focus_get()
            except tk.TclError:
                w = None
        cls = w.winfo_class() if w is not None else ""
        return cls in {"Entry", "TEntry", "Text", "TCombobox"}

    def _show_home_landing(self) -> None:
        """Compatibility: cold landing is onboarding or Library."""
        self._show_library_or_onboard()

    def _refresh_footer(self, summary: dict | None = None) -> None:
        from semblon.fluid_shell import (
            footer_library_line,
            footer_status_word,
            people_chrome_label,
        )
        from semblon.home_shell import enrich_summary_counts

        if summary is None:
            summary = enrich_summary_counts(self.store, self._library_summary())
        if hasattr(self, "_footer_counts"):
            self._footer_counts.set(footer_library_line(summary))
        if hasattr(self, "_footer_ready"):
            self._footer_ready.set(
                footer_status_word(
                    busy=bool(self.app.busy),
                    paused=bool(self.app.paused),
                )
            )
        if hasattr(self, "_library_status"):
            self._library_status.set(footer_library_line(summary))
        people_btn = getattr(self, "btn_people", None)
        if people_btn is not None and hasattr(people_btn, "configure"):
            waiting = 0
            try:
                waiting = int((summary or {}).get("unnamed_groups") or 0)
            except (TypeError, ValueError):
                waiting = 0
            try:
                people_btn.configure(text=people_chrome_label(waiting))
            except tk.TclError:
                pass

    def _build_library_home(self) -> None:
        """Retained frame for compatibility; Library chrome owns the strip now."""
        bar = self._library_home
        for child in bar.winfo_children():
            child.destroy()
        self.btn_lib_review = None
        self.btn_lib_add = None
        self._lib_home_title = tk.StringVar(value="")
        self._lib_home_thumbs = tk.Frame(bar, bg=BG_CANVAS)
        self._lib_home_thumb_images: list = []

    def _show_library_home(self, summary: dict | None = None) -> None:
        """Compatibility shim — route into the unified Library."""
        self._show_library(filter_key="photos")

    def _refresh_library_home_thumbs(self, waiting: int) -> None:
        frame = getattr(self, "_lib_home_thumbs", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        self._lib_home_thumb_images = []
        if waiting <= 0 or not self.store.is_file():
            return
        try:
            rows = _unnamed_cluster_face_paths(Path(self.store), limit=12)
        except Exception:  # noqa: BLE001
            rows = []
        if not rows:
            try:
                rows = _recent_face_paths(Path(self.store), limit=12)
            except Exception:  # noqa: BLE001
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
                    max_side=64,
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
            self._lib_home_thumb_images.append(img)
            lbl = tk.Label(frame, image=img, bg=BG_CANVAS, cursor="hand2")
            lbl.pack(side=tk.LEFT, padx=(0, SP_8))
            lbl.bind("<Button-1>", lambda _e: self._navigate("unknown"))
            if len(self._lib_home_thumb_images) >= 12:
                break

    def _refresh_processing_home(self, ev: ProgressEvent | None = None) -> None:
        """Push soft processing copy into the PROCESSING workspace."""
        from semblon.product_surface import processing_home_snapshot

        paused = bool(getattr(self, "app", None) and self.app.paused)
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
            browse.set_kind("primary" if plan["primary"] == "browse" else "tertiary")

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
                privacy.pack(anchor=tk.W, pady=(SP_20, 0))

        # Step cards were retired from the shell; keep loop safe if empty.
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
        """Footer counts + People to name badge. Hidden badge at 0."""
        summary = self._library_summary()
        self._refresh_footer(summary)
        btn = getattr(self, "_nav_buttons", {}).get("unknown")
        waiting = 0 if summary is None else int(summary.get("unnamed_groups") or 0)
        people_btn = getattr(self, "_nav_buttons", {}).get("people")
        if hasattr(self, "_to_name"):
            self._to_name.set(f"{waiting} to name" if waiting else "")
        for target in (btn, people_btn):
            if target is not None and hasattr(target, "set_badge"):
                target.set_badge(waiting)
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

    def _on_processing_cue_tick(self, color: str, brightness: float) -> None:
        """Footer + Activity control illumination while indexing / jobs run."""
        self._footer_pulse_color = color if brightness > 0 else TEXT_SECONDARY
        for lbl in (
            getattr(self, "_footer_ready_lbl", None),
            getattr(self, "_footer_local_lbl", None),
        ):
            if lbl is None:
                continue
            try:
                lbl.configure(fg=self._footer_pulse_color if brightness > 0 else TEXT_SECONDARY)
            except tk.TclError:
                pass
        act = getattr(self, "btn_activity", None)
        if act is not None and hasattr(act, "set_kind"):
            try:
                act.set_kind("secondary" if brightness > 0.45 else "tertiary")
            except Exception:  # noqa: BLE001
                pass

    def _sync_activity_chrome(self) -> None:
        """Activity is operational context — emphasize while busy, quiet when idle."""
        act = getattr(self, "btn_activity", None)
        if act is None:
            return
        busy = bool(getattr(self.app, "busy", False))
        try:
            if hasattr(act, "configure"):
                act.configure(text="Activity · scanning" if busy else "Activity")
            if hasattr(act, "set_kind"):
                act.set_kind("secondary" if busy else "tertiary")
        except Exception:  # noqa: BLE001
            pass
        # Keep reachable; pack into modes row if somehow forgotten.
        modes = getattr(self, "_modes", None)
        if modes is not None and busy:
            try:
                if not act.winfo_ismapped():
                    act.pack(in_=modes, side=tk.LEFT)
            except tk.TclError:
                pass

    def _sync_processing_cue(self) -> None:
        cue = getattr(self, "_processing_cue", None)
        if cue is None:
            self._sync_activity_chrome()
            return
        busy = bool(getattr(self.app, "busy", False))
        if busy and not cue.active:
            from semblon.atmosphere_render import active_atmosphere_id

            cue.start(active_atmosphere_id())
        elif not busy and cue.active:
            cue.stop()
        self._sync_activity_chrome()

    def _apply_saved_theme(self) -> None:
        """Publish the saved appearance before widgets are built."""
        from semblon.atmosphere_render import publish_atmosphere
        from semblon.ui_prefs import load_theme_mode, resolve_atmosphere_id

        aid = resolve_atmosphere_id(load_theme_mode(self.store))
        publish_atmosphere(aid)



    def _on_theme_band_configure(self, event) -> None:
        """Repaint the band at the real width. The fill comes from the active theme."""
        band = getattr(self, "_theme_band", None)
        if band is None or event.widget is not band:
            return
        width = int(event.width)
        if width < 2 or width == getattr(self, "_theme_band_width", 0):
            return
        self._theme_band_width = width
        from semblon.atmosphere_render import active_atmosphere_id

        self._paint_theme_gradient(active_atmosphere_id())

    def _restyle_native_surfaces(self) -> None:
        """Tk widgets keep the color they were given. Reapply the live palette."""
        from semblon.ui_theme import style_listbox

        box = getattr(self, "_sel_list", None)
        if box is not None:
            style_listbox(box)
        body = getattr(self, "_inspector_body", None)
        canvas = getattr(body, "_canvas", None) if body is not None else None
        if canvas is not None:
            try:
                canvas.configure(bg=BG_SURFACE)
            except tk.TclError:
                pass

    def _paint_theme_gradient(self, aid: str) -> None:
        from semblon.atmosphere import get_atmosphere

        spec = get_atmosphere(aid)
        backdrop = getattr(self, "_gradient", None)
        if backdrop is not None:
            backdrop.set_stops(spec.surface, spec.mist or spec.accent)
        band = getattr(self, "_theme_band", None)
        if band is not None:
            from semblon.atmosphere_render import paint_vertical_gradient

            try:
                band.configure(bg=spec.surface)
            except tk.TclError:
                pass
            self._theme_band_width = max(int(band.winfo_width()), 0)
            paint_vertical_gradient(band, spec.surface, spec.mist or spec.accent, 72)
        try:
            self._shell.configure(bg=spec.surface)
        except Exception:
            pass
        rows = getattr(self, "_theme_rows", {}) or {}
        for key, row in rows.items():
            canvas = row.get("canvas")
            if canvas is None:
                continue
            try:
                canvas.configure(highlightthickness=2 if key == aid else 1)
            except Exception:
                pass

    def _on_theme_row(self, aid: str) -> None:
        self._theme_var.set(aid)
        self._preview_theme(aid)

    def _on_theme_list(self, _event=None) -> None:
        box = getattr(self, "_theme_list", None)
        ids = getattr(self, "_theme_ids", [])
        if box is None:
            return
        sel = box.curselection()
        if not sel:
            return
        aid = ids[sel[0]]
        self._theme_var.set(aid)
        self._preview_theme(aid)

    def _preview_theme(self, mode: str) -> None:
        """Apply a theme live. Does not write appearance.json."""
        from semblon.atmosphere import ATMOSPHERE_LABELS
        from semblon.atmosphere_render import transition_to
        from semblon.ui_prefs import resolve_atmosphere_id
        from semblon.ui_theme import apply_theme, reset_theme_for_tests

        self._theme_preview = mode
        aid = resolve_atmosphere_id(mode)
        self._paint_theme_gradient(aid)
        label = ATMOSPHERE_LABELS.get(aid, aid)
        status = getattr(self, "_theme_status", None)
        if status is not None:
            status.set(f"Previewing {label}. Not saved.")

        def _finish() -> None:
            if apply_theme is not None:
                reset_theme_for_tests()
                apply_theme(self.root, force=True)
            self._restyle_chrome()

        transition_to(self.root, aid, on_done=_finish)

    def _save_theme(self) -> None:
        """Persist the previewed theme. This is the only write."""
        mode = getattr(self, "_theme_preview", None) or self._theme_var.get()
        self._set_theme_mode(mode)

    def _set_theme_mode(self, mode: str) -> None:
        from semblon.atmosphere import ATMOSPHERE_LABELS
        from semblon.atmosphere_render import transition_to
        from semblon.ui_prefs import resolve_atmosphere_id, save_theme_mode
        from semblon.ui_theme import apply_theme, reset_theme_for_tests

        kept = save_theme_mode(mode, self.store)
        self._theme_preview = kept
        self._theme_saved = kept
        aid = resolve_atmosphere_id(kept)
        self._paint_theme_gradient(aid)
        label = ATMOSPHERE_LABELS.get(aid, aid)
        status = getattr(self, "_theme_status", None)
        if status is not None:
            status.set(f"Saved {label}.")

        def _finish() -> None:
            self._invalidate_panes()
            if apply_theme is not None:
                reset_theme_for_tests()
                apply_theme(self.root, force=True)
            self._restyle_chrome()
            if self._nav != "settings":
                self._refresh_atmosphere_previews()

        transition_to(self.root, aid, on_done=_finish)

    def _refresh_atmosphere_previews(self) -> None:
        tiles = getattr(self, "_atmosphere_tiles", None) or []
        from semblon.ui_prefs import load_theme_mode, resolve_atmosphere_id

        cur = resolve_atmosphere_id(load_theme_mode(self.store))
        for tile in tiles:
            try:
                tile.set_selected(tile.atmosphere_id == cur)
            except Exception:  # noqa: BLE001
                pass

    def _restyle_chrome(self) -> None:
        """Repaint surfaces that captured colors when they were created."""
        self._restyle_native_surfaces()
        try:
            self.root.configure(bg=BG_CANVAS)
        except tk.TclError:
            pass
        for lbl in (
            getattr(self, "_footer_local_lbl", None),
            getattr(self, "_footer_counts_lbl", None),
            getattr(self, "_footer_ready_lbl", None),
        ):
            if lbl is None:
                continue
            try:
                lbl.configure(bg=BG_CANVAS, fg=TEXT_SECONDARY)
            except tk.TclError:
                pass
        # Inspector / contextual drawer — raised surface with accent edge when selected.
        insp = getattr(self, "_inspector", None)
        if insp is not None:
            try:
                insp.configure(style="Surface.TFrame")
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
        self._sync_processing_cue()

    def _fill_result_card(self) -> None:
        kind = self._completion_kind
        data = self._completion or {}
        # Reset button packing
        for b in (
            self.btn_result_primary,
            self.btn_result_secondary,
            self.btn_result_continue,
            self.btn_result_start_over,
            getattr(self, "btn_result_browse", None),
        ):
            if b is not None:
                b.pack_forget()
        photos = int(data.get("photos") or 0)
        faces = int(data.get("faces") or 0)
        groups = int(data.get("groups") or 0)
        failed = int(data.get("failed") or 0)
        show_stats = kind in {"done", "partial", "empty"} or (
            kind == "interrupted" and photos > 0
        )
        self._fill_result_stats(data if show_stats else None)
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
        if kind == "interrupted":
            self._result_headline.set("Processing was interrupted")
            if photos > 0:
                self._result_body.set(
                    f"Semblon saved {photos} photo{'s' if photos != 1 else ''} "
                    "before it stopped. You can continue or choose another folder."
                )
            else:
                self._result_body.set(
                    "Semblon was still preparing this folder when it stopped. "
                    "Continue to resume, or choose a different folder."
                )
            self.btn_result_continue.pack(side=tk.LEFT, padx=(0, SP_8), ipady=4, ipadx=8)
            self.btn_result_start_over.pack(side=tk.LEFT, ipady=2, ipadx=6)
            return
        if kind == "empty" or (kind == "done" and photos <= 0 and failed <= 0):
            self._result_headline.set("No supported photos found")
            self._result_body.set(
                "That folder did not contain photos or videos Semblon can import. "
                "Choose a different folder to try again."
            )
            self.btn_result_start_over.configure(text="Select Different Folder")
            self.btn_result_start_over.pack(side=tk.LEFT, ipady=4, ipadx=8)
            return
        if kind == "partial" or (kind == "done" and failed > 0 and photos > 0):
            self._result_headline.set("Import finished with some issues")
            self._result_body.set(
                f"Semblon imported {photos} photo{'s' if photos != 1 else ''} "
                f"({failed} could not be read)."
                + (
                    f" Found {faces} faces across {groups} groups."
                    if faces > 0
                    else " No faces were found to group."
                )
            )
            if faces > 0:
                self.btn_result_primary.pack(
                    side=tk.LEFT, padx=(0, SP_8), ipady=4, ipadx=8
                )
            if getattr(self, "btn_result_browse", None) is not None:
                self.btn_result_browse.pack(side=tk.LEFT, padx=(0, SP_8), ipady=2, ipadx=6)
            self.btn_result_secondary.pack(side=tk.LEFT, ipady=2, ipadx=6)
            return
        # Normal / zero-face success
        self._result_headline.set("Your photos are ready")
        if faces <= 0:
            self._result_body.set(
                f"Semblon checked {photos} photos but didn't find any faces to group."
                if photos
                else "Semblon finished this folder but didn't find any faces to group."
            )
            if getattr(self, "btn_result_browse", None) is not None:
                self.btn_result_browse.pack(side=tk.LEFT, padx=(0, SP_8), ipady=4, ipadx=8)
            self.btn_result_secondary.pack(side=tk.LEFT, ipady=2, ipadx=6)
        else:
            self._result_body.set(
                f"Semblon checked {photos} photos and found {faces} faces "
                f"across {groups} groups."
                if photos
                else f"Semblon found {faces} faces across {groups} groups."
            )
            self.btn_result_primary.pack(side=tk.LEFT, padx=(0, SP_8), ipady=4, ipadx=8)
            if getattr(self, "btn_result_browse", None) is not None:
                self.btn_result_browse.pack(side=tk.LEFT, padx=(0, SP_8), ipady=2, ipadx=6)
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
    def _counts_from_done_payload(payload: dict) -> dict:
        ing = payload.get("ingest") if isinstance(payload.get("ingest"), dict) else {}
        clu = payload.get("cluster") if isinstance(payload.get("cluster"), dict) else {}
        photos = int(ing.get("files") or ing.get("new_media") or payload.get("files") or 0)
        faces = int(ing.get("faces") or payload.get("faces") or 0)
        groups = int(clu.get("clusters") or payload.get("clusters") or 0)
        failed = int(ing.get("failed") or payload.get("failed") or 0)
        return {
            "photos": photos,
            "faces": faces,
            "groups": groups,
            "failed": failed,
            "run_id": payload.get("run_id"),
        }

    def _set_inspector_collapsed(self, collapsed: bool) -> None:
        """Reserve the inspector column so route changes do not jump width."""
        self._inspector_collapsed = collapsed
        self._body.columnconfigure(1, weight=0, minsize=INSPECTOR_WIDTH)
        self._body.columnconfigure(0, weight=5)
        try:
            self._inspector_frame.grid()
        except tk.TclError:
            return

    def _on_root_configure(self, event) -> None:
        if event.widget is not self.root:
            return
        # Model D: no left rail / condensed swap — compact header is always used.
        self._condensed = shell_is_condensed(int(event.width))

    def _apply_shell_width(self, width: int) -> None:
        """Compatibility no-op — Model D dropped the MAIN sidebar rail."""
        self._condensed = shell_is_condensed(int(width))

    def _mark_nav_active(self, nav_id: str) -> None:
        """One active mode: teal text on a tinted chip. Hover is not a second accent."""
        try:
            style = ttk.Style(self.root)
            style.configure(
                "NavActive.TButton",
                foreground=REVIEW_NAV_ACTIVE_FG,
                background=REVIEW_NAV_ACTIVE_BG,
            )
            style.configure("NavIdle.TButton", foreground="#C5D0DE")
        except tk.TclError:
            style = None
        for nid, btn in self._nav_buttons.items():
            try:
                if nid == nav_id:
                    btn.state(["pressed"])
                    if style is not None:
                        btn.configure(style="NavActive.TButton")
                else:
                    btn.state(["!pressed"])
                    if style is not None:
                        btn.configure(style="NavIdle.TButton")
            except tk.TclError:
                pass

    def _sync_chrome_for_route(self) -> None:
        """Header owns Add Folder except on Stage (one primary CTA); job bar demoted."""
        for w in (
            self.btn_review,
            self.btn_live,
            self.btn_canvas,
        ):
            try:
                w.pack_forget()
            except tk.TclError:
                pass
        busy = self._ingest_running()
        on_stage = False
        try:
            on_stage = bool(self._landing.winfo_ismapped()) and not busy
        except (tk.TclError, AttributeError):
            on_stage = False
        on_processing = False
        try:
            on_processing = bool(self._processing.winfo_ismapped())
        except (tk.TclError, AttributeError):
            on_processing = False
        on_result = False
        try:
            on_result = bool(self._result_card.winfo_ismapped())
        except (tk.TclError, AttributeError):
            on_result = False
        # Folder stays in the header — never pack into the job bar.
        # On Stage, the Stage CTA is the sole Add Folder action.
        try:
            self.btn_folder.pack_forget()
        except tk.TclError:
            pass
        if not on_stage and not on_processing and not on_result:
            try:
                self.btn_folder.pack(in_=self._top, side=tk.RIGHT, padx=(SP_8, 0))
            except tk.TclError:
                pass
        on_library = self._nav in {"home", "library", "photos", "videos"}
        # Naming CTAs live on result card / To name — do not pack Start naming here.
        if on_library or on_processing or on_result:
            self._jobs_frame.pack_forget()
        else:
            try:
                self._jobs_frame.pack(fill=tk.X, before=self._body)
            except tk.TclError:
                self._jobs_frame.pack(fill=tk.X)
        # Pause / Resume / Cancel must stay visible while ingest runs.
        if busy:
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
            self._prog_frame.pack_forget()
        try:
            self._rebuild_overflow_menu()
        except Exception:  # noqa: BLE001
            pass

    def _toggle_pause_resume(self) -> None:
        """Single Pause/Resume control adjacent to the progress bar."""
        if self.app.paused:
            self._resume()
            return
        if self.app.busy:
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

    def _dispatch_empty_action(self, action_id: str | None) -> None:
        from semblon.empty_states import (
            ACTION_ADD_ANOTHER_FOLDER,
            ACTION_ADD_FOLDER,
            ACTION_CLEAR_SEARCH,
            ACTION_OPEN_REVIEW,
            ACTION_REVIEW_PEOPLE,
        )

        if action_id in {ACTION_ADD_FOLDER, ACTION_ADD_ANOTHER_FOLDER}:
            self._choose_folder()
        elif action_id in {ACTION_REVIEW_PEOPLE, ACTION_OPEN_REVIEW}:
            self._navigate("unknown")
        elif action_id == ACTION_CLEAR_SEARCH:
            try:
                self.search_var.set(getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER))
            except Exception:  # noqa: BLE001
                pass
        elif action_id == "browse_photos":
            self._navigate("photos")

    def _mount_workspace_empty(self, state) -> None:
        """Real buttons for actionable empties (not plain inspector text)."""
        from semblon.empty_states import mount_empty_state

        host = getattr(self, "_welcome", None)
        if host is None:
            return
        # Keep the title label; replace coaching body with bound controls.
        children = list(host.winfo_children())
        for child in children[1:]:
            try:
                child.destroy()
            except tk.TclError:
                pass
        on_primary = None
        on_tertiary = None
        if state.primary_action and state.action_id:
            on_primary = lambda aid=state.action_id: self._dispatch_empty_action(aid)
        if state.tertiary_action and state.tertiary_action_id:
            on_tertiary = lambda aid=state.tertiary_action_id: self._dispatch_empty_action(
                aid
            )
        mount_empty_state(
            host,
            state,
            on_primary=on_primary,
            on_tertiary=on_tertiary,
            tk_mod=tk,
            ttk_mod=ttk,
        ).pack(fill=tk.BOTH, expand=True)

    def _offer_empty_action(self, state) -> None:
        """Inspector-only empties: pack a real bound CTA (never dead text)."""
        if state is None or not state.primary_action or not state.action_id:
            return
        try:
            self.btn_review.configure(
                text=state.primary_action,
                command=lambda aid=state.action_id: self._dispatch_empty_action(aid),
            )
            self._jobs_frame.pack(fill=tk.X, before=self._body)
            self.btn_review.pack(side=tk.LEFT, padx=(SP_8, 0))
        except tk.TclError:
            pass

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._refresh_job_controls()

    def _refresh_job_controls(self) -> None:
        busy = self.app.busy
        dup_busy = self._duplicate_scan_busy()
        self._busy = busy
        states = home_control_states(
            job_running=busy,
            job_paused=self.app.paused,
            resume_ready=self._resume_ready,
        )
        # Pause + Resume share one toggle widget adjacent to the progress bar.
        # Duplicate scan reuses Cancel (backend want_cancel) but not Pause —
        # duplicates.py has no pause gates.
        if busy:
            if self.app.paused:
                self.btn_pause_toggle.configure(text="Resume", state=tk.NORMAL)
            else:
                self.btn_pause_toggle.configure(text="Pause", state=tk.NORMAL)
            self.btn_cancel.configure(state=tk.NORMAL)
        else:
            if self._resume_ready:
                self.btn_pause_toggle.configure(text="Resume", state=tk.NORMAL)
            else:
                self.btn_pause_toggle.configure(text="Pause", state=tk.DISABLED)
            self.btn_cancel.configure(
                state=tk.NORMAL if dup_busy else tk.DISABLED
            )
        buttons = {
            "folder": self.btn_folder,
            "review": self.btn_review,
            "people": self.btn_people,
            "unknown": self.btn_unknown,
            "activity": self.btn_activity,
            "settings": self.btn_settings,
            "live": self.btn_live,
            "search": self.btn_search,
        }
        for key, btn in buttons.items():
            if btn is None:
                continue
            try:
                btn.configure(state=tk.NORMAL if states[key] == "normal" else tk.DISABLED)
            except tk.TclError:
                pass
        self.btn_canvas.configure(state=tk.NORMAL)
        if hasattr(self, "btn_landing_cta") and self.btn_landing_cta is not None:
            try:
                self.btn_landing_cta.configure(
                    state=tk.NORMAL if states["folder"] == "normal" else tk.DISABLED
                )
            except tk.TclError:
                pass
        if hasattr(self, "btn_proc_pause"):
            if busy:
                if self.app.paused:
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
        self._refresh_footer()
        self._sync_processing_cue()
        if self._nav in {"home", "library", "photos", "videos"} and busy:
            # Cold ingest must leave Stage/marketing for the processing pane.
            try:
                on_proc = bool(self._processing.winfo_ismapped())
            except (tk.TclError, AttributeError):
                on_proc = False
            if not on_proc:
                self._show_processing_home()

    def _request_pause(self) -> None:
        if not self.app.busy or self.app.paused:
            return
        self.app.pause_job()
        self.status.set("Paused")
        self._refresh_job_controls()
        self._refresh_processing_home(getattr(self, "_last_progress_event", None))

    def _request_cancel(self) -> None:
        if self._duplicate_scan_busy():
            self._dup_cancel.set()
            try:
                self.status.set("Cancelling duplicate scan…")
            except Exception:  # noqa: BLE001
                pass
            self._refresh_job_controls()
            if not self.app.busy:
                return
        if not self.app.busy:
            return
        self.app.cancel_job()
        self.status.set("Cancelling…")
        self._refresh_job_controls()

    def _effective_prefer_gpu(self) -> bool:
        if self._prefer_gpu_user is not None:
            return bool(self._prefer_gpu_user)
        return resolve_home_prefer_gpu()

    def _start_process(self, path: Path, *, resume: bool) -> None:
        from semblon.home_completion import clear_completion
        from semblon.product_surface import product_status_text

        self._last_folder = path
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._resume_ready = False
        self._completion = None
        self._completion_kind = None
        clear_completion(self.store)
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

        queued = make_event(STAGE_PROCESS, KIND_QUEUED, path=str(path), outcome="resumed" if resume else None)
        self.status.set(product_status_text(queued))
        self._set_busy(True)
        # Immediate transition off Stage — files may still be 0.
        if self._nav in {"home", "library", "photos", "videos"}:
            self._show_processing_home()
            self._refresh_footer()
        observers = resolve_home_observers()
        prefer_gpu = self._effective_prefer_gpu()

        def on_event(ev: ProgressEvent) -> None:
            # Worker thread: queue only — never touch Tk here.
            self._wd.note(ev)
            self._q.put(("event", ev))

        def on_done(result) -> None:
            # Worker thread: queue only — UI drain marshals into Tk.
            if result.status == "completed":
                self._q.put(("done", result.rec or {}))
            elif result.status == "cancelled":
                self._q.put(("cancelled", result.run_id or ""))
            else:
                self._q.put(("error", result.error or RuntimeError("ingest failed")))

        try:
            self.app.submit_ingest(
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

    def _on_image_open(self, media: dict, image) -> None:
        """Start understanding beside the open photo. Never on pointer movement."""
        if image is None or media is None:
            return
        run_id = self._last_run_id
        media_id = media.get("media_id")
        board = getattr(self._canvas_ws, "board", None) or {}
        from semblon.visual.persist import should_submit_visual

        if not should_submit_visual(
            busy=bool(self.app.busy),
            items=board.get("items") or [],
            media_id=media_id,
            run_id=run_id,
        ):
            return
        ws = self._canvas_ws
        view_w = int(getattr(ws, "_nw", 0) or 0) or None
        view_h = int(getattr(ws, "_nh", 0) or 0) or None
        try:
            self.app.submit_visual(
                media_id=media_id,
                run_id=run_id,
                view_w=view_w,
                view_h=view_h,
                on_event=self._on_visual_progress,
                on_done=self._on_visual_done,
            )
        except JobBusy:
            return

    def _on_visual_progress(self, event) -> None:
        if getattr(event, "kind", None) != "partial":
            return
        self._refresh_open_visual()

    def _on_visual_done(self, result) -> None:
        if getattr(result, "status", None) != "completed":
            return
        self._refresh_open_visual()

    def _refresh_open_visual(self) -> None:
        def hop() -> None:
            ws = getattr(self, "_canvas_ws", None)
            if ws is None:
                return
            try:
                ws.refresh_open_hits()
            except Exception:  # noqa: BLE001
                return

        try:
            self.root.after(0, hop)
        except Exception:  # noqa: BLE001
            return

    def _choose_folder(self) -> None:
        if self.app.busy:
            return
        folder = filedialog.askdirectory(title="Choose a folder of photos for Semblon")
        if not folder:
            return
        self._start_process(Path(folder), resume=False)

    def _resume(self) -> None:
        # Same-job unpause vs resume-after-cancel (new submit with resume=True).
        if self.app.paused:
            self.app.unpause_job()
            self.status.set("Resuming job…")
            self._refresh_job_controls()
            return
        if self.app.busy or self._last_folder is None:
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

                    paused = bool(self.app.paused)
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
                    if self._nav in {"home", "library", "photos", "videos"}:
                        self._refresh_processing_home(payload)
                elif kind == "done":
                    from semblon.home_completion import save_unseen_completion

                    self._last_run_id = payload.get("run_id")
                    out = payload.get("out")
                    self._last_review_html = Path(out) if out else None
                    self._resume_ready = False
                    self._set_busy(False)
                    counts = self._counts_from_done_payload(
                        payload if isinstance(payload, dict) else {}
                    )
                    photos = int(counts.get("photos") or 0)
                    failed = int(counts.get("failed") or 0)
                    if photos <= 0 and failed <= 0:
                        self._completion_kind = "empty"
                    elif failed > 0 and photos > 0:
                        self._completion_kind = "partial"
                    else:
                        self._completion_kind = "done"
                    self._completion = counts
                    save_unseen_completion(
                        self.store,
                        kind=self._completion_kind,
                        payload=counts,
                    )
                    self._refresh_library_chrome()
                    # §10/§11 — status stays plain; card owns messaging (no run_id / elapsed).
                    if photos > 0:
                        self.status.set(
                            f"Your photos are ready. {photos} photo{'s' if photos != 1 else ''} added."
                        )
                    else:
                        self.status.set("Import finished.")
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
                    if self._nav in {"home", "library", "photos", "videos"}:
                        self._show_result_card()
                    elif self._nav in {"canvas"}:
                        self._show_workspace_canvas(reload=True, source_types=None)
                elif kind == "cancelled":
                    from semblon.home_completion import save_unseen_completion

                    self._resume_ready = self._last_folder is not None
                    self._set_busy(False)
                    done, total = self._last_progress_files
                    self._completion = {
                        "files_processed": done,
                        "files_total": total,
                        "run_id": payload or None,
                    }
                    self._completion_kind = "cancelled"
                    save_unseen_completion(
                        self.store,
                        kind="cancelled",
                        payload=self._completion,
                    )
                    self._refresh_library_chrome()
                    self.status.set(
                        "Processing stopped. Any partial results have been retained."
                    )
                    self.clock.set("")
                    if self._nav in {"home", "library", "photos", "videos"}:
                        self._show_result_card()
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
        if self.app.busy:
            if self.app.paused:
                self.status.set("Paused")
                if self._nav in {"home", "library", "photos", "videos"}:
                    self._refresh_processing_home()
            stalled = self._wd.check()
            if stalled is not None and stalled.kind == KIND_STALLED and not self.app.paused:
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

        focus = None
        for it in getattr(self, "_insp_selected", None) or []:
            if it.get("kind") == "cluster" and it.get("cluster_id"):
                focus = it["cluster_id"]
                break
        try:
            # Toplevel on Home's root. Home keeps pumping events. No nested mainloop.
            rec = run_review_ui(
                store=self.store,
                run_id=self._last_run_id,
                parent=self.root,
                on_add_folder=self._choose_folder,
                focus_cluster_id=focus,
            )
            html_out = (rec or {}).get("review_html") if isinstance(rec, dict) else None
            if html_out:
                self._last_review_html = Path(html_out)
        except ReviewUiError as e:
            # Expected empty (no store / no runs) is handled inside run_review_ui.
            if is_expected_condition(e, has_store=self.store.is_file()):
                if not self.store.is_file():
                    self._set_inspector(
                        "People to name", to_review_empty(has_store=False).as_lines()
                    )
                else:
                    self._set_inspector(
                        "People to name",
                        to_review_empty(has_store=True, has_faces=False).as_lines(),
                    )
                return
            self._show_failure(e)

    def _list_window(self, title: str, lines: list[str]) -> None:
        """Legacy helper: route into Inspector (no floating list-only windows)."""
        self._set_inspector(title, lines)

    def _show_people(self) -> None:
        from semblon.inspector_verbs import evidence_lines_for_selection
        from semblon.search import SearchError, search_people

        if not self.store.is_file():
            empty = people_empty()
            self._mount_workspace_empty(empty)
            self._set_inspector_selection(
                run_id=None,
                media_id=None,
                available=[],
                evidence_lines=empty.as_lines(),
                title="People",
            )
            return
        try:
            rec = search_people(self.store)
        except SearchError as e:
            if is_expected_condition(e):
                empty = people_empty()
                self._mount_workspace_empty(empty)
                self._set_inspector("People", empty.as_lines())
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
            empty = people_empty()
            self._mount_workspace_empty(empty)
            self._set_inspector_selection(
                run_id=self._last_run_id,
                media_id=None,
                available=[],
                evidence_lines=empty.as_lines(),
                title="People",
            )
            return
        # Selecting a person sets Assign target; observations come from Unknown/Canvas.
        self._insp_available = []
        self._sel_list.delete(0, tk.END)
        for p in people_items:
            name = (p.get("display_name") or "").strip() or "Named person"
            label = f"{name}  ({p.get('faces', 0)} photos)"
            self._sel_list.insert(tk.END, label)
        self._people_items = people_items
        self._sel_list.bind("<<ListboxSelect>>", self._on_people_sel_change)
        evid = evidence_lines_for_selection(
            run_id=self._last_run_id,
            selected=[],
            board_lines=format_people_lines(rec),
            candidate_person=self._insp_target_person_name,
        )
        # Header already coaches; avoid duplicating the lecture.
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

        # Display label "People to name"; route id remains ``unknown``.
        title = "People to name"
        if not self.store.is_file():
            empty = to_review_empty(has_store=False)
            self._mount_workspace_empty(empty)
            self._set_inspector_selection(
                run_id=None,
                media_id=None,
                available=[],
                evidence_lines=empty.as_lines(),
                title=title,
            )
            return
        rid = latest_run_id(self.store, with_faces=True)
        if rid is None:
            empty = to_review_empty(has_store=True, has_faces=False)
            self._mount_workspace_empty(empty)
            self._set_inspector_selection(
                run_id=None,
                media_id=None,
                available=[],
                evidence_lines=empty.as_lines(),
                title=title,
            )
            return
        try:
            rec = inbox(self.store, rid)
        except InboxError as e:
            if is_expected_condition(e):
                empty = to_review_empty(has_store=True, has_faces=False)
                self._mount_workspace_empty(empty)
                self._set_inspector(title, empty.as_lines())
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
        from semblon.activity_surface import _processing_stats

        return _processing_stats(self.store, run_id)

    def _open_canvas(self) -> None:
        """First-class canvas is the Home workspace; keep Toplevel as escape hatch."""
        self._navigate("library")

    def _present_search(
        self,
        rec: dict | None,
        *,
        extra_lines: list[str] | None = None,
        text_rec: dict | None = None,
    ) -> None:
        """Render Search with shared chrome; filter Memory Canvas when media ids exist."""
        from semblon.ui_primitives import (
            build_search_presentation,
            media_ids_from_search_rec,
            search_header_lines,
        )

        primary = rec if isinstance(rec, dict) else (text_rec if isinstance(text_rec, dict) else {})
        body_lines: list[str] = []
        if extra_lines:
            body_lines.extend(extra_lines)
            body_lines.append("")
        if isinstance(rec, dict):
            body_lines.extend(format_search_lines(rec))
        if isinstance(text_rec, dict) and text_rec is not rec:
            if body_lines:
                body_lines.append("")
            body_lines.extend(format_search_lines(text_rec))
        media_ids = media_ids_from_search_rec(rec)
        if not media_ids and isinstance(text_rec, dict):
            media_ids = self._media_ids_for_text_search(text_rec)
        pres = build_search_presentation(primary, lines=body_lines, media_ids=media_ids)
        header = search_header_lines(pres)
        # Drop duplicate "Search"/"People" title rows from body when header already sets mode.
        trimmed = [ln for ln in body_lines if ln.strip() and ln.strip() != "Search"]
        lines = header + ([""] + trimmed if trimmed else [])
        self._set_inspector("Search", lines)
        self._set_inspector_collapsed(False)
        if media_ids:
            filt = getattr(self, "_library_filter", "all") or "all"
            self._show_library(filter_key=filt, similar_media_ids=media_ids)

    def _media_ids_for_text_search(self, text_rec: dict) -> list[str]:
        """Resolve OCR hit observation_ids → media_ids (presentation only)."""
        items = list(text_rec.get("items") or [])
        obs_ids = [
            str(it.get("observation_id"))
            for it in items
            if isinstance(it, dict) and it.get("observation_id")
        ]
        if not obs_ids or not self.store.is_file():
            return []
        try:
            from semblon.store import connect

            con = connect(self.store)
            try:
                qmarks = ",".join("?" for _ in obs_ids)
                rows = con.execute(
                    f"SELECT observation_id, media_id FROM observations "
                    f"WHERE observation_id IN ({qmarks})",
                    obs_ids,
                ).fetchall()
            finally:
                con.close()
        except Exception:  # noqa: BLE001
            return []
        out: list[str] = []
        seen: set[str] = set()
        for r in rows:
            mid = str(r["media_id"] or "").strip()
            if mid and mid not in seen:
                seen.add(mid)
                out.append(mid)
        return out

    def _set_search_mode(self, mode: str) -> None:
        from semblon.ui_primitives import SEARCH_MODES

        key = (mode or "people").strip().lower()
        valid = {k for k, _ in SEARCH_MODES}
        if key not in valid:
            key = "people"
        self._search_mode = key
        try:
            save_search_mode(key, self.store)
        except Exception:  # noqa: BLE001
            pass
        try:
            if getattr(self, "_settings_search_var", None) is not None:
                self._settings_search_var.set(key)
        except Exception:  # noqa: BLE001
            pass
        for k, btn in (getattr(self, "_search_mode_buttons", {}) or {}).items():
            if hasattr(btn, "set_kind"):
                btn.set_kind("secondary" if k == key else "tertiary")
        if key == "region":
            self._set_inspector(
                "Search",
                [
                    "Region search (C)",
                    "",
                    "Select a region on an open photo, then Find Similar.",
                    "Basis: Selected region — not whole-image · not integrity duplicates.",
                ],
            )
            self._set_inspector_collapsed(False)

    def _run_unified_search(self) -> None:
        """People | Text in photos | Whole image | Region — one field, mode chips."""
        mode = getattr(self, "_search_mode", "people") or "people"
        if mode == "region":
            self._set_search_mode("region")
            if hasattr(self, "_find_similar_in_workspace"):
                # Prefer existing region query; otherwise guide the user.
                if getattr(self, "_discovery", None) and self._discovery.query_rect:
                    self._find_similar_in_workspace()
                else:
                    self._set_inspector(
                        "Search",
                        [
                            "Region mode",
                            "",
                            "Open a photo, select a region, then Search or Find Similar.",
                            "Basis: Selected region (C).",
                        ],
                    )
                    self._set_inspector_collapsed(False)
            return
        if mode == "whole":
            self._search_whole_image()
            return
        if mode == "text":
            self._search_text_mode()
            return
        self._search_person()

    def _search_text_mode(self) -> None:
        from semblon.search import SearchError, search_text

        q = (self.search_var.get() or "").strip()
        ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
        if q in {ph, SEARCH_PLACEHOLDER, SEARCH_PLACEHOLDER_PHOTOS}:
            q = ""
        if not q:
            messagebox.showinfo("Semblon", "Type text that appears in a photo.")
            return
        if not self.store.is_file():
            self._set_inspector("Search", search_no_store().as_lines())
            return
        try:
            text_rec = search_text(self.store, q)
        except SearchError as e:
            if is_expected_condition(e):
                self._present_search(
                    {"kind": "text", "query": q, "count": 0, "status": "NO_RESULT"},
                    extra_lines=[str(e)],
                )
            else:
                self._show_failure(e)
            return
        self._present_search(text_rec, text_rec=text_rec)

    def _search_whole_image(self) -> None:
        from semblon.search import SearchError, search_similar_media

        if not self.store.is_file():
            self._set_inspector("Search", search_no_store().as_lines())
            return
        q = (self.search_var.get() or "").strip()
        ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
        if q in {ph, SEARCH_PLACEHOLDER, SEARCH_PLACEHOLDER_PHOTOS}:
            q = ""
        mid = q or getattr(self, "_insp_media_id", None)
        if not mid:
            self._present_search(
                {
                    "kind": "similar",
                    "query": "",
                    "count": 0,
                    "status": "UNAVAILABLE",
                    "items": [],
                },
                extra_lines=[
                    "Whole image (B)",
                    "Open a photo first, or type a media id.",
                    "Basis: Whole photo · search_similar — not Find Similar (region).",
                ],
            )
            return
        try:
            rec = search_similar_media(self.store, str(mid))
        except SearchError as e:
            self._show_failure(e)
            return
        media_ids = list(rec.get("media_ids") or [])
        self._present_search(rec)
        if media_ids:
            filt = getattr(self, "_library_filter", "all") or "all"
            self._show_library(filter_key=filt, similar_media_ids=media_ids)

    def _show_saved_regions(self) -> None:
        """WIRED browse of list_user_regions — no second storage."""
        from semblon.user_region import list_user_regions

        if not self.store.is_file():
            self._set_inspector(
                "Saved Regions",
                ["No library yet.", "", "Add a photo folder, then save regions from Discover."],
            )
            self._set_inspector_collapsed(False)
            return
        try:
            regions = list_user_regions(
                self.store, run_id=getattr(self, "_last_run_id", None)
            )
        except Exception as e:  # noqa: BLE001
            self._set_inspector("Saved Regions", [f"Could not list regions: {e}"])
            self._set_inspector_collapsed(False)
            return
        self._saved_regions = list(regions or [])
        self._saved_region_index = 0
        if not self._saved_regions:
            self._set_inspector(
                "Saved Regions",
                [
                    "No saved regions yet.",
                    "",
                    "Select a region on a photo and use Name this region.",
                    "Regions are observations — not persons.",
                ],
            )
            self._set_inspector_collapsed(False)
            return
        lines = [
            "Saved Regions",
            "",
            f"{len(self._saved_regions)} region{'s' if len(self._saved_regions) != 1 else ''}.",
            "Open filters the Memory Canvas · Find Similar uses region basis (C).",
            "",
        ]
        for i, r in enumerate(self._saved_regions[:12], start=1):
            name = r.get("named") or "(unnamed)"
            mid = r.get("media_id") or "?"
            lines.append(f"{i}. {name} · media {mid}")
        if len(self._saved_regions) > 12:
            lines.append(f"…and {len(self._saved_regions) - 12} more.")
        self._set_inspector("Saved Regions", lines)
        self._set_inspector_collapsed(False)
        # Focus first region on Canvas when it has a media_id.
        first = self._saved_regions[0]
        mid = first.get("media_id")
        if mid:
            filt = getattr(self, "_library_filter", "all") or "all"
            self._show_library(filter_key=filt, similar_media_ids=[str(mid)])
            self._focus_library_media(str(mid))

    def _on_library_context_menu(self, event) -> None:
        from semblon.context_menu import popup_context_menu

        ctx = {}
        if hasattr(self, "_inspector_context"):
            try:
                ctx = self._inspector_context()
            except Exception:  # noqa: BLE001
                ctx = {}
        popup_context_menu(self, event, context=ctx)

    def _search_person(self) -> None:
        from semblon.search import SearchError, search_people, search_person, search_text

        q = (self.search_var.get() or "").strip()
        ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
        if q in {ph, SEARCH_PLACEHOLDER, SEARCH_PLACEHOLDER_PHOTOS}:
            q = ""
        if not q:
            messagebox.showinfo("Semblon", "Type a person name or text from a photo.")
            return
        if self.app.busy:
            # State-aware: library still analysing — don't fail silently.
            self._set_inspector("Search", search_library_analysing().as_lines())
            if not self.store.is_file():
                return
            # Fall through only when a store already has named people to try.
        if not self.store.is_file():
            empty = search_no_store()
            self._set_inspector("Search", empty.as_lines())
            self._offer_empty_action(empty)
            return
        try:
            named = search_people(self.store)
        except SearchError as e:
            if is_expected_condition(e):
                empty = search_no_store()
                self._set_inspector("Search", empty.as_lines())
                self._offer_empty_action(empty)
            else:
                self._show_failure(e)
            return
        if not (named.get("items") or []):
            # Still try text/OCR over owned memory — people search is not the only door.
            extra: list[str] = []
            action_state = None
            if self.app.busy:
                extra.extend(search_library_analysing().as_lines())
            else:
                action_state = search_no_named_people()
                extra.extend(action_state.as_lines())
            try:
                text_rec = search_text(self.store, q)
            except SearchError:
                text_rec = None
            self._present_search(
                {"kind": "text", "query": q, "count": int((text_rec or {}).get("count") or 0)},
                extra_lines=extra,
                text_rec=text_rec,
            )
            if action_state is not None:
                self._offer_empty_action(action_state)
            return
        try:
            rec = search_person(self.store, q)
        except SearchError as e:
            if is_expected_condition(e):
                lines = search_no_matches(q).as_lines()
                if self.app.busy:
                    lines = search_library_analysing().as_lines() + [""] + lines
                self._present_search(
                    {"kind": "person", "query": q, "count": 0, "items": []},
                    extra_lines=lines,
                )
            else:
                self._show_failure(e)
            return
        extra_busy: list[str] | None = None
        if self.app.busy and int(rec.get("count") or 0) == 0:
            extra_busy = search_library_analysing().as_lines()
        # Broader lookup when people miss: OCR/text over owned memory (not ANN theatre).
        text_rec = None
        if int(rec.get("count") or 0) == 0:
            try:
                text_rec = search_text(self.store, q)
            except SearchError:
                text_rec = None
            if text_rec is not None and not (
                int(text_rec.get("count") or 0) > 0
                or text_rec.get("status")
                in {
                    "UNAVAILABLE",
                    "ERROR",
                    "TIMEOUT",
                    "CANCELLED",
                    "NO_RESULT",
                }
            ):
                text_rec = None
        self._present_search(rec, extra_lines=extra_busy, text_rec=text_rec)


    def _settings_card(self, parent, title: str, hint: str = ""):
        """Hairline card used by Settings. Same surface stack as review chrome."""
        card = tk.Frame(
            parent,
            bg=BG_SURFACE,
            highlightbackground=BORDER_DEFAULT,
            highlightthickness=1,
            padx=16,
            pady=14,
        )
        card.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(card, text=title, font=BODY_STRONG).pack(anchor=tk.W)
        if hint:
            ttk.Label(
                card,
                text=hint,
                font=CAPTION,
                foreground=TEXT_SECONDARY,
                wraplength=640,
            ).pack(anchor=tk.W, pady=(4, 8))
        body = ttk.Frame(card)
        body.pack(fill=tk.X)
        return body

    def _build_settings_workspace(self) -> None:
        """Settings is a first-class workspace route — not a Toplevel popup."""
        for child in self._settings.winfo_children():
            child.destroy()
        outer = ttk.Frame(self._settings)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0, bg=BG_CANVAS)
        scroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pad = ttk.Frame(canvas, padding=(SP_32, SP_24))
        pad_id = canvas.create_window((0, 0), window=pad, anchor=tk.NW)
        self._settings_canvas = canvas
        self._settings_pad = pad
        self._settings_pad_id = pad_id

        def _sync_scroll(_event=None) -> None:
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.itemconfigure(pad_id, width=canvas.winfo_width())
            except tk.TclError:
                pass

        pad.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", _sync_scroll)

        def _on_mousewheel(event) -> None:
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        self._fill_settings_body()

    def _fill_settings_body(self) -> None:
        """Rebuild Settings sections inside the workspace scroll body."""
        from semblon.product_surface import (
            SETTINGS_ADVANCED,
            SETTINGS_ADVANCED_HINT,
            SETTINGS_DIAGNOSTICS,
            SETTINGS_DIAGNOSTICS_HINT,
            SETTINGS_GPU,
            SETTINGS_GRID_DENSITY,
            SETTINGS_OPEN_DIAGNOSTICS,
            SETTINGS_RECOVERY,
            SETTINGS_RECOVERY_HINT,
            SETTINGS_RESET_BUTTON,
            SETTINGS_RESET_SAFE,
            SETTINGS_RESET_TITLE,
            SETTINGS_SEARCH_MODE,
            SETTINGS_SHORTCUTS,
            SETTINGS_TITLE,
            settings_contributions,
        )

        pad = getattr(self, "_settings_pad", None)
        canvas = getattr(self, "_settings_canvas", None)
        if pad is None:
            return
        for child in pad.winfo_children():
            child.destroy()
        # Tear down prior preview theatres so demo after() jobs stop.
        for tile in getattr(self, "_atmosphere_tiles", None) or []:
            try:
                tile.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._atmosphere_tiles = []

        if canvas is not None:
            try:
                canvas.configure(bg=BG_CANVAS)
            except tk.TclError:
                pass

        head = ttk.Frame(pad)
        head.pack(fill=tk.X, pady=(0, SP_16))
        ttk.Label(head, text=SETTINGS_TITLE, font=HERO).pack(anchor=tk.W)
        ttk.Label(
            head,
            text="Library, appearance, and recovery on this computer.",
            font=BODY,
            foreground=TEXT_SECONDARY,
        ).pack(anchor=tk.W, pady=(4, 0))

        sections = {s.id: s for s in settings_contributions()}
        library = sections["library"]
        processing = sections["processing"]
        appearance = sections["appearance"]
        about = sections["about"]

        lib = self._settings_card(pad, library.title, library.hint)
        ttk.Label(lib, text="Library location", font=BODY).pack(
            anchor=tk.W, pady=(SP_8, 0)
        )
        loc_row = ttk.Frame(lib)
        loc_row.pack(fill=tk.X, pady=(SP_8, 0))
        self._settings_lib_var = tk.StringVar(value=str(self.store))
        ttk.Label(
            loc_row,
            textvariable=self._settings_lib_var,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=420,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        _button(
            loc_row, "Change…", self._settings_change_library, kind="secondary"
        ).pack(side=tk.RIGHT)

        # Packs / advanced model tooling — after first success only (UI-EXPOSURE-MAP).
        if self._library_has_media():
            packs = self._settings_card(
                pad,
                "Packs",
                "Missing packs stay missing. They are not an empty library.",
            )
            ttk.Label(
                packs,
                text="Missing packs stay missing. They are not an empty library.",
                font=CAPTION,
                foreground=TEXT_SECONDARY,
                wraplength=640,
            ).pack(anchor=tk.W)
            from semblon.home_shell import capability_sections

            cap_rows = capability_sections(has_library_content=True)
            for row in list(cap_rows["ready"]) + list(cap_rows["tracked"]):
                state = row.get("state") or "Available"
                ttk.Label(
                    packs,
                    text=f"{row['label']} — {state}",
                    font=BODY,
                    wraplength=640,
                ).pack(anchor=tk.W, pady=(SP_4, 0))

        proc = self._settings_card(pad, processing.title, processing.hint)
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
                try:
                    save_prefer_gpu(self._prefer_gpu_user, self.store)
                except Exception:  # noqa: BLE001
                    pass

            ttk.Checkbutton(
                proc,
                text=SETTINGS_GPU,
                variable=self._gpu_var,
                command=_on_gpu,
            ).pack(anchor=tk.W)
        else:
            ttk.Label(
                proc,
                text=processing.hint,
                font=CAPTION,
                foreground=TEXT_SECONDARY,
            ).pack(anchor=tk.W)

        appear = self._settings_card(pad, appearance.title, appearance.hint)
        # Everyday defaults — same keys as library/search chrome; no second stack.
        ttk.Label(appear, text=SETTINGS_GRID_DENSITY, font=BODY).pack(
            anchor=tk.W, pady=(SP_8, 0)
        )
        dens_row = ttk.Frame(appear)
        dens_row.pack(anchor=tk.W, pady=(SP_4, 0))
        self._settings_density_var = tk.StringVar(
            value=getattr(self, "_grid_density", "comfortable") or "comfortable"
        )
        for key, label in (("comfortable", "Comfortable"), ("compact", "Compact")):
            ttk.Radiobutton(
                dens_row,
                text=label,
                value=key,
                variable=self._settings_density_var,
                command=lambda k=key: self._set_grid_density(k),
            ).pack(side=tk.LEFT, padx=(0, SP_12))

        ttk.Label(appear, text=SETTINGS_SEARCH_MODE, font=BODY).pack(
            anchor=tk.W, pady=(SP_12, 0)
        )
        from semblon.ui_primitives import SEARCH_MODES as _SEARCH_MODE_CHOICES

        mode_row = ttk.Frame(appear)
        mode_row.pack(anchor=tk.W, pady=(SP_4, 0))
        self._settings_search_var = tk.StringVar(
            value=getattr(self, "_search_mode", "people") or "people"
        )
        for key, label in _SEARCH_MODE_CHOICES:
            ttk.Radiobutton(
                mode_row,
                text=label,
                value=key,
                variable=self._settings_search_var,
                command=lambda k=key: self._set_search_mode(k),
            ).pack(side=tk.LEFT, padx=(0, SP_8))

        from semblon.atmosphere import ATMOSPHERE_IDS, ATMOSPHERE_LABELS, get_atmosphere
        from semblon.ui_prefs import load_theme_mode, resolve_atmosphere_id

        ttk.Label(appear, text="Theme", font=BODY).pack(anchor=tk.W, pady=(SP_12, 0))
        ttk.Label(
            appear,
            text="Click a theme to preview it. Save theme writes the choice.",
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=640,
        ).pack(anchor=tk.W, pady=(SP_4, SP_8))
        current_mode = resolve_atmosphere_id(load_theme_mode(self.store))
        self._theme_var = tk.StringVar(value=current_mode)
        self._theme_preview = current_mode
        self._theme_saved = current_mode
        from semblon.atmosphere_render import paint_vertical_gradient

        self._theme_ids = [aid for aid in ATMOSPHERE_IDS if aid in ATMOSPHERE_LABELS]
        self._theme_rows = {}
        list_host = tk.Frame(appear, bg=BG_CANVAS)
        list_host.pack(fill=tk.X, pady=(0, SP_8))
        for aid in self._theme_ids:
            spec = get_atmosphere(aid)
            row = tk.Frame(list_host, bg=BG_CANVAS)
            row.pack(fill=tk.X, pady=3)
            swatch = tk.Canvas(
                row,
                width=72,
                height=32,
                highlightthickness=2 if aid == current_mode else 1,
                highlightbackground=(
                    REVIEW_NAV_ACTIVE_FG if aid == current_mode else BORDER_DEFAULT
                ),
                bd=0,
            )
            swatch.pack(side=tk.LEFT, padx=(0, 10))
            swatch.bind("<Configure>", lambda e, c=swatch, a=spec.surface, b=spec.accent: paint_vertical_gradient(c, a, b, e.height))
            paint_vertical_gradient(swatch, spec.surface, spec.accent, 32)
            name = tk.Label(
                row,
                text=spec.label,
                font=BODY,
                bg=BG_CANVAS,
                fg=TEXT_PRIMARY,
                anchor="w",
            )
            name.pack(side=tk.LEFT, fill=tk.X, expand=True)
            for widget in (row, swatch, name):
                widget.bind("<Button-1>", lambda _e, a=aid: self._on_theme_row(a))
            self._theme_rows[aid] = {"canvas": swatch, "row": row}
        self._theme_status = tk.StringVar(value="Saved theme.")
        ttk.Label(
            appear,
            textvariable=self._theme_status,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
        ).pack(anchor=tk.W)
        _button(appear, "Save theme", self._save_theme, kind="primary").pack(
            anchor=tk.W, pady=(SP_8, 0)
        )
        self._atmosphere_tiles = []

        about_card = self._settings_card(pad, about.title, about.hint)
        try:
            from semblon import __version__ as _ver
        except Exception:  # noqa: BLE001
            _ver = "1.4.0"
        ttk.Label(about_card, text="Semblon", font=H2).pack(anchor=tk.W)
        ttk.Label(
            about_card, text=f"Version {_ver}", font=CAPTION, foreground=TEXT_SECONDARY
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        ttk.Label(
            about_card,
            text=about.hint,
            font=BODY,
            wraplength=640,
        ).pack(anchor=tk.W, pady=(SP_8, 0))

        advanced = self._settings_card(pad, SETTINGS_ADVANCED, SETTINGS_ADVANCED_HINT)
        for shortcut, keys in SETTINGS_SHORTCUTS:
            row = ttk.Frame(advanced)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=shortcut, font=BODY).pack(side=tk.LEFT)
            ttk.Label(
                row, text=keys, font=META, foreground=TEXT_SECONDARY
            ).pack(side=tk.RIGHT)
        recovery = self._settings_card(pad, SETTINGS_RECOVERY, SETTINGS_RECOVERY_HINT)
        ttk.Label(
            recovery,
            text=SETTINGS_RESET_TITLE,
            font=BODY,
        ).pack(anchor=tk.W, pady=(SP_8, 0))
        ttk.Label(
            recovery,
            text=SETTINGS_RESET_SAFE,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=640,
        ).pack(anchor=tk.W, pady=(SP_4, 0))
        _button(
            recovery,
            SETTINGS_RESET_BUTTON,
            self._reset_app_to_defaults,
            kind="secondary",
        ).pack(anchor=tk.W, pady=(SP_8, 0))

        diag = self._settings_card(pad, SETTINGS_DIAGNOSTICS, SETTINGS_DIAGNOSTICS_HINT)
        _button(
            diag,
            SETTINGS_OPEN_DIAGNOSTICS,
            self._open_advanced_diagnostics,
            kind="tertiary",
        ).pack(anchor=tk.W, pady=(SP_8, 0))

    def _show_settings(self) -> None:
        """Product Settings workspace. Runtime/provider/model/schema/job live in Diagnostics."""
        self._hide_workspace_panes()
        self._set_inspector_collapsed(True)
        if not getattr(self, "_settings_pad", None):
            self._build_settings_workspace()
        self._settings.pack(fill=tk.BOTH, expand=True)
        self._set_inspector(
            "Settings",
            [
                "Appearance, library, and processing live here.",
                "Diagnostics stay under Settings when you need them.",
            ],
        )

    def _reset_app_to_defaults(self) -> None:
        """Confirm, then clear Semblon-owned rebuildable state via app_reset."""
        from semblon.app_reset import reset_app_to_defaults
        from semblon.product_surface import SETTINGS_RESET_CONFIRM

        if self.app.busy:
            messagebox.showinfo(
                "Semblon",
                "Finish or cancel processing before resetting the app.",
            )
            return
        if not messagebox.askyesno(
            "Reset app",
            SETTINGS_RESET_CONFIRM,
            parent=self.root,
        ):
            return
        result = reset_app_to_defaults(self.store)
        if not result.ok:
            messagebox.showerror("Semblon", result.message, parent=self.root)
            self.status.set("Reset failed.")
            return
        # In-session chrome back to defaults (prefs file already removed).
        self._prefer_gpu_user = None
        self._grid_density = "comfortable"
        self._search_mode = "people"
        self._library_filter = "all"
        self._browse_facet = None
        try:
            if hasattr(self, "_compare") and self._compare is not None:
                self._compare.clear()
        except Exception:  # noqa: BLE001
            pass
        try:
            for k, btn in (getattr(self, "_search_mode_buttons", {}) or {}).items():
                if hasattr(btn, "set_kind"):
                    btn.set_kind("secondary" if k == "people" else "tertiary")
        except Exception:  # noqa: BLE001
            pass
        try:
            from semblon.atmosphere_render import transition_to
            from semblon.ui_prefs import load_theme_mode, resolve_atmosphere_id
            from semblon.ui_theme import apply_theme, reset_theme_for_tests

            aid = resolve_atmosphere_id(load_theme_mode(self.store))
            def _finish() -> None:
                if apply_theme is not None:
                    reset_theme_for_tests()
                    apply_theme(self.root, force=True)
                self._restyle_chrome()
            transition_to(self.root, aid, on_done=_finish)
        except Exception:  # noqa: BLE001
            pass
        try:
            ws = getattr(self, "_canvas_ws", None)
            if ws is not None and hasattr(ws, "set_density"):
                ws.set_density(self._grid_density)
        except Exception:  # noqa: BLE001
            pass
        self._fill_settings_body()
        self.status.set("Reset to defaults.")
        messagebox.showinfo("Semblon", result.message, parent=self.root)
        if result.restart_required:
            messagebox.showinfo(
                "Semblon",
                "Restart Semblon to finish applying the reset.",
                parent=self.root,
            )

    def _settings_change_library(self) -> None:
        """Pick an existing store.sqlite — presentation path only; no ingest change."""
        if self.app.busy:
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
        try:
            save_last_store(self.store)
        except Exception:  # noqa: BLE001
            pass
        from semblon.application import Application

        self.app = Application(self.store)
        self.engine = self.app.engine
        # Reload library-scoped presentation prefs for the new store.
        try:
            self._prefer_gpu_user = load_prefer_gpu(self.store)
            self._library_filter = load_library_filter(self.store)
            self._search_mode = load_search_mode(self.store)
            from semblon.ui_prefs import load_grid_density as _load_dens

            self._grid_density = _load_dens(self.store)
        except Exception:  # noqa: BLE001
            pass
        if hasattr(self, "_settings_lib_var"):
            self._settings_lib_var.set(str(self.store))
        try:
            self._fill_settings_body()
        except Exception:  # noqa: BLE001
            pass

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
        if self.app.busy:
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
        self.status.set("Live overlay finished.")

    def _persist_window_geometry(self) -> None:
        try:
            geom = self.root.winfo_geometry()
            save_window_geometry(geom)
        except Exception:  # noqa: BLE001
            pass

    def _on_close(self) -> None:
        if self.app.busy:
            if messagebox.askyesno(
                "Semblon",
                "Processing is still running. Cancel and exit?",
            ):
                self._exit_after_cancel = True
                self._request_cancel()
            return
        self._persist_window_geometry()
        try:
            save_last_store(self.store)
        except Exception:  # noqa: BLE001
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_home_ui(store: Path | None = None) -> int:
    HomeApp(store=store).run()
    return 0
