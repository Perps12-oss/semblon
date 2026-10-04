"""Activity feature — first modular production page.

Builds soft Recent activity into the host Activity frame. Read-only.
Uses Application.activity_memory. Does not write the store or assign persons.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from semblon.empty_states import activity_empty
from semblon.gui_registry import Feature, GuiCommand, NavContribution

__all__ = [
    "activity_feature",
    "build_activity_workspace",
    "refresh_activity_workspace",
    "show_activity_page",
]


def build_activity_workspace(host: Any) -> None:
    """Populate host._activity chrome (headline, CTAs, body)."""
    import tkinter as tk
    from tkinter import ttk

    from semblon.activity_surface import ACTIVITY_HEADLINE, ACTIVITY_SUBCOPY
    from semblon.ui_tokens import BODY, H1, SP_4, SP_8, SP_12, SP_16, SP_20, SP_24, TEXT_SECONDARY
    from semblon.ui_widgets import Button

    frame = host._activity
    if getattr(host, "_pane_is_ready", None) and host._pane_is_ready("activity"):
        return
    for child in frame.winfo_children():
        child.destroy()
    shell = ttk.Frame(frame, padding=(SP_24, SP_20))
    shell.pack(fill=tk.BOTH, expand=True)
    if hasattr(host, "_mark_pane_ready"):
        host._mark_pane_ready("activity")
    ttk.Label(shell, text=ACTIVITY_HEADLINE, font=H1).pack(anchor=tk.W)
    ttk.Label(
        shell,
        text=ACTIVITY_SUBCOPY,
        font=BODY,
        foreground=TEXT_SECONDARY,
        wraplength=560,
    ).pack(anchor=tk.W, pady=(SP_4, SP_16))

    actions = ttk.Frame(shell)
    actions.pack(anchor=tk.W, pady=(0, SP_12))
    host.btn_activity_review = Button(
        actions,
        text="Start naming",
        command=lambda: host._navigate("unknown"),
        kind="secondary",
    )
    host.btn_activity_review.pack(side=tk.LEFT, padx=(0, SP_8))
    host.btn_activity_people = Button(
        actions,
        text="Open People",
        command=lambda: host._navigate("people"),
        kind="tertiary",
    )
    host.btn_activity_people.pack(side=tk.LEFT)

    host._activity_body = ttk.Frame(shell)
    host._activity_body.pack(anchor=tk.W, fill=tk.BOTH, expand=True)
    host._last_activity_view = None


def refresh_activity_workspace(host: Any, view: dict | None = None) -> None:
    import tkinter as tk
    from tkinter import ttk

    from semblon.activity_surface import (
        ACTIVITY_HEADLINE,
        activity_workspace_sections,
        format_activity_memory_lines,
    )
    from semblon.ui_tokens import BODY, CAPTION, SP_4, SP_12, TEXT_PRIMARY, TEXT_SECONDARY

    if view is None:
        view = getattr(host, "_last_activity_view", None)
    if view is None:
        return
    host._last_activity_view = view
    body = getattr(host, "_activity_body", None)
    if body is None:
        return
    for child in body.winfo_children():
        child.destroy()

    sections = activity_workspace_sections(view)
    for sec in sections:
        title = str(sec.get("title") or "")
        ttk.Label(body, text=title, font=CAPTION).pack(anchor=tk.W, pady=(SP_12, SP_4))
        rows = list(sec.get("rows") or [])
        emptyish = bool(sec.get("empty"))
        for row in rows:
            ttk.Label(
                body,
                text=str(row),
                font=BODY,
                foreground=TEXT_SECONDARY if emptyish else TEXT_PRIMARY,
                wraplength=560,
            ).pack(anchor=tk.W, pady=(0, SP_4))

    if hasattr(host, "btn_activity_review"):
        show_review = bool(view.get("has_unnamed")) and not view.get("empty")
        try:
            if show_review:
                host.btn_activity_review.configure(state=tk.NORMAL)
            else:
                host.btn_activity_review.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    host._set_inspector(ACTIVITY_HEADLINE, format_activity_memory_lines(view))


def show_activity_page(host: Any) -> None:
    """Route handler: show Activity workspace and load soft memory."""
    from semblon.activity_surface import ACTIVITY_HEADLINE, load_activity_memory
    from semblon.process import latest_run_id

    host._hide_workspace_panes()
    host._set_inspector_collapsed(True)
    host._activity.pack(fill="both", expand=True)

    title = ACTIVITY_HEADLINE
    if not host.store.is_file():
        refresh_activity_workspace(host, load_activity_memory(host.store, None))
        return

    rid = latest_run_id(host.store)
    if not rid:
        refresh_activity_workspace(host, load_activity_memory(host.store, None))
        return

    try:
        from semblon.application import activity_memory
        from semblon.empty_states import is_expected_condition

        view = activity_memory(host.store, rid)
    except (sqlite3.DatabaseError, OSError, ValueError) as e:
        if is_expected_condition(e):
            refresh_activity_workspace(
                host,
                {
                    "empty": True,
                    "partial": False,
                    "processing": None,
                    "together_lines": [],
                    "moment_lines": [],
                    "has_unnamed": False,
                    "empty_state": activity_empty(),
                },
            )
        else:
            host._show_failure(e)
        return

    refresh_activity_workspace(host, view)
    host._inspector_title.set(title)


def _cmd_open_people(host: Any, _context: Any = None) -> None:
    host._navigate("people")


def _cmd_review_people(host: Any, _context: Any = None) -> None:
    host._navigate("unknown")


def activity_feature() -> Feature:
    return Feature(
        id="activity",
        label="Activity",
        nav=NavContribution(
            section="MAIN",
            route_id="activity",
            label="Activity",
            shortcut="3",
            order=2,
        ),
        route_id="activity",
        page=show_activity_page,
        commands=(
            GuiCommand(
                id="activity.open_people",
                label="Open People",
                run=_cmd_open_people,
                surfaces=frozenset({"palette", "overflow"}),
            ),
                GuiCommand(
                id="activity.review_people",
                label="Start naming",
                run=_cmd_review_people,
                surfaces=frozenset({"palette", "overflow"}),
            ),
        ),
    )
