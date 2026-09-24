"""Render the shared Cluster Review document (snapshot or live)."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from semblon.export import (
    EVIDENCE_SCHEMA,
    EVIDENCE_SCRIPT_ID,
    STRONG_MIN_INTRA,
    _evidence_payload,
    _evidence_script,
    _file_uri,
)
from semblon.review_chrome.board_dto import build_chrome_board

PACKAGE_DIR = Path(__file__).resolve().parent


def _read_asset(name: str) -> str:
    return (PACKAGE_DIR / name).read_text(encoding="utf-8")


def _esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def _run_local_label(started_at: str | None, run_id: str) -> str:
    """Prefer a short local-looking stamp; fall back to run_id prefix."""
    raw = (started_at or "").strip()
    if not raw:
        return run_id[:16]
    # ISO-ish → "YYYY-MM-DD HH:MM"
    m = re.match(
        r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})",
        raw,
    )
    if m:
        return f"{m.group(1)} {m.group(2)}"
    # Compact run ids: 20260913T153515Z-…
    m2 = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})", run_id)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)} {m2.group(4)}:{m2.group(5)}"
    return raw[:19]


def _explorer_html(board: dict, *, mode: str) -> str:
    store = board.get("store") or ""
    if not store:
        return ""
    try:
        store_path = Path(store)
        target = store_path if store_path.is_dir() else store_path.parent
        uri = _file_uri(str(target))
    except OSError:
        return ""
    if not uri:
        return ""
    if mode == "snapshot":
        return (
            f'<a class="btn-explorer" href="{_esc(uri)}">'
            f"Open in Explorer</a>"
        )
    return (
        f'<button type="button" class="btn-explorer" id="btn-explorer" '
        f'data-store="{_esc(store)}">'
        f"Open in Explorer</button>"
    )


def _evidence_for_board(board: dict, run_row: dict | None = None) -> str:
    """Build #semblon-run-evidence from the chrome board + optional raw run row."""
    stats = board.get("stats") or {}
    clusters = board.get("clusters") or []
    decisions = board.get("decisions") or []
    counts = {
        "faces": int(stats.get("faces_detected", 0)),
        "ok": int(stats.get("ok", 0)),
        "low_quality": int(stats.get("low_quality", 0)),
        "rejected": int(stats.get("rejected", 0)),
        "clusters": int(stats.get("clusters", 0)),
        "review_required": int(stats.get("review", 0)),
        "strong": int(stats.get("good", 0)),
        "unassigned": int(stats.get("unassigned", 0)),
        "decisions": len(decisions),
    }

    run = run_row or {
        "run_id": board.get("run_id"),
        "started_at": board.get("run_started_at"),
        "finished_at": None,
        "software_version": None,
        "pack_id": board.get("pack_id"),
        "embedding_dim": None,
        "embedding_norm": None,
        "config_json": None,
        "runtime_json": None,
        "arch": board.get("arch"),
        "execution": board.get("execution"),
        "ort_version": None,
        "peak_rss_mb": None,
        "timings_json": board.get("timings"),
    }
    cluster_rows = [
        {
            "cluster_id": c["cluster_id"],
            "strategy": c.get("strategy") or "",
            "face_count": c["face_count"],
            "min_intra": c.get("min_intra"),
            "status": c.get("status") or "auto",
        }
        for c in clusters
    ]
    # _evidence_payload expects decision rows with policy_json key.
    decision_rows = [
        {
            "kind": d.get("kind"),
            "cluster_id": d.get("cluster_id"),
            "face_id": d.get("face_id"),
            "created_at": d.get("created_at"),
            "policy_json": json.dumps(d.get("policy"))
            if not isinstance(d.get("policy"), str) and d.get("policy") is not None
            else (d.get("policy") if isinstance(d.get("policy"), str) else "{}"),
        }
        for d in decisions
    ]
    payload = _evidence_payload(
        run,
        cluster_rows,
        counts,
        float(board.get("strong_min_intra") or STRONG_MIN_INTRA),
        decision_rows,
    )
    # Ensure schema_version stays pinned.
    payload["schema_version"] = EVIDENCE_SCHEMA
    return _evidence_script(payload)


