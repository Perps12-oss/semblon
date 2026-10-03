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
except (ModuleNotFoundError, ImportError):  # pragma: no cover - host without libtk
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
        BORDER_SUBTLE,
        CAPTION,
        DISPLAY,
        META,
        MONO,
        H1,
        H2,
        H3,
        INK_SECONDARY,
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
    BORDER_SUBTLE = "#E4E4E2"
    CAPTION = ("Segoe UI", 10)
    DISPLAY = ("Segoe UI", 22, "bold")
    H1 = ("Segoe UI", 15, "bold")
    H2 = ("Segoe UI", 15, "bold")
    H3 = ("Segoe UI", 12)
    INK_SECONDARY = "#565656"
    INK_TERTIARY = "#8A8A8A"
    META = ("Segoe UI", 11)
    MONO = ("Cascadia Code", 11)
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

# Job control, not an application lock. These stay usable while ingest runs.
# review.html / Canvas are not product chrome keys (secondary / export only).
HOME_CONTROLS_ALWAYS_ON = (
    "review",
    "people",
    "unknown",
    "activity",
    "settings",
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
        self.store = Path(store) if store is not None else default_store_path()
        self.engine = JobEngine(self.store)
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
        self._prefer_gpu_user: bool | None = None  # Settings toggle; None = product default
        self._completion: dict | None = None  # last done/cancelled summary for §11 card
        self._completion_kind: str | None = None  # "done" | "cancelled" | None
        self._last_progress_files: tuple[int | None, int | None] = (None, None)
        self._last_faces_found: int | None = None
        self._proc_thumbs_faces: int | None = None
        self._inspector_collapsed = False
        self._last_progress_event: ProgressEvent | None = None
        self._library_filter = "all"
        self._similar_media_ids: list[str] | None = None
        self._library_return: dict | None = None
        from semblon.discovery_loop import DiscoverySession

        self._discovery = DiscoverySession()
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

        # Model D — full-bleed main; compact header chrome (no MAIN sidebar).
        self._shell = tk.Frame(self.root, bg=BG_CANVAS)
        self._shell.pack(fill=tk.BOTH, expand=True)
        self._main = ttk.Frame(self._shell)
        self._main.pack(fill=tk.BOTH, expand=True)
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
        self._search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=28)
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
            search_row, "Search", self._search_person, kind="tertiary", icon="search"
        )
        self._search_entry.bind("<Return>", lambda _e: self._search_person())
        self.root.bind("<Control-f>", lambda _e: self._search_entry.focus_set())
        self.root.bind("<Control-k>", self._open_command_palette)
        self.root.bind("<Control-Key-0>", lambda _e: self._open_home_stage())
        self.root.bind("<Control-Key-4>", lambda _e: self._navigate("lens"))
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
            modes, "People", lambda: self._navigate("people"), kind="tertiary"
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
        self.btn_review = _button(jobs, "Open Review", self._open_review_ui, kind="secondary")
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
        self._canvas_ws = CanvasWorkspace(
            work,
            store=None,
            run_id=None,
            on_select=self._on_canvas_select,
            show_chrome=True,
            on_image_open=self._on_image_open,
            job_engine=self.engine,
        )

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

        # Primary: type a name and save it. Add-to-person is for an existing person.
        name_row = ttk.Frame(actions)
        name_row.pack(fill=tk.X, pady=1)
        ttk.Label(name_row, text=VERB_LABEL_NAME).pack(side=tk.LEFT)
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(name_row, textvariable=self._name_var)
        self._name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
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
                actions,
                label,
                lambda c=cmd, k=key: self._run_inspector_verb(k, c),
                kind=_verb_kind.get(key, "secondary"),
            )
            btn.pack(fill=tk.X, pady=1)
            setattr(self, f"btn_{key}", btn)
            self._verb_buttons[key] = btn
        self.btn_region = _button(
            actions, "Select a region", self._open_region_select, kind="secondary"
        )
        self.btn_region.pack(fill=tk.X, pady=1)
        self.btn_find_similar = _button(
            actions, "Find Similar", self._find_similar_in_workspace, kind="secondary"
        )
        self.btn_find_similar.pack(fill=tk.X, pady=1)
        self.btn_ask_lens = _button(
            actions, "Ask about this photo", self._ask_with_lens, kind="secondary", icon="lens"
        )
        self.btn_ask_lens.pack(fill=tk.X, pady=1)
        # Registry contextual commands (person.history, identify, …) — same widgets
        # pattern; labels/enablement come from GuiCommand metadata.
        self._registry_cmd_buttons: dict[str, object] = {}
        _verb_ids = {spec[1] for spec in INSPECTOR_VERB_SPECS}
        for cmd in self._registry.commands(surface="inspector"):
            if cmd.id in _verb_ids or cmd.id in {
                "lens.select_region",
                "lens.ask",
                "lens.find_similar",
            }:
                # Verbs packed from INSPECTOR_VERB_SPECS. Region / Find Similar / Ask above.
                continue
            btn = _button(
                actions,
                cmd.label,
                lambda c=cmd: self._run_registry_command(c),
                kind="secondary",
            )
            btn.pack(fill=tk.X, pady=1)
            self._registry_cmd_buttons[cmd.id] = btn
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
        self._navigate("library")

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
        self._inspector.delete(0, tk.END)
        for line in lines:
            self._inspector.insert(tk.END, line)
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
        """Start region select — embedded in Lens pane when on that route."""
        from semblon.selection import lens_result_summary, media_file, mount_region_select

        path = media_file(self.store, getattr(self, "_insp_media_id", None))
        if path is None:
            self._set_inspector(
                "Lens",
                [
                    "Open a photo first.",
                    "Then select something to look at. Semblon uses available understanding.",
                    "Nothing was searched.",
                ],
            )
            if getattr(self, "_nav", None) == "lens":
                self._refresh_lens_workspace()
            return

        def done(lines: list[str]) -> None:
            try:
                self._set_inspector("Lens", lines or ["Nothing was searched."])
            except Exception:  # noqa: BLE001 — never crash Home on Lens result paint
                pass
            if hasattr(self, "_refresh_lens_workspace"):
                try:
                    self._refresh_lens_workspace()
                except Exception:  # noqa: BLE001
                    pass

        def on_report(report) -> None:
            self._last_lens_result = lens_result_summary(report)
            if hasattr(self, "_refresh_library_shell"):
                try:
                    self._refresh_library_shell()
                except Exception:  # noqa: BLE001
                    pass

        def on_busy(flag: bool) -> None:
            self._lens_busy = bool(flag)
            if hasattr(self, "_lens_status"):
                from semblon.selection import LENS_BUSY

                try:
                    self._lens_status.set(LENS_BUSY if flag else "")
                except Exception:  # noqa: BLE001
                    pass
            self._set_lens_processing(flag)

        schedule = lambda fn: self.root.after(0, fn)  # noqa: E731

        # Prefer the Lens workspace stage when that route is active.
        if getattr(self, "_nav", None) == "lens" and hasattr(self, "_lens_stage"):
            for child in self._lens_stage.winfo_children():
                child.destroy()
            mounted = mount_region_select(
                self._lens_stage,
                path,
                on_lines=done,
                on_report=on_report,
                on_busy=on_busy,
                schedule=schedule,
            )
            if mounted is not None:
                mounted.pack(fill=tk.BOTH, expand=True)
            return

        from semblon.selection import open_region_window

        open_region_window(
            self.root,
            path,
            done,
            on_report=on_report,
            on_busy=on_busy,
            schedule=schedule,
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
        """Photos/Videos → Lens with the current asset (clear product path)."""
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
        """Query the full image with available understanding (backend decides)."""
        from semblon.selection import (
            LENS_BUSY,
            lens_result_summary,
            media_file,
            run_lens_query,
        )

        path = media_file(self.store, getattr(self, "_insp_media_id", None))
        if path is None:
            self._set_inspector(
                "Lens",
                [
                    "Open a photo first.",
                    "Then ask about it. Nothing was searched.",
                ],
            )
            return

        def done(lines: list[str]) -> None:
            try:
                self._set_inspector("Lens", lines or ["Nothing was searched."])
            except Exception:  # noqa: BLE001
                pass
            self._refresh_lens_workspace()

        def on_report(report) -> None:
            self._last_lens_result = lens_result_summary(report)
            if hasattr(self, "_refresh_library_shell"):
                try:
                    self._refresh_library_shell()
                except Exception:  # noqa: BLE001
                    pass

        def on_busy(flag: bool) -> None:
            self._lens_busy = bool(flag)
            try:
                self._lens_status.set(LENS_BUSY if flag else "")
                state = tk.DISABLED if flag else tk.NORMAL
                self.btn_lens_region.configure(state=state)
                self.btn_lens_whole.configure(state=state)
            except Exception:  # noqa: BLE001
                pass
            self._set_lens_processing(flag)

        def on_error(exc: BaseException) -> None:
            try:
                show_failure_dialog(self.root, exc, tk_mod=tk, ttk_mod=ttk)
            except Exception:  # noqa: BLE001
                messagebox.showerror("Semblon", "Semblon could not finish looking.")
            self._set_inspector(
                "Lens",
                ["Semblon could not finish looking.", "Nothing was searched."],
            )
            self._refresh_lens_workspace()

        run_lens_query(
            path,
            schedule=lambda fn: self.root.after(0, fn),
            on_lines=done,
            on_report=on_report,
            on_busy=on_busy,
            on_error=on_error,
        )

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

    def _show_lens_workspace(self) -> None:
        self._hide_workspace_panes()
        self._set_inspector_collapsed(False)
        self._lens.pack(fill=tk.BOTH, expand=True)
        self._refresh_lens_workspace()

    def _rebuild_overflow_menu(self) -> None:
        """More menu from registry overflow commands (deduped labels)."""
        self._overflow_menu = tk.Menu(self._overflow, tearoff=0)
        seen: set[str] = set()
        for cmd in self._registry.commands(surface="overflow"):
            if cmd.label in seen:
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
                    f"{n} faces in this group — Open Review to compare all."
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
        self._sync_name_save_button()
        self._verb_reason.set(" · ".join(reasons[:3]) if reasons else "")
        self._sync_discovery_actions()
        self._sync_registry_inspector_commands()

    def _sync_discovery_actions(self) -> None:
        """Enable Select a region / Find Similar when a photo is open in Memory Canvas."""
        from semblon.selection import media_file

        has_media = media_file(self.store, getattr(self, "_insp_media_id", None)) is not None
        for attr in ("btn_region", "btn_find_similar"):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.configure(state=tk.NORMAL if has_media else tk.DISABLED)
            except tk.TclError:
                pass
        back = getattr(self, "btn_discovery_back", None)
        if back is not None:
            hist = bool(getattr(self, "_discovery", None) and self._discovery.has_history())
            try:
                back.configure(state=tk.NORMAL if hist else tk.DISABLED)
            except tk.TclError:
                pass

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
        if hasattr(self, "_library_home"):
            self._library_home.pack_forget()
        if hasattr(self, "_library_chrome"):
            self._library_chrome.pack_forget()
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
        """Memory Canvas when media exists; Home Stage when empty (or Stage forced)."""
        summary = self._library_summary()
        files = 0 if summary is None else int(summary.get("files") or 0)
        if getattr(self, "_stage_forced", False) or (
            files <= 0 and not self._ingest_running()
        ):
            self._show_stage()
            return
        self._stage_forced = False
        self._show_library(filter_key=getattr(self, "_library_filter", "all") or "all")

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
        self._landing.pack(fill=tk.BOTH, expand=True)
        self._refresh_footer()
        self._sync_activity_chrome()

    def _show_onboarding(self) -> None:
        """Compatibility alias — Model D Stage."""
        self._show_stage()

    def _build_library_chrome(self) -> None:
        """Filter chips + optional review banner + Clear Search for Library."""
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
            "Review People",
            lambda: self._navigate("unknown"),
            kind="tertiary",
            plate=BG_CANVAS,
        )
        filters = tk.Frame(shell, bg=BG_CANVAS)
        filters.pack(anchor=tk.W, pady=(SP_8, 0))
        self._lib_filter_buttons: dict[str, object] = {}
        from semblon.fluid_shell import LIBRARY_FILTERS

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
        self._similar_media_ids = None
        if hasattr(self, "_discovery"):
            self._discovery.clear()
        self._library_return = None
        self._show_library(filter_key=self._library_filter)

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
            if self._similar_media_ids:
                self._similar_title.set("Similar to selected region")
                similar.pack(anchor=tk.W, fill=tk.X, pady=(SP_8, 0))

        self._library_chrome.pack(fill=tk.X, anchor=tk.N)
        self._canvas_ws.pack(fill=tk.BOTH, expand=True)
        source_types = library_source_types(self._library_filter)
        try:
            self._canvas_ws.reload(
                self.store,
                self._last_run_id,
                source_types=source_types,
                media_ids=self._similar_media_ids,
                clear_media_ids=not bool(self._similar_media_ids),
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
            self._set_inspector("Details", photos_empty().as_lines())
        self._refresh_footer(summary)
        self._nav = "library"
        self._mark_nav_active("library")

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
        """Pop one discovery step; stay in Memory Canvas."""
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
            # Honest fallback: draw a region (still lands results on Memory Canvas).
            from semblon.lens_home import open_region_select

            open_region_select(self)
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
        summary = rec.get("summary") or {}
        # Prefer product lines from lens_release; fall back to result_set_lines via apply.
        try:
            self._set_inspector("Details", rec.get("lines") or ["Nothing was searched."])
            self._set_inspector_collapsed(False)
        except Exception:  # noqa: BLE001
            pass
        self._apply_find_similar_result(summary)

    def _clear_similar_search(self) -> None:
        prior = getattr(self, "_library_return", None) or {}
        self._similar_media_ids = None
        self._library_return = None
        if hasattr(self, "_discovery"):
            self._discovery.clear()
        filt = prior.get("filter") or getattr(self, "_library_filter", "all") or "all"
        self._show_library(filter_key=filt)
        self._focus_library_media(prior.get("media_id"))
        self._set_inspector_collapsed(True)
        self._sync_discovery_actions()

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
                    busy=bool(self.engine.busy),
                    paused=bool(self.engine.paused),
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
        busy = bool(getattr(self.engine, "busy", False))
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
        busy = bool(getattr(self.engine, "busy", False))
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

    def _set_theme_mode(self, mode: str) -> None:
        from semblon.atmosphere_render import transition_to
        from semblon.ui_prefs import resolve_atmosphere_id, save_theme_mode
        from semblon.ui_theme import apply_theme, reset_theme_for_tests

        kept = save_theme_mode(mode, self.store)
        aid = resolve_atmosphere_id(kept)

        def _finish() -> None:
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
        """Hide Details when nothing to inspect; ~320px when open."""
        self._inspector_collapsed = collapsed
        if collapsed:
            self._inspector_frame.grid_remove()
            self._body.columnconfigure(1, weight=0, minsize=0)
            self._body.columnconfigure(0, weight=5)
        else:
            self._inspector_frame.grid()
            self._body.columnconfigure(1, weight=0, minsize=320)
            self._body.columnconfigure(0, weight=5)

    def _on_root_configure(self, event) -> None:
        if event.widget is not self.root:
            return
        # Model D: no left rail / condensed swap — compact header is always used.
        self._condensed = shell_is_condensed(int(event.width))

    def _apply_shell_width(self, width: int) -> None:
        """Compatibility no-op — Model D dropped the MAIN sidebar rail."""
        self._condensed = shell_is_condensed(int(width))

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
        """Header owns Add Folder; job bar only for Review/More when useful."""
        for w in (
            self.btn_review,
            self.btn_live,
            self.btn_canvas,
        ):
            try:
                w.pack_forget()
            except tk.TclError:
                pass
        # Folder stays in the header — never pack into the job bar.
        try:
            self.btn_folder.pack_forget()
        except tk.TclError:
            pass
        try:
            self.btn_folder.pack(in_=self._top, side=tk.RIGHT, padx=(SP_8, 0))
        except tk.TclError:
            pass
        busy = self._ingest_running()
        on_library = self._nav in {"home", "library", "photos", "videos"}
        processing_home = on_library and busy
        if on_library:
            self._jobs_frame.pack_forget()
            if self._completion_kind == "done" and not busy:
                self._jobs_frame.pack(fill=tk.X, before=self._body)
                self.btn_review.pack(side=tk.LEFT, padx=(SP_8, 0))
        else:
            try:
                self._jobs_frame.pack(fill=tk.X, before=self._body)
            except tk.TclError:
                self._jobs_frame.pack(fill=tk.X)
            if self._nav not in {"lens", "activity", "settings"}:
                self.btn_review.pack(side=tk.LEFT, padx=(SP_8, 0))
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
            if on_library or not busy:
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
        self._refresh_footer()
        self._sync_processing_cue()
        if self._nav in {"home", "library", "photos", "videos"} and busy:
            # Stay on Library; footer shows Scanning — do not force old dashboard.
            try:
                mapped = bool(self._canvas_ws.winfo_ismapped()) or bool(
                    self._landing.winfo_ismapped()
                )
            except (tk.TclError, AttributeError):
                mapped = False
            if not mapped:
                self._show_library_or_onboard()

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
        if self._nav in {"home", "library", "photos", "videos"}:
            # Stay on Library / onboarding; footer carries Scanning status.
            self._show_library_or_onboard()
            self._refresh_footer()
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

    def _on_image_open(self, media: dict, image) -> None:
        """Start understanding beside the open photo. Never on pointer movement."""
        if image is None or media is None:
            return
        run_id = self._last_run_id
        media_id = media.get("media_id")
        board = getattr(self._canvas_ws, "board", None) or {}
        from semblon.visual.persist import should_submit_visual

        if not should_submit_visual(
            busy=bool(self.engine.busy),
            items=board.get("items") or [],
            media_id=media_id,
            run_id=run_id,
        ):
            return
        ws = self._canvas_ws
        view_w = int(getattr(ws, "_nw", 0) or 0) or None
        view_h = int(getattr(ws, "_nh", 0) or 0) or None
        try:
            self.engine.submit_visual(
                media_id=media_id,
                image=image,
                run_id=run_id,
                color="bgr",
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
                    if self._nav in {"home", "library", "photos", "videos"}:
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
                    if self._nav in {"home", "library", "photos", "videos"}:
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
                    if self._nav in {"home", "library", "photos", "videos"}:
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
                if self._nav in {"home", "library", "photos", "videos"}:
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

        focus = None
        for it in getattr(self, "_insp_selected", None) or []:
            if it.get("kind") == "cluster" and it.get("cluster_id"):
                focus = it["cluster_id"]
                break
        try:
            # Toplevel on Home's root. Home keeps pumping events. No nested mainloop.
            # Shared Cluster Review chrome when WebView exists; else tk + review.html.
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
        from semblon.activity_surface import _processing_stats

        return _processing_stats(self.store, run_id)

    def _open_canvas(self) -> None:
        """First-class canvas is the Home workspace; keep Toplevel as escape hatch."""
        self._navigate("library")

    def _search_person(self) -> None:
        from semblon.search import SearchError, search_people, search_person, search_text

        q = (self.search_var.get() or "").strip()
        ph = getattr(self, "_search_placeholder", SEARCH_PLACEHOLDER)
        if q in {ph, SEARCH_PLACEHOLDER, SEARCH_PLACEHOLDER_PHOTOS}:
            q = ""
        if not q:
            messagebox.showinfo("Semblon", "Type a person name or text from a photo.")
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
            # Still try text/OCR over owned memory — people search is not the only door.
            lines: list[str] = []
            if self.engine.busy:
                lines.extend(search_library_analysing().as_lines())
                lines.append("")
            else:
                lines.extend(search_no_named_people().as_lines())
                lines.append("")
            try:
                text_rec = search_text(self.store, q)
            except SearchError:
                text_rec = None
            if text_rec is not None:
                lines.extend(format_search_lines(text_rec))
            self._set_inspector("Search", lines)
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
        # Broader lookup when people miss: OCR/text over owned memory (not ANN theatre).
        if int(rec.get("count") or 0) == 0:
            try:
                text_rec = search_text(self.store, q)
            except SearchError:
                text_rec = None
            if text_rec is not None and (
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
                lines.append("")
                lines.extend(format_search_lines(text_rec))
        self._set_inspector("Search", lines)

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
            SETTINGS_EXPORT_REVIEW,
            SETTINGS_GPU,
            SETTINGS_OPEN_DIAGNOSTICS,
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
        head.pack(fill=tk.X)
        ttk.Label(head, text=SETTINGS_TITLE, font=H2).pack(side=tk.LEFT)

        sections = {s.id: s for s in settings_contributions()}
        library = sections["library"]
        processing = sections["processing"]
        appearance = sections["appearance"]
        about = sections["about"]

        ttk.Label(pad, text=library.title, font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_16, SP_8)
        )
        ttk.Label(
            pad,
            text=library.hint,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=640,
        ).pack(anchor=tk.W)
        ttk.Label(pad, text="Library location", font=BODY).pack(
            anchor=tk.W, pady=(SP_8, 0)
        )
        loc_row = ttk.Frame(pad)
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

        ttk.Label(pad, text="Packs", font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
        ttk.Label(
            pad,
            text="Missing packs stay missing. They are not an empty library.",
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=640,
        ).pack(anchor=tk.W)
        from semblon.home_shell import capability_sections

        cap_rows = capability_sections(has_library_content=False)
        for row in list(cap_rows["ready"]) + list(cap_rows["tracked"]):
            state = row.get("state") or "Available"
            ttk.Label(
                pad,
                text=f"{row['label']} — {state}",
                font=BODY,
                wraplength=640,
            ).pack(anchor=tk.W, pady=(SP_4, 0))

        ttk.Label(pad, text=processing.title, font=BODY_STRONG).pack(
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
                text=SETTINGS_GPU,
                variable=self._gpu_var,
                command=_on_gpu,
            ).pack(anchor=tk.W)
        else:
            ttk.Label(
                pad,
                text=processing.hint,
                font=CAPTION,
                foreground=TEXT_SECONDARY,
            ).pack(anchor=tk.W)

        ttk.Label(pad, text=appearance.title, font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
        from semblon.ui_prefs import load_theme_mode, resolve_atmosphere_id

        current_mode = load_theme_mode(self.store)
        self._theme_var = tk.StringVar(value=current_mode)
        for mode, label in (
            ("system", "System"),
            ("light", "Light"),
        ):
            ttk.Radiobutton(
                pad,
                text=label,
                value=mode,
                variable=self._theme_var,
                command=lambda m=mode: self._set_theme_mode(m),
            ).pack(anchor=tk.W)

        ttk.Label(
            pad,
            text="Atmospheres — hover a tile to preview states; click to apply",
            font=CAPTION,
            foreground=TEXT_SECONDARY,
        ).pack(anchor=tk.W, pady=(SP_12, SP_8))
        preview_row = ttk.Frame(pad)
        preview_row.pack(anchor=tk.W, fill=tk.X)
        try:
            from semblon.atmosphere_render import build_atmosphere_previews

            def _pick(aid: str) -> None:
                self._theme_var.set(aid)
                self._set_theme_mode(aid)

            tiles = build_atmosphere_previews(
                preview_row,
                current=resolve_atmosphere_id(current_mode),
                on_select=_pick,
            )
            self._atmosphere_tiles = tiles
            for i, tile in enumerate(tiles):
                tile.widget().grid(row=0, column=i, padx=(0, SP_8), pady=2)
        except Exception:  # noqa: BLE001 — radios still work without previews
            from semblon.atmosphere import ATMOSPHERE_LABELS, DARK_ATMOSPHERE_IDS

            for aid in DARK_ATMOSPHERE_IDS:
                ttk.Radiobutton(
                    pad,
                    text=ATMOSPHERE_LABELS.get(aid, aid),
                    value=aid,
                    variable=self._theme_var,
                    command=lambda m=aid: self._set_theme_mode(m),
                ).pack(anchor=tk.W)

        ttk.Label(pad, text=about.title, font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
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
            text=about.hint,
            font=BODY,
            wraplength=640,
        ).pack(anchor=tk.W, pady=(SP_8, 0))

        ttk.Label(pad, text=SETTINGS_ADVANCED, font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
        ttk.Label(
            pad,
            text=SETTINGS_ADVANCED_HINT,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=640,
        ).pack(anchor=tk.W)
        for shortcut, keys in SETTINGS_SHORTCUTS:
            row = ttk.Frame(pad)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=shortcut, font=BODY).pack(side=tk.LEFT)
            ttk.Label(
                row, text=keys, font=META, foreground=TEXT_SECONDARY
            ).pack(side=tk.RIGHT)
        _button(
            pad,
            SETTINGS_EXPORT_REVIEW,
            self._open_html,
            kind="tertiary",
        ).pack(anchor=tk.W, pady=(SP_12, 0))

        ttk.Label(pad, text=SETTINGS_DIAGNOSTICS, font=BODY_STRONG).pack(
            anchor=tk.W, pady=(SP_24, SP_8)
        )
        ttk.Label(
            pad,
            text=SETTINGS_DIAGNOSTICS_HINT,
            font=CAPTION,
            foreground=TEXT_SECONDARY,
            wraplength=640,
        ).pack(anchor=tk.W)
        _button(
            pad,
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
        else:
            self._fill_settings_body()
        self._settings.pack(fill=tk.BOTH, expand=True)
        self._set_inspector(
            "Settings",
            [
                "Appearance, library, and processing live here.",
                "Diagnostics stay under Settings when you need them.",
            ],
        )

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
