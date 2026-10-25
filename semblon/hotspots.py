"""Tap targets for the picture view: a few well-spaced dots over things worth finding again.

Pure geometry on boxes the library already holds. Nothing here reads the disk, loads a
detector, or names anyone. A face dot only ever leads to a look-alike search.
"""

from __future__ import annotations

MAX_HOTSPOTS = 8
_MIN_AREA = 0.0009  # skip specks smaller than ~3% of each side
_MAX_OVERLAP = 0.45
_MIN_GAP = 0.07  # dot centres closer than this (fraction of the photo) read as one

_TEXT_JOIN = 0.04  # writing blocks closer than this (fraction of the photo) become one dot

_PLAIN = {"face": "a face", "text": "some writing"}
_KIND_WORD = {"face": "Look-alikes", "text": "Writing"}


def kind_word(box: dict) -> str:
    return _KIND_WORD.get(str(box.get("kind") or ""), "Thing")


def _gap(a: dict, b: dict) -> float:
    dx = max(0.0, max(a["nx"], b["nx"]) - min(a["nx"] + a["nw"], b["nx"] + b["nw"]))
    dy = max(0.0, max(a["ny"], b["ny"]) - min(a["ny"] + a["nh"], b["ny"] + b["nh"]))
    return max(dx, dy)


def merge_writing(boxes: list[dict]) -> list[dict]:
    """Neighbouring writing blocks read as one piece of writing, so they get one dot."""
    text = [dict(b) for b in boxes if b.get("kind") == "text" and b.get("snap")]
    rest = [b for b in boxes if not (b.get("kind") == "text" and b.get("snap"))]
    groups: list[list[dict]] = []
    for box in sorted(text, key=lambda b: str(b.get("id") or "")):
        near = [g for g in groups if any(_gap(box, m) < _TEXT_JOIN for m in g)]
        merged = [box]
        for g in near:
            merged.extend(g)
            groups.remove(g)
        groups.append(merged)
    out = list(rest)
    for g in groups:
        if len(g) == 1:
            out.append(g[0])
            continue
        x1 = min(float(m["nx"]) for m in g)
        y1 = min(float(m["ny"]) for m in g)
        x2 = max(float(m["nx"]) + float(m["nw"]) for m in g)
        y2 = max(float(m["ny"]) + float(m["nh"]) for m in g)
        lead = max(g, key=lambda m: float(m["nw"]) * float(m["nh"]))
        out.append({**lead, "nx": x1, "ny": y1, "nw": x2 - x1, "nh": y2 - y1, "joined": True})
    return out


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
        for box in merge_writing(boxes)
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
                "word": kind_word(box),
                "joined": bool(box.get("joined")),
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