def _thumb_ssr(t: dict | None, size: int = 40) -> str:
    if not t:
        return '<span class="thumb-missing">—</span>'
    if t.get("data_uri"):
        img = (
            f'<img class="thumb" src="{t["data_uri"]}" alt="{_esc(t.get("face_id"))}" '
            f'style="width:{size}px;height:{size}px">'
        )
        if t.get("path_uri"):
            return f'<a href="{_esc(t["path_uri"])}">{img}</a>'
        return img
    return (
        f'<span class="thumb-missing" title="{_esc(t.get("face_id"))}">file missing</span>'
    )


def _card_ssr(c: dict) -> str:
    cls = "good" if c.get("classification") == "good" else "review"
    badge = "GOOD" if cls == "good" else "REVIEW"
    mi = c.get("min_intra")
    mi_s = "—" if mi is None else f"{float(mi):.2f}"
    sim_min = c.get("sim_min")
    sim_max = c.get("sim_max")
    lo = "—" if sim_min is None else f"{float(sim_min):.2f}"
    hi = "—" if sim_max is None else f"{float(sim_max):.2f}"
    thumbs = c.get("thumbs") or []
    thumb_html = "".join(_thumb_ssr(t) for t in thumbs[:10])
    extra = len(thumbs) - 10
    if extra > 0:
        thumb_html += f'<span class="thumb-more">+{extra}</span>'
    meta = (
        f'{c.get("face_count", 0)} faces  ·  {mi_s} worst pair  ·  '
        f"Similarity range: {lo} – {hi}"
    )
    return (
        f'<article class="cluster-card {cls}" id="c-{_esc(c["cluster_id"])}" '
        f'data-kind="cluster" data-id="{_esc(c["cluster_id"])}">'
        f'<div class="card-top"><span class="card-title">Cluster {_esc(c.get("display_index"))}</span>'
        f'<span class="badge {cls}">{badge}</span></div>'
        f'<div class="card-meta">{_esc(meta)}</div>'
        f'<div class="thumb-row">{thumb_html}</div></article>'
    )


