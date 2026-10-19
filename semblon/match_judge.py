"""Check the top matches after the first grid. Not identity.

Uses colour and a local pixel description. A missing VLM stays skipped.
Does not write the store. Does not invent a product or a person.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from semblon.observers import color_histogram


def judge_matches(
    store: Path,
    *,
    crop,
    items: list[dict] | None,
    limit: int = 20,
    cancelled=None,
) -> dict:
    """Rescore fused hits against the query crop. Empty input is skipped."""
    pool = [item for item in (items or []) if isinstance(item, dict) and item.get("media_id")]
    if crop is None or not pool:
        return {"status": "SKIPPED", "items": list(items or []), "judge": "skipped"}
    query_hist = _hist(crop)
    query_concepts = _concepts(crop)
    scored: list[dict] = []
    compared = 0
    for item in pool[: max(1, int(limit))]:
        if cancelled is not None and cancelled():
            return {"status": "CANCELLED", "items": list(items or []), "judge": "kept"}
        pair = _pair_crop(store, item)
        base = _unit(item.get("score"))
        if pair is None:
            row = dict(item)
            row["judge_score"] = base
            scored.append(row)
            continue
        color = _hist_dot(query_hist, _hist(pair))
        overlap = _concept_overlap(query_concepts, _concepts(pair))
        row = dict(item)
        row["judge_score"] = 0.50 * base + 0.35 * color + 0.15 * overlap
        row["score"] = float(row["judge_score"])
        scored.append(row)
        compared += 1
    scored.sort(
        key=lambda row: (
            -float(row.get("score") or 0.0),
            str(row.get("media_id") or ""),
        )
    )
    return {
        "status": "SUCCESS" if compared else "SKIPPED",
        "items": scored,
        "judge": "ready" if compared else "skipped",
        "compared": compared,
    }


def _hist(image) -> np.ndarray:
    raw = color_histogram(image)
    return np.frombuffer(raw, dtype=np.float32).copy()


def _hist_dot(left: np.ndarray, right: np.ndarray) -> float:
    if left.size == 0 or right.size == 0 or left.size != right.size:
        return 0.0
    return max(0.0, min(1.0, float(np.dot(left, right))))


def _concepts(image) -> set[str]:
    try:
        from semblon.lens import describe_pixels

        rec = describe_pixels(image)
    except Exception:
        return set()
    if not isinstance(rec, dict):
        return set()
    return {str(item).strip().lower() for item in (rec.get("concepts") or []) if str(item).strip()}


def _concept_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / float(len(left | right))


def _unit(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0:
        return 0.0
    return number if number <= 1.0 else min(1.0, number / 4.0)


def _pair_crop(store: Path, item: dict):
    media_id = str(item.get("media_id") or "").strip()
    path = _media_path(store, media_id)
    if path is None:
        return None
    from semblon.region_search import crop_bgr

    width, height = _media_size(store, media_id)
    norm = item.get("match_norm") if isinstance(item.get("match_norm"), (list, tuple)) else None
    if norm and len(norm) == 4 and width and height and any(float(v) > 0 for v in norm):
        x = max(0, int(round(float(norm[0]) * width)))
        y = max(0, int(round(float(norm[1]) * height)))
        w = max(1, int(round(float(norm[2]) * width)))
        h = max(1, int(round(float(norm[3]) * height)))
    else:
        x, y, w, h = 0, 0, int(width or 8), int(height or 8)
    try:
        return crop_bgr(path, x, y, w, h)
    except Exception:
        return None


def _media_path(store: Path, media_id: str) -> Path | None:
    if not media_id or not Path(store).is_file():
        return None
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT path FROM media WHERE media_id=?", (media_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    path = Path(row[0])
    return path if path.is_file() else None


def _media_size(store: Path, media_id: str) -> tuple[int, int]:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT width, height FROM media WHERE media_id=?",
            (media_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return 0, 0
    return int(row[0] or 0), int(row[1] or 0)
