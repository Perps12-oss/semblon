"""Lens mouse-up → persist user box → find similar.

Uses the canonical image-space rectangle already produced by geometry.
Does not remap widget coordinates. Does not create persons or face embeddings.
"""

from __future__ import annotations

from pathlib import Path

from semblon.application import Application
from semblon.region_search import remember_and_find


UNKNOWN_HEADLINE = "Unknown selection"
UNKNOWN_BODY = "We couldn't identify this yet."
SIMILAR_HEADLINE = "Similar images"
SIMILAR_HINT = (
    "These images look visually related to your selection. "
    "Semblon hasn't identified what the thing is."
)
EMPTY_SIMILAR = "No similar images found yet."


def format_similar_lines(result: dict) -> list[str]:
    """Product copy only. No pack / modality / embedding words."""
    similar = result.get("similar") or {}
    region = result.get("region") or {}
    norm = region.get("norm") or {}
    lines = [UNKNOWN_HEADLINE, UNKNOWN_BODY]
    if norm:
        lines.append("Your selection was kept.")
    status = similar.get("status")
    items = list(similar.get("items") or [])
    if status == "SUCCESS" and items:
        lines.append(SIMILAR_HEADLINE)
        lines.append(SIMILAR_HINT)
        n = len(items)
        lines.append(f"{n} similar photo{'s' if n != 1 else ''} in your library.")
        for item in items[:8]:
            media = item.get("media_id") or "photo"
            lines.append(f"  {media}")
    elif status == "NO_RESULT":
        lines.append(EMPTY_SIMILAR)
    elif status == "UNAVAILABLE":
        reason = similar.get("reason") or EMPTY_SIMILAR
        if "embedding" in reason.lower() or "pack" in reason.lower() or "space" in reason.lower():
            lines.append("Similar search needs photos that have already been looked at.")
        else:
            lines.append(reason)
    else:
        lines.append(EMPTY_SIMILAR)
    return lines


def similar_summary(result: dict) -> dict:
    similar = result.get("similar") or {}
    items = list(similar.get("items") or [])
    status = similar.get("status") or "UNAVAILABLE"
    if status == "SUCCESS" and items:
        return {
            "status": "SUCCESS",
            "summary": f"{len(items)} similar photo{'s' if len(items) != 1 else ''}",
            "item_count": len(items),
            "items": items,
            "kind": "similar",
        }
    if status == "NO_RESULT":
        return {
            "status": "NO_RESULT",
            "reason": EMPTY_SIMILAR,
            "item_count": 0,
            "kind": "similar",
        }
    return {
        "status": "UNAVAILABLE",
        "reason": similar.get("reason") or "Similar search did not run.",
        "item_count": 0,
        "kind": "similar",
    }


def remember_selection(
    store: Path,
    *,
    media_id: str,
    image_path: Path | None,
    x: int,
    y: int,
    w: int,
    h: int,
    run_id: str | None = None,
    limit: int = 10,
    app: Application | None = None,
) -> dict:
    """Persist the drawn box and search. Crop uses these exact pixels."""
    if app is not None:
        rec = app.remember_and_find_region(
            media_id,
            x,
            y,
            w,
            h,
            image_path=image_path,
            run_id=run_id,
            limit=limit,
        )
    else:
        rec = remember_and_find(
            Path(store),
            media_id=media_id,
            image_path=image_path,
            x=x,
            y=y,
            w=w,
            h=h,
            run_id=run_id,
            limit=limit,
        )
    similar = rec.get("similar") or {}
    query_pixels = similar.get("query_pixels") or {
        "x": int(x),
        "y": int(y),
        "w": int(w),
        "h": int(h),
    }
    return {
        "region": rec.get("region"),
        "similar": similar,
        "lines": format_similar_lines(rec),
        "summary": similar_summary(rec),
        "rect": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
        "query_pixels": query_pixels,
        "persons": rec.get("persons", 0),
        "entity": False,
        "wrote_embedding": False,
        "box_kept": True,
    }