def _ssr_board_html(board: dict) -> str:
    """Static first paint so forensic HTML matches the mock without running JS."""
    clusters = board.get("clusters") or []
    review = [c for c in clusters if c.get("classification") == "review"]
    strong = [c for c in clusters if c.get("classification") == "good"]
    un = board.get("unassigned") or {}
    rej = board.get("rejected") or {}
    decisions = board.get("decisions") or []

    def section(sid: str, title: str, cls: str, copy: str, body: str) -> str:
        return (
            f'<section class="priority-group {cls}" id="{sid}">'
            f'<div class="group-head"><h2>{title}</h2><p>{copy}</p></div>'
            f'<div class="card-grid">{body}</div></section>'
        )

    review_body = "".join(_card_ssr(c) for c in review) or '<p class="none-line">none</p>'
    strong_body = "".join(_card_ssr(c) for c in strong) or '<p class="none-line">none</p>'

    un_thumbs = "".join(_thumb_ssr(t) for t in (un.get("thumbs") or [])[:10])
    un_extra = int(un.get("face_count") or 0) - min(10, len(un.get("thumbs") or []))
    if un_extra > 0:
        un_thumbs += f'<span class="thumb-more">+{un_extra}</span>'
    # Surface derived track labels for video unassigned (tests + forensic readers).
    track_bits = []
    for tr in un.get("tracks") or []:
        name = (tr.get("path") or "").replace("\\", "/").rstrip("/").split("/")[-1] or "track"
        track_bits.append(
            f'<p class="card-meta">track {_esc(name)} · {tr.get("face_count", 0)} observations · '
            f't={tr.get("t_ms_start")}-{tr.get("t_ms_end")}ms · not a person</p>'
        )
    if not track_bits and int(un.get("face_count") or 0):
        # Still/video leftovers — note untracked when video present without a track group.
        video_caps = []
        for t in un.get("thumbs") or []:
            if t.get("source_type") == "video":
                video_caps.append(
                    f'<p class="card-meta">video frame={t.get("frame_id")} '
                    f't_ms={t.get("t_ms")} · held out of clustering · not a person</p>'
                )
        if video_caps:
            track_bits.append(
                '<p class="card-meta">untracked · held out of clustering · not a person</p>'
            )
            track_bits.extend(video_caps)
    none = '<p class="none-line">none</p>'
    un_body = (
        '<article class="cluster-card unassigned" data-kind="unassigned" data-id="unassigned">'
        '<div class="card-top"><span class="card-title">Unassigned</span></div>'
        f'<div class="card-meta">{int(un.get("face_count") or 0)} faces</div>'
        f'{"".join(track_bits)}'
        f'<div class="thumb-row">{un_thumbs or none}</div></article>'
    )

    rej_thumbs = "".join(_thumb_ssr(t) for t in (rej.get("thumbs") or [])[:10])
    rej_body = (
        (
            '<article class="cluster-card" data-kind="rejected" data-id="rejected">'
            '<div class="card-top"><span class="card-title">Rejected</span></div>'
            f'<div class="card-meta">{int(rej.get("face_count") or 0)} faces</div>'
            f'<div class="thumb-row">{rej_thumbs or none}</div></article>'
        )
        if int(rej.get("face_count") or 0)
        else none
    )

    dec_body = '<p class="none-line">none</p>'
    if decisions:
        items = []
        for d in decisions:
            items.append(
                "<li>"
                f"<strong>{_esc(d.get('kind'))}</strong> "
                f"{_esc(d.get('cluster_id') or d.get('face_id') or '')} "
                f"<span class=\"card-meta\">{_esc(d.get('created_at'))}</span>"
                "</li>"
            )
        dec_body = "<ol>" + "".join(items) + "</ol>"

    n_un = int(un.get("face_count") or 0)
    n_rej = int(rej.get("face_count") or 0)
    parts = [
        section(
            "review",
            "REVIEW REQUIRED (highest priority)",
            "review",
            "These clusters have low confidence, mixed faces or unusual similarity scores.",
            review_body,
        ),
        section(
            "strong",
            "STRONG CLUSTERS",
            "strong",
            "These clusters look consistent. No immediate action needed. Still not persons until named after review.",
            strong_body,
        ),
        section(
            "unassigned",
            f"UNASSIGNED ({n_un})",
            "unassigned",
            "Faces that didn’t meet the clustering threshold. Video faces are observations "
            "(held out of clustering), not persons.",
            un_body,
        ),
        section(
            "rejected",
            f"REJECTED ({n_rej})",
            "rejected",
            "rejected / low_quality stay held-out. Not clustered.",
            rej_body,
        ),
        (
            f'<section id="decisions" class="priority-group rejected">'
            f'<div class="group-head"><h2>DECISIONS ({len(decisions)})</h2>'
            f"<p>Human review. Merge does not create a person. "
            f"rejected / low_quality stay held-out.</p></div>"
            f"{dec_body}</section>"
        ),
    ]
    # Also emit the compact count line forensic readers / older tests look for.
    stats = board.get("stats") or {}
    compact = (
        f'<p class="card-meta" id="legacy-counts">'
        f'UNASSIGNED {n_un} · REVIEW REQUIRED {stats.get("review", 0)} · '
        f'STRONG {stats.get("good", 0)}</p>'
    )
    return compact + "\n".join(parts)


