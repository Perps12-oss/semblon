"""Parts inside a user highlight. Observation only. Not identity."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.query_spec import empty_parts
from semblon.store import connect_readonly

_OBJECT_SKIP = {"region", "user_region", "barcode"}
_NANODET = "opencv-zoo-nanodet"


def propose_parts(
    store: Path,
    *,
    media_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    crop=None,
    limit: int = 3,
) -> list[dict]:
    """Whole area plus up to three parts the user can search instead."""
    parts = empty_parts()
    width = max(1, int(w))
    height = max(1, int(h))
    found: list[dict] = []
    found.extend(_stored_parts(store, media_id, x, y, w, h))
    if len(found) < limit and crop is not None:
        found.extend(_crop_parts(crop, x, y))
    seen: set[str] = set()
    index = 0
    for item in found:
        label = str(item.get("label") or "").strip()
        key = label.lower()
        if not label or key in seen or key in _OBJECT_SKIP:
            continue
        seen.add(key)
        box = item.get("box") or [x, y, w, h]
        px, py, pw, ph = _clip_box(box, x, y, width, height)
        if pw < 4 or ph < 4:
            continue
        parts.append(
            {
                "index": index,
                "label": _plain_label(label, item.get("kind")),
                "kind": str(item.get("kind") or "object"),
                "norm": _norm_on_media(store, media_id, px, py, pw, ph),
                "box": [px, py, pw, ph],
                "selected": False,
            }
        )
        index += 1
        if index >= limit:
            break
    return parts


def select_part(parts: list[dict], part_index: int) -> dict:
    chosen = None
    for item in parts:
        item["selected"] = int(item.get("index", -2)) == int(part_index)
        if item["selected"]:
            chosen = item
    if chosen is None and parts:
        parts[0]["selected"] = True
        chosen = parts[0]
    return chosen or parts[0]


def _plain_label(label: str, kind: str | None) -> str:
    text = label.strip()
    if not text:
        return "This part"
    if str(kind or "") == "text":
        return text[:24]
    return text[:1].upper() + text[1:]


def _clip_box(box, x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    try:
        bx, by, bw, bh = [int(v) for v in box[:4]]
    except (TypeError, ValueError):
        return int(x), int(y), int(w), int(h)
    x1 = max(int(x), bx)
    y1 = max(int(y), by)
    x2 = min(int(x) + int(w), bx + max(1, bw))
    y2 = min(int(y) + int(h), by + max(1, bh))
    if x2 <= x1 or y2 <= y1:
        return int(x), int(y), int(w), int(h)
    return x1, y1, x2 - x1, y2 - y1


def _norm_on_media(store: Path, media_id: str, x: int, y: int, w: int, h: int) -> list[float] | None:
    path = Path(store)
    if not path.is_file() or not media_id:
        return None
    conn = connect_readonly(path.resolve())
    try:
        row = conn.execute(
            "SELECT width, height FROM media WHERE media_id=?",
            (media_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    width = float(row[0] or 0)
    height = float(row[1] or 0)
    if width <= 0 or height <= 0:
        return None
    return [x / width, y / height, w / width, h / height]


def _stored_parts(store: Path, media_id: str, x: int, y: int, w: int, h: int) -> list[dict]:
    path = Path(store)
    if not path.is_file() or not media_id:
        return []
    conn = connect_readonly(path.resolve())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT i.kind, i.provider, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2,
                      i.score, i.payload_json
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE o.media_id=? AND i.kind IN ('object', 'text')
               ORDER BY i.score DESC""",
            (media_id,),
        ).fetchall()
    finally:
        conn.close()
    cx = float(x) + float(w) / 2.0
    cy = float(y) + float(h) / 2.0
    found = []
    for row in rows:
        try:
            x1 = float(row["bbox_x1"])
            y1 = float(row["bbox_y1"])
            x2 = float(row["bbox_x2"])
            y2 = float(row["bbox_y2"])
        except (TypeError, ValueError):
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        if not (x1 <= cx <= x2 and y1 <= cy <= y2) and not _overlap(x, y, w, h, x1, y1, x2 - x1, y2 - y1):
            continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        kind = str(row["kind"] or "")
        if kind == "object" and str(row["provider"] or "") != _NANODET:
            continue
        if kind == "object":
            label = str(payload.get("label") or payload.get("class") or "").strip()
        else:
            label = str(payload.get("text") or "").strip()
        if not label:
            continue
        found.append(
            {
                "label": label,
                "kind": kind,
                "box": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
            }
        )
    return found


def _overlap(x: int, y: int, w: int, h: int, ox: float, oy: float, ow: float, oh: float) -> bool:
    return not (x + w <= ox or ox + ow <= x or y + h <= oy or oy + oh <= y)


def _crop_parts(crop, origin_x: int, origin_y: int) -> list[dict]:
    try:
        from semblon.object_nanodet import detect_objects
        from semblon.object_pack import probe_nanodet_status
    except Exception:
        return []
    ready, _note = probe_nanodet_status()
    if not ready:
        return []
    try:
        hits = detect_objects(crop)
    except Exception:
        return []
    found = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        label = str(hit.get("label") or hit.get("class") or "").strip()
        if not label or label.lower() in _OBJECT_SKIP:
            continue
        box = hit.get("bbox") or hit.get("box")
        if not isinstance(box, (list, tuple)) or len(box) < 4:
            continue
        x1, y1, x2, y2 = (float(v) for v in box[:4])
        if x2 < x1 or y2 < y1:
            continue
        found.append(
            {
                "label": label,
                "kind": "object",
                "box": [
                    int(origin_x + x1),
                    int(origin_y + y1),
                    max(1, int(round(x2 - x1))),
                    max(1, int(round(y2 - y1))),
                ],
            }
        )
    return found
