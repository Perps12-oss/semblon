"""Home library shell — presentation for the local-first dashboard.

Matches the product Home: stats, ready vs not-installed capabilities,
and last-result honesty. Never invents model availability. Never writes
the store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Caps shown under Available when the model is AVAILABLE.
_READY_IDS = frozenset({"library_query"})

# Optional product capabilities (not Home nav). ann_index stays invisible —
# it is an accelerator under Lens/Search, not a tracked Home row.
_TRACKED_IDS = (
    "visual_embedding",
    "ocr",
    "translation",
    "grounding",
    "barcode",
    "vlm",
    "lkg",
    "screen_capture",
)

SHELL_HEADLINE = "Your pictures stay here."
SHELL_SUBCOPY = (
    "Semblon finds faces in your photos on this computer, groups similar ones, "
    "and lets you name the people. Add a folder to begin. "
    "Available vs optional below is honest — missing a model is not an empty library."
)
SHELL_READY_TITLE = "Available"
SHELL_TRACKED_TITLE = "Optional · component required"
SHELL_LAST_TITLE = "Last result"
SHELL_LAST_EMPTY = "Nothing has been asked yet."
SHELL_LAST_HINT = (
    "A failure says it did not run. "
    "“Nothing matched” only appears after a real run."
)
SHELL_SAVED_LINE = "Saved faces, text, and barcodes already in the library"


def _state_label(model_state: str, *, disabled_as: str = "Experimental") -> str:
    """Product honesty vocabulary — never imply a nav button is required."""
    state = (model_state or "").upper()
    if state == "AVAILABLE":
        return "Available"
    if state == "DISABLED":
        return disabled_as
    if state in {"UNSUPPORTED_RUNTIME", "INCOMPATIBLE"}:
        return "Optional · not supported here"
    if state == "CORRUPT":
        return "Unavailable"
    return "Optional · install needed"


def probe_model_overrides() -> dict[str, str]:
    """Disk/runtime facts only. Never download. Never add sidebar rows."""
    overrides: dict[str, str] = {}
    try:
        from semblon.observers import probe_ocr_status

        ready, _ = probe_ocr_status()
        if ready:
            overrides["ocr"] = "AVAILABLE"
    except Exception:
        pass
    try:
        import os

        pack = os.environ.get("SEMBLON_LKG_PACK")
        if pack and Path(pack).is_file():
            overrides["lkg"] = "AVAILABLE"
    except Exception:
        pass
    try:
        from semblon.sam2_runtime import sam2_ready

        if callable(sam2_ready) and sam2_ready():
            overrides["grounding"] = "AVAILABLE"
    except Exception:
        pass
    return overrides


def capability_sections(
    *,
    report: list[dict] | None = None,
    has_library_content: bool = False,
    model_overrides: dict[str, str] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Partition runtime_contract status into Ready vs Not installed rows.

    Ready always includes Library search when AVAILABLE. When the store
    already has local content, add the honesty line about saved faces/text.
    Deferred / missing models stay listed — never omitted to look empty.
    Live ``model_overrides`` (from a disk probe) may move a row to Available.
    """
    from semblon.runtime_contract import default_catalog, status_report

    if report is not None:
        rows = list(report)
    else:
        overrides = model_overrides if model_overrides is not None else probe_model_overrides()
        rows = list(status_report(model_overrides=overrides or None))
    by_id = {str(r.get("capability_id") or ""): r for r in rows}
    catalog = {spec.id: spec for spec in default_catalog().specs}

    ready: list[dict[str, str]] = []
    for cap_id in _READY_IDS:
        row = by_id.get(cap_id) or {}
        spec = catalog.get(cap_id)
        label = (spec.label if spec else cap_id) or cap_id
        if (row.get("model_state") or "").upper() == "AVAILABLE":
            ready.append({"id": cap_id, "label": label, "state": ""})
    if has_library_content:
        ready.append({"id": "saved_local", "label": SHELL_SAVED_LINE, "state": ""})

    tracked: list[dict[str, str]] = []
    for cap_id in _TRACKED_IDS:
        row = by_id.get(cap_id) or {}
        spec = catalog.get(cap_id)
        label = (spec.label if spec else cap_id) or cap_id
        model = str(row.get("model_state") or "MISSING")
        if model.upper() == "AVAILABLE":
            ready.append({"id": cap_id, "label": label, "state": "Available"})
            continue
        tracked.append(
            {
                "id": cap_id,
                "label": label,
                "state": _state_label(model),
            }
        )

    return {"ready": ready, "tracked": tracked}


