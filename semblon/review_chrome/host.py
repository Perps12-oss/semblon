"""Live host for the shared Cluster Review document.

Prefers an in-window HTML host when available. Falls back to the existing
tk ``ReviewApp`` and still writes the new ``review.html`` so snapshot and
live share one chrome. Never opens a second GUI via the system browser.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from semblon.export import STRONG_MIN_INTRA, export_review
from semblon.process import default_review_out

log = logging.getLogger("semblon.review_chrome.host")


def _try_html_frame(parent):
    """Return (frame_factory, kind) or (None, None).

    Only use toolkits already importable — do not add Electron/Tauri/FastAPI.
    """
    try:
        from tkinterweb import HtmlFrame  # type: ignore

        return HtmlFrame, "tkinterweb"
    except Exception:
        pass
    return None, None


def write_snapshot_html(
    store: Path,
    run_id: str,
    out: Path | None = None,
    *,
    strong_min_intra: float = STRONG_MIN_INTRA,
) -> Path:
    """Always emit the shared chrome ``review.html`` (snapshot)."""
    out = Path(out) if out is not None else default_review_out(store)
    export_review(store, run_id, out, strong_min_intra=strong_min_intra)
    return Path(out)


def host_review_chrome(
    store: Path,
    run_id: str,
    *,
    parent=None,
    strong_min_intra: float = STRONG_MIN_INTRA,
    on_add_folder=None,
    force_tk: bool | None = None,
) -> dict:
    """Host Cluster Review for Home / ``review-ui``.

    Returns a small status dict: ``host`` is ``webview`` or ``tk_fallback``.
    Always writes snapshot ``review.html`` alongside the live session.
    """
    store = Path(store)
    html_path = write_snapshot_html(
        store, run_id, strong_min_intra=strong_min_intra
    )

    if force_tk is None:
        force_tk = os.environ.get("SEMBLON_REVIEW_CHROME_TK", "").strip() in (
            "1",
            "true",
            "yes",
        )

    frame_cls, kind = (None, None) if force_tk else _try_html_frame(parent)
    if frame_cls is not None and parent is not None:
        try:
            return _host_in_webview(
                store,
                run_id,
                parent=parent,
                frame_cls=frame_cls,
                kind=kind or "webview",
                strong_min_intra=strong_min_intra,
                html_path=html_path,
            )
        except Exception as e:  # noqa: BLE001 — fall back to tk
            log.warning(
                "review_chrome WebView host failed (%s); falling back to tk review-ui. "
                "Snapshot written to %s",
                e,
                html_path,
            )
    else:
        if not force_tk:
            log.info(
                "review_chrome: no in-window WebView available; "
                "using tk review-ui fallback. Snapshot at %s",
                html_path,
            )

    from semblon.review_ui import ReviewApp

    app = ReviewApp(
        store,
        run_id,
        parent=parent,
        on_add_folder=on_add_folder,
    )
    app.run()
    return {
        "store": str(store.resolve()),
        "run_id": run_id,
        "host": "tk_fallback",
        "review_html": str(html_path.resolve()),
    }


def _host_in_webview(
    store: Path,
    run_id: str,
    *,
    parent,
    frame_cls,
    kind: str,
    strong_min_intra: float,
    html_path: Path,
) -> dict:
    """Embed live document in an HtmlFrame Toplevel on ``parent``."""
    import tkinter as tk
    from tkinter import simpledialog

    from semblon.review_chrome.board_dto import build_chrome_board
    from semblon.review_chrome.render import render_review_document_from_store
    from semblon.review_ui import (
        apply_merge,
        apply_name,
        apply_note,
        apply_split,
    )

    win = tk.Toplevel(parent)
    win.title("Semblon Cluster Review")
    win.geometry("1440x900")

    html_text = render_review_document_from_store(
        store, run_id, mode="live", strong_min_intra=strong_min_intra
    )
    frame = frame_cls(win, messages_enabled=True)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.load_html(html_text)

    def _reload() -> None:
        doc = render_review_document_from_store(
            store, run_id, mode="live", strong_min_intra=strong_min_intra
        )
        frame.load_html(doc)
        write_snapshot_html(store, run_id, html_path, strong_min_intra=strong_min_intra)

    def _cluster_item(cid: str) -> dict:
        return {"kind": "cluster", "cluster_id": cid}

    def _on_message(msg) -> None:
        if not isinstance(msg, dict):
            return
        op = msg.get("op")
        payload = msg.get("payload") or {}
        cid = payload.get("cluster_id") or (
            payload.get("id") if payload.get("kind") == "cluster" else None
        )
        try:
            if op == "same" and cid:
                apply_note(
                    store,
                    run_id,
                    _cluster_item(cid),
                    "worst_pair_same=true",
                )
            elif op in ("different", "split") and cid:
                board = build_chrome_board(
                    store, run_id, mode="live", include_thumbs=False
                )
                cluster = next(
                    (c for c in board["clusters"] if c["cluster_id"] == cid),
                    None,
                )
                pair = (cluster or {}).get("worst_pair") or []
                if len(pair) >= 2:
                    apply_split(store, run_id, cid, list(pair))
            elif op == "merge" and cid:
                other = simpledialog.askstring(
                    "Merge with…",
                    "Donor cluster id (hex):",
                    parent=win,
                )
                if other:
                    apply_merge(store, run_id, [cid, other.strip()])
            elif op == "name" and cid:
                name = simpledialog.askstring(
                    "Name person",
                    "Display name (cluster is not a person until named):",
                    parent=win,
                )
                if name and name.strip():
                    apply_name(
                        store,
                        run_id,
                        _cluster_item(cid),
                        name.strip(),
                    )
            _reload()
        except Exception as e:  # noqa: BLE001
            log.warning("review_chrome apply failed: %s", e)

    win._semblon_apply = _on_message  # type: ignore[attr-defined]
    win.wait_window()
    return {
        "store": str(store.resolve()),
        "run_id": run_id,
        "host": kind,
        "review_html": str(html_path.resolve()),
    }


__all__ = [
    "host_review_chrome",
    "write_snapshot_html",
]
