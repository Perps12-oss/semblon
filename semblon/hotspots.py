"""Tap targets for the picture view: a few well-spaced dots over things worth finding again.

Pure geometry on boxes the library already holds. Nothing here reads the disk, loads a
detector, or names anyone. A face dot only ever leads to a look-alike search.
"""

from __future__ import annotations

MAX_HOTSPOTS = 8
_MIN_AREA = 0.0009  # skip specks smaller than ~3% of each side
_MAX_OVERLAP = 0.45
_MIN_GAP = 0.07  # dot centres closer than this (fraction of the photo) read as one

_PLAIN = {"face": "a face", "text": "some writing"}


def label_for(box: dict) -> str:
    kind = str(box.get("kind") or "")
    tag = str(box.get("tag") or "").strip()
    if kind == "face":
        return _PLAIN["face"]
    if kind == "text":
        return _PLAIN["text"]
    return f"a {tag.lower()}" if tag else "this thing"


def _overlap(a: dict, b: dict) -> float:
    ix = max(0.0, min(a["nx"] + a["nw"], b["nx"] + b["nw"]) - max(a["nx"], b["nx"]))
    iy = max(0.0, min(a["ny"] + a["nh"], b["ny"] + b["nh"]) - max(a["ny"], b["ny"]))
    inter = ix * iy
    smaller = min(a["nw"] * a["nh"], b["nw"] * b["nh"])
    return inter / smaller if smaller > 0 else 0.0


def rank_hotspots(boxes: list[dict], limit: int = MAX_HOTSPOTS) -> list[dict]:
    """Biggest searchable areas first, no near-duplicates, at most ``limit`` dots."""
    usable = [
        box
        for box in boxes
        if box.get("snap") and float(box.get("nw") or 0) * float(box.get("nh") or 0) >= _MIN_AREA
    ]
    usable.sort(key=lambda b: (-(float(b["nw"]) * float(b["nh"])), str(b.get("id") or "")))
    kept: list[dict] = []
    for box in usable:
        cx = float(box["nx"]) + float(box["nw"]) / 2
        cy = float(box["ny"]) + float(box["nh"]) / 2
        if any(_overlap(box, other) > _MAX_OVERLAP for other in kept):
            continue
        if any(abs(cx - o["cx"]) < _MIN_GAP and abs(cy - o["cy"]) < _MIN_GAP for o in kept):
            continue
        kept.append(
            {
                "id": str(box.get("id") or ""),
                "kind": str(box.get("kind") or ""),
                "label": label_for(box),
                "cx": cx,
                "cy": cy,
                "nx": float(box["nx"]),
                "ny": float(box["ny"]),
                "nw": float(box["nw"]),
                "nh": float(box["nh"]),
            }
        )
        if len(kept) >= limit:
            break
    return kept