def shell_stats(summary: dict | None) -> list[dict[str, Any]]:
    """Stat tiles for the Home shell. Zeros are real."""
    s = summary or {}
    return [
        {"key": "photos", "label": "Photos", "value": int(s.get("photos") or 0)},
        {
            "key": "video_frames",
            "label": "Video frames",
            "value": int(s.get("video_frames") or 0),
        },
        {"key": "named", "label": "Named", "value": int(s.get("named_people") or 0)},
        {
            "key": "to_name",
            "label": "To name",
            "value": int(s.get("unnamed_groups") or 0),
        },
        {
            "key": "observations",
            "label": "Observations",
            "value": int(s.get("observations") or 0),
        },
    ]


def last_result_copy(last: dict | None) -> tuple[str, str]:
    """(body, hint) for the Last result card. Never invents a match."""
    if not last:
        return SHELL_LAST_EMPTY, SHELL_LAST_HINT
    status = str(last.get("status") or "").upper()
    reason = (last.get("reason") or "").strip()
    if status in {"UNAVAILABLE", "ERROR", "TIMEOUT", "CANCELLED"}:
        body = reason or "It did not run."
        return body, SHELL_LAST_HINT
    if status == "NO_RESULT":
        return "Nothing matched.", SHELL_LAST_HINT
    if status == "SUCCESS":
        n = int(last.get("item_count") or len(last.get("items") or []) or 0)
        if n <= 0:
            return "Nothing matched.", SHELL_LAST_HINT
        label = last.get("summary") or f"{n} result{'s' if n != 1 else ''}"
        return str(label), SHELL_LAST_HINT
    return reason or SHELL_LAST_EMPTY, SHELL_LAST_HINT


LENS_UNDERSTANDING_TITLE = "Available understanding"
_LENS_IDS = (
    "ocr",
    "barcode",
    "grounding",
    "visual_embedding",
    "translation",
    "vlm",
    "lkg",
)


def lens_understanding_rows(
    *,
    report: list[dict] | None = None,
    model_overrides: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Soft rows for the Lens pane. Labels from the catalog — never capability ids."""
    from semblon.runtime_contract import default_catalog, status_report

    if report is not None:
        rows = list(report)
    else:
        overrides = model_overrides if model_overrides is not None else probe_model_overrides()
        rows = list(status_report(model_overrides=overrides or None))
    by_id = {str(r.get("capability_id") or ""): r for r in rows}
    catalog = {spec.id: spec for spec in default_catalog().specs}
    out: list[dict[str, str]] = []
    for cap_id in _LENS_IDS:
        row = by_id.get(cap_id) or {}
        spec = catalog.get(cap_id)
        label = (spec.label if spec else cap_id) or cap_id
        model = str(row.get("model_state") or "MISSING")
        out.append(
            {
                "id": cap_id,
                "label": label,
                "state": _state_label(model),
            }
        )
    return out


def enrich_summary_counts(store: Path, summary: dict | None) -> dict | None:
    """Add photos / video_frames / observations when the store can answer."""
    if summary is None:
        return None
    out = dict(summary)
    path = Path(store)
    if not path.is_file():
        return out
    import sqlite3

    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        photos = int(
            conn.execute(
                "SELECT COUNT(*) FROM media WHERE source_type='folder' OR source_type IS NULL OR source_type=''"
            ).fetchone()[0]
        )
        try:
            videos = int(
                conn.execute(
                    "SELECT COUNT(*) FROM media WHERE source_type='video'"
                ).fetchone()[0]
            )
        except sqlite3.OperationalError:
            videos = 0
        try:
            observations = int(
                conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            )
        except sqlite3.OperationalError:
            observations = int(out.get("faces") or 0)
        try:
            video_frames = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM observations o
                    JOIN media m ON m.media_id = o.media_id
                    WHERE m.source_type='video'
                    """
                ).fetchone()[0]
            )
        except sqlite3.OperationalError:
            video_frames = videos
        out["photos"] = photos if photos else int(out.get("files") or 0)
        out["video_frames"] = video_frames
        out["observations"] = observations
    except sqlite3.OperationalError:
        out.setdefault("photos", int(out.get("files") or 0))
        out.setdefault("video_frames", 0)
        out.setdefault("observations", int(out.get("faces") or 0))
    finally:
        conn.close()
    return out