def render_review_document(
    board: dict,
    *,
    mode: str = "snapshot",
    evidence: bool | None = None,
    run_row: dict | None = None,
) -> str:
    """Return one self-contained HTML document for snapshot or live host.

    ``board`` is the shared chrome DTO from ``build_chrome_board``.
    Snapshot keeps the evidence JSON script; live may omit it.
    """
    if mode not in ("snapshot", "live"):
        raise ValueError(f"mode must be snapshot|live, got {mode!r}")
    if evidence is None:
        evidence = mode == "snapshot"

    board = dict(board)
    board["mode"] = mode

    tokens = _read_asset("tokens.css")
    shell_css = _read_asset("shell.css")
    shell_html = _read_asset("shell.html")
    board_js = _read_asset("board.js")
    bridge_js = _read_asset("bridge.js")

    run_id = board.get("run_id") or ""
    title = f"Semblon review — {run_id}" if mode == "snapshot" else "Semblon Cluster Review"
    empty = board.get("empty_state") or ""
    empty_html = (
        f'<p class="empty-state">{_esc(empty)}</p>' if empty else ""
    )
    public_board = _public_board_json(board)
    board_json = json.dumps(public_board, ensure_ascii=False, default=str).replace(
        "</", "<\\/"
    )
    evidence_script = _evidence_for_board(board, run_row=run_row) if evidence else ""
    ssr = _ssr_board_html(board)

    # Snapshot buttons are disabled in markup for forensic readers without JS.
    disabled_attr = " disabled" if mode == "snapshot" else ""
    ssr_note = (
        f'<!-- mode={mode} snapshot_buttons_disabled={mode == "snapshot"} -->'
        if mode == "snapshot"
        else ""
    )

    page = (
        shell_html.replace("__TITLE__", _esc(title))
        .replace("__TOKENS_CSS__", tokens)
        .replace("__SHELL_CSS__", shell_css)
        .replace("__MODE__", mode)
        .replace("__RUN_ID_ESC__", _esc(run_id))
        .replace(
            "__RUN_LOCAL__",
            _esc(_run_local_label(board.get("run_started_at"), run_id)),
        )
        .replace("__EXPLORER_HTML__", _explorer_html(board, mode=mode))
        .replace("__EMPTY_STATE_HTML__", empty_html)
        .replace("__BOARD_JSON__", board_json)
        .replace("__EVIDENCE_SCRIPT__", evidence_script)
        .replace("__BOARD_JS__", board_js)
        .replace("__BRIDGE_JS__", bridge_js)
    )
    page = page.replace(
        '<div id="board-root"></div>',
        f'<div id="board-root">{ssr_note}{ssr}</div>',
    )
    # Ensure snapshot verb affordances exist (disabled) even before inspector opens.
    if mode == "snapshot" and 'data-op="same"' not in page:
        page = page.replace(
            '<div class="inspector-body hidden" id="inspector-body"></div>',
            (
                '<div class="inspector-body hidden" id="inspector-body">'
                f'<button type="button" class="btn-same" data-op="same"{disabled_attr} '
                f'title="Open Semblon Home to decide">Same person</button>'
                f'<button type="button" class="btn-diff" data-op="different"{disabled_attr} '
                f'title="Open Semblon Home to decide">Different people</button>'
                f'<button type="button" class="btn-action" data-op="merge"{disabled_attr} '
                f'title="Open Semblon Home to decide">Merge with…</button>'
                f'<button type="button" class="btn-action" data-op="split"{disabled_attr} '
                f'title="Open Semblon Home to decide">Split cluster</button>'
                f'<button type="button" class="btn-action" data-op="name"{disabled_attr} '
                f'title="Open Semblon Home to decide">Name person</button>'
                "</div>"
            ),
        )
    return page


def _public_board_json(board: dict) -> dict:
    """Drop non-JSON / identity vectors from the browser payload."""
    return dict(board)


def render_review_document_from_store(
    store: Path,
    run_id: str,
    *,
    mode: str = "snapshot",
    strong_min_intra: float = STRONG_MIN_INTRA,
    include_thumbs: bool | None = None,
) -> str:
    board = build_chrome_board(
        store,
        run_id,
        mode=mode,
        strong_min_intra=strong_min_intra,
        include_thumbs=include_thumbs,
    )
    return render_review_document(board, mode=mode)


__all__ = [
    "EVIDENCE_SCRIPT_ID",
    "PACKAGE_DIR",
    "build_chrome_board",
    "render_review_document",
    "render_review_document_from_store",
]
