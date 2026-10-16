"""UX Rescue §7 — Advanced Diagnostics panel (read-only).

Collects every diagnostic string currently dumped by Home Settings / Inspector
into a separate Toplevel. Presentation only — does not write the store, does
not touch FaceKit/identity/ingest/JobEngine semantics.

Public API for other agents (Settings §6 wires the entry later)::

    from semblon.advanced_diagnostics import (
        build_advanced_diagnostics_lines,
        open_advanced_diagnostics,
    )
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError:  # pragma: no cover - host Python without tk
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]

# Soft import of design tokens; fall back if §1 module is missing mid-merge.
try:
    from semblon.ui_tokens import (
        BODY,
        CAPTION_STRONG,
        H2,
        BG_INSET,
        MONO,
        SP_8,
        SP_12,
        SP_16,
        SP_24,
        SURFACE_PRIMARY,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        TERTIARY_HEIGHT,
    )
except ImportError:  # pragma: no cover
    BODY = ("Segoe UI", 11)
    CAPTION_STRONG = ("Segoe UI", 9, "bold")
    H2 = ("Segoe UI", 16, "bold")
    BG_INSET = "#F0EDE6"
    MONO = ("Cascadia Code", 12)
    SP_8 = 8
    SP_12 = 12
    SP_16 = 16
    SP_24 = 24
    SURFACE_PRIMARY = "#FFFFFF"
    TEXT_PRIMARY = "#1A1A1A"
    TEXT_SECONDARY = "#6B6B6B"
    TERTIARY_HEIGHT = 28

_PANEL_WIDTH = 720
_PANEL_HEIGHT = 640
_RECENT_RUN_LIMIT = 12

__all__ = [
    "build_advanced_diagnostics_lines",
    "open_advanced_diagnostics",
]


def build_advanced_diagnostics_lines(store: Path | str | None) -> list[str]:
    """Collect read-only diagnostic lines for Advanced Diagnostics.

    Preserves content currently shown via ``HomeApp._show_settings`` plus
    integrity / chrome legend / recent runs. Sections match UX Rescue §7 order.
    """
    store_path = Path(store) if store is not None else None
    lines: list[str] = []
    lines.extend(_section_store(store_path))
    lines.append("")
    lines.extend(_section_processing())
    lines.append("")
    lines.extend(_section_observers())
    lines.append("")
    lines.extend(_section_architecture())
    lines.append("")
    lines.extend(_section_recent_runs(store_path))
    return lines


def open_advanced_diagnostics(parent: Any, store: Path | str | None) -> Any:
    """Open a read-only Advanced Diagnostics Toplevel (~480px, scrollable).

    Returns the Toplevel (or ``None`` when tkinter is unavailable). Safe to call
    from Settings later — this module owns the panel; Home only imports it.
    """
    if tk is None:
        return None

    lines = build_advanced_diagnostics_lines(store)
    text = "\n".join(lines)

    win = tk.Toplevel(parent)
    win.title("Advanced diagnostics")
    win.configure(bg=SURFACE_PRIMARY)
    win.geometry(f"{_PANEL_WIDTH}x{_PANEL_HEIGHT}")
    win.minsize(_PANEL_WIDTH, 360)
    try:
        win.transient(parent)
    except tk.TclError:
        pass

    header = ttk.Frame(win, padding=(SP_16, SP_12, SP_16, SP_8))
    header.pack(fill=tk.X)
    ttk.Label(header, text="Advanced diagnostics", font=H2).pack(side=tk.LEFT)
    ttk.Label(
        header,
        text="Read-only · copy for support",
        font=CAPTION_STRONG,
        foreground=TEXT_SECONDARY,
    ).pack(side=tk.LEFT, padx=(SP_8, 0))

    def _copy_all() -> None:
        try:
            win.clipboard_clear()
            win.clipboard_append(text)
            win.update_idletasks()
        except tk.TclError:
            pass

    copy_btn = ttk.Button(header, text="Copy all", command=_copy_all)
    copy_btn.pack(side=tk.RIGHT)
    # Tertiary intent: compact height when theme allows.
    try:
        copy_btn.configure(padding=(12, 4))
    except tk.TclError:
        pass
    _ = TERTIARY_HEIGHT  # documented class; ttk height is theme-driven

    body = ttk.Frame(win, padding=(SP_16, 0, SP_16, SP_16))
    body.pack(fill=tk.BOTH, expand=True)

    scroll = ttk.Scrollbar(body, orient=tk.VERTICAL)
    # Text widget: monospace for paths/IDs; headers use same face for simplicity
    # (section titles are already uppercase ASCII markers in the line stream).
    view = tk.Text(
        body,
        wrap=tk.WORD,
        font=MONO,
        bg=BG_INSET,
        fg=TEXT_PRIMARY,
        relief=tk.FLAT,
        highlightthickness=0,
        padx=SP_8,
        pady=SP_8,
        yscrollcommand=scroll.set,
    )
    scroll.config(command=view.yview)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    view.insert("1.0", text)
    view.configure(state=tk.DISABLED)

    # Keep a body-weight note for assistive context (not editable).
    ttk.Label(
        win,
        text="These details are for diagnostics only. They do not change your photos or people.",
        font=BODY,
        foreground=TEXT_SECONDARY,
        wraplength=_PANEL_WIDTH - 2 * SP_16,
    ).pack(anchor=tk.W, padx=SP_16, pady=(0, SP_12))

    return win


# ── Section builders ────────────────────────────────────────────────────────


def _heading(title: str) -> str:
    return f"— {title} —"


def _section_store(store: Path | None) -> list[str]:
    lines = [_heading("Store")]
    if store is None:
        lines.append("Store: (none)")
        lines.append("integrity unavailable: no store path")
        return lines
    lines.append(f"Store: {store}")
    try:
        resolved = store.resolve()
        if str(resolved) != str(store):
            lines.append(f"Resolved: {resolved}")
    except OSError:
        pass
    if not store.is_file():
        lines.append("integrity: store file not present yet")
        return lines
    try:
        from semblon.store import integrity_report

        integ = integrity_report(store)
        lines.append(
            f"integrity ok={integ['ok']} unfinished={len(integ['unfinished_runs'])}"
        )
        lines.append(f"pragma_integrity={integ.get('pragma_integrity')}")
        lines.append(
            f"schema_version={integ.get('schema_version')}  "
            f"media={integ.get('media')} faces={integ.get('faces')} "
            f"persons={integ.get('persons')}"
        )
        if integ.get("unfinished_runs"):
            lines.append(
                "unfinished_runs: " + ", ".join(str(r) for r in integ["unfinished_runs"])
            )
        lines.append(str(integ.get("note") or ""))
    except (OSError, sqlite3.DatabaseError, KeyError, TypeError) as e:
        lines.append(f"integrity unavailable: {e}")
    return lines


def _section_processing() -> list[str]:
    from semblon.engine import format_execution_status_lines
    from semblon.providers import weights_status

    w = weights_status()
    lines = [_heading("Processing")]
    # FaceKit / buffalo_l presence (same strings Settings used to dump).
    lines.append("Identity: YuNet + SFace (OpenCV Zoo); buffalo_l retired from production")
    lines.append(f"pack_family: insightface/buffalo_l")
    lines.append(f"Weights dir: {w['dir']}")
    lines.append(f"onnx files: {w['onnx_count']}  bundled={w['bundled']}")
    present = w.get("present") or []
    if present:
        lines.append("onnx present: " + ", ".join(str(n) for n in present))
    lines.append(str(w.get("note") or ""))
    lines.extend(format_execution_status_lines())
    return lines


def _section_observers() -> list[str]:
    # Prefer observers module (not home_ui) to avoid circular imports when Home
    # later wires open_advanced_diagnostics from Settings.
    from semblon.observers import (
        BASE_HOME_OBSERVERS,
        modality_product_settings_lines,
        resolve_product_observers,
    )

    base_csv = ",".join(BASE_HOME_OBSERVERS)
    lines = [_heading("Observers")]
    lines.append(f"Home observers (base): {base_csv}")
    lines.append(f"Home observers (product): {resolve_product_observers()}")
    lines.extend(modality_product_settings_lines())
    return lines


def _section_architecture() -> list[str]:
    from semblon.r3_chrome import chrome_legend_lines

    lines = [_heading("Architecture")]
    # Exact strings from HomeApp._show_settings (preserve diagnostic content).
    lines.append(
        "Shell: Library | Workspace/Canvas | Inspector "
        "(compatibility Tk; toolkit unnamed)"
    )
    lines.append(
        "R3 chrome: five display states + processing ring grammar (shape, not hue)."
    )
    lines.append(
        "Ingest is a JobEngine job, not an application lock. "
        "Review/People/Search stay usable."
    )
    lines.append(
        "Pause: cooperative between files (not mid-file); "
        "Resume while paused continues the same job"
    )
    lines.append("Cancel: between files (not mid-file)")
    lines.append(
        "Resume when idle: continues cancelled/interrupted run "
        "from next unfinished stage"
    )
    lines.append("Stills bar: real files done / files total, climbs to 100%")
    lines.extend(chrome_legend_lines())
    return lines


def _section_recent_runs(store: Path | None) -> list[str]:
    lines = [_heading("Recent runs")]
    lines.append("Open Activity in the Library for the current run summary.")
    if store is None or not store.is_file():
        lines.append("(no runs — store not present)")
        return lines
    try:
        conn = sqlite3.connect(f"file:{store.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        rows = conn.execute(
            """SELECT r.run_id AS run_id,
                      r.started_at AS started_at,
                      r.finished_at AS finished_at,
                      r.notes AS notes,
                      (SELECT COUNT(*) FROM faces f WHERE f.run_id = r.run_id) AS faces,
                      (SELECT COUNT(DISTINCT o.media_id) FROM observations o
                         WHERE o.run_id = r.run_id) AS media
               FROM runs r
               ORDER BY COALESCE(r.finished_at, r.started_at) DESC, r.run_id DESC
               LIMIT ?""",
            (_RECENT_RUN_LIMIT,),
        ).fetchall()
        conn.close()
    except (OSError, sqlite3.DatabaseError) as e:
        lines.append(f"recent runs unavailable: {e}")
        return lines
    if not rows:
        lines.append("(no runs yet)")
        return lines
    for row in rows:
        rid = row["run_id"]
        started = row["started_at"] or "—"
        finished = row["finished_at"] or "unfinished"
        notes = row["notes"] or ""
        faces = int(row["faces"] or 0)
        media = int(row["media"] or 0)
        note_bit = f"  notes={notes}" if notes else ""
        lines.append(
            f"{rid}  started={started}  finished={finished}  "
            f"media={media} faces={faces}{note_bit}"
        )
    return lines
