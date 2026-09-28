"""Write visual regions onto existing observation_items. No new columns. No persons.

Does not import user_region or OpenCV. Identity tables are only read to prove
they did not change.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np

from semblon.store import connect, init_db
from semblon.visual.engine import Analysis

PROVIDER = "visual.region"


def _ensure_observation(conn, *, media_id: str, run_id: str, frame_id: int | None = None, t_ms: int | None = None) -> str:
    if frame_id is None:
        row = conn.execute(
            """SELECT observation_id FROM observations
               WHERE media_id=? AND run_id=? AND frame_id IS NULL""",
            (media_id, run_id),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT observation_id FROM observations
               WHERE media_id=? AND run_id=? AND frame_id=?""",
            (media_id, run_id, frame_id),
        ).fetchone()
    if row is not None:
        return str(row[0])
    oid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
        (oid, media_id, frame_id, t_ms, run_id),
    )
    return oid


def _replace_previous(conn, *, media_id: str, run_id: str, frame_id: int | None) -> None:
    if frame_id is None:
        rows = conn.execute(
            """SELECT i.item_id FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE i.provider=? AND i.run_id=? AND o.media_id=? AND o.frame_id IS NULL""",
            (PROVIDER, run_id, media_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT i.item_id FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE i.provider=? AND i.run_id=? AND o.media_id=? AND o.frame_id=?""",
            (PROVIDER, run_id, media_id, frame_id),
        ).fetchall()
    ids = [row[0] for row in rows]
    if not ids:
        return
    marks = ",".join("?" * len(ids))
    conn.execute(
        f"DELETE FROM relationships WHERE src_item_id IN ({marks}) OR dst_item_id IN ({marks})",
        [*ids, *ids],
    )
    conn.execute(f"DELETE FROM track_members WHERE item_id IN ({marks})", ids)
    conn.execute(f"DELETE FROM group_members WHERE item_id IN ({marks})", ids)
    conn.execute(f"DELETE FROM embeddings WHERE item_id IN ({marks})", ids)
    conn.execute(f"DELETE FROM observation_items WHERE item_id IN ({marks})", ids)


def persist_analysis(
    store: Path,
    analysis: Analysis,
    *,
    media_id: str,
    run_id: str,
    frame_id: int | None = None,
    t_ms: int | None = None,
) -> dict:
    """Persist the hover slice. The owner map is derived and is not a column."""
    path = Path(store)
    conn = connect(path)
    init_db(conn)
    try:
        persons_before = int(conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0])
        faces_before = int(conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0])
        face_emb_before = int(
            conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
        )
        _replace_previous(conn, media_id=media_id, run_id=run_id, frame_id=frame_id)
        observation_id = _ensure_observation(
            conn, media_id=media_id, run_id=run_id, frame_id=frame_id, t_ms=t_ms
        )
        id_to_item: dict[int, str] = {}
        for region in analysis.regions:
            payload = region.to_payload()
            payload["rows"] = analysis.rows.get(region.region_id, {})
            payload["map_revision"] = analysis.revision
            payload["frame_id"] = frame_id
            x, y, bw, bh = region.bbox
            item_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
                   bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json, face_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item_id,
                    observation_id,
                    run_id,
                    "object",
                    PROVIDER,
                    float(x),
                    float(y),
                    float(x + bw),
                    float(y + bh),
                    region.confidence,
                    json.dumps(payload),
                    None,
                ),
            )
            id_to_item[region.region_id] = item_id
        for src, dst, kind, weight in analysis.edges:
            if src not in id_to_item or dst not in id_to_item:
                continue
            if kind not in {"contains", "overlaps"}:
                continue
            conn.execute(
                """INSERT INTO relationships(relationship_id, run_id, kind, src_item_id, dst_item_id,
                   evidence_json, confirmed) VALUES (?,?,?,?,?,?,0)""",
                (
                    uuid.uuid4().hex,
                    run_id,
                    kind,
                    id_to_item[src],
                    id_to_item[dst],
                    json.dumps({"weight": weight, "visual": True, "revision": analysis.revision}),
                ),
            )
        conn.commit()
        persons_after = int(conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0])
        faces_after = int(conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0])
        face_emb_after = int(
            conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
        )
    finally:
        conn.close()
    if persons_after != persons_before:
        raise RuntimeError("visual persist must not create persons")
    if faces_after != faces_before:
        raise RuntimeError("visual persist must not create faces")
    if face_emb_after != face_emb_before:
        raise RuntimeError("visual persist must not write face embeddings")
    return {
        "items": len(id_to_item),
        "edges": sum(1 for edge in analysis.edges if edge[0] in id_to_item and edge[1] in id_to_item),
        "persons": persons_after,
        "faces": faces_after,
        "revision": analysis.revision,
        "level": analysis.level,
    }


def visual_already_stored(items, media_id: str) -> bool:
    for item in items or []:
        if item.get("media_id") == media_id and item.get("provider") == PROVIDER:
            return True
    return False


def should_submit_visual(*, busy: bool, items, media_id: str | None, run_id: str | None) -> bool:
    """Home's open-photo gate. Pointer movement never reaches this."""
    if busy or not media_id or not run_id:
        return False
    return not visual_already_stored(items, media_id)


def load_hover_rows(store: Path, *, media_id: str, run_id: str) -> list[dict]:
    conn = connect(store)
    try:
        rows = conn.execute(
            """SELECT i.item_id, i.payload_json, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE i.provider=? AND i.run_id=? AND o.media_id=?""",
            (PROVIDER, run_id, media_id),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for item_id, payload_json, x1, y1, x2, y2 in rows:
        payload = json.loads(payload_json or "{}")
        out.append(
            {
                "item_id": item_id,
                "label": payload.get("selected_label"),
                "kind": payload.get("kind"),
                "rows": payload.get("rows") or {},
                "region_id": payload.get("region_id"),
                "bbox": [x1, y1, x2, y2],
                "parent_id": payload.get("parent_id"),
                "parent_label": payload.get("parent_label"),
                "method": payload.get("method"),
            }
        )
    return out


def load_scene_inputs(store: Path, *, media_id: str, run_id: str, height: int, width: int) -> dict:
    """Face boxes and user boxes already in the store. No new identity."""
    path = Path(store)
    if not path.is_file():
        return {"face_boxes": [], "user_regions": []}
    conn = connect(path)
    try:
        faces = conn.execute(
            """SELECT f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2
               FROM faces f
               JOIN observations o ON o.observation_id = f.observation_id
               WHERE o.media_id=? AND f.run_id=?""",
            (media_id, run_id),
        ).fetchall()
        boxes = conn.execute(
            """SELECT i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2, i.payload_json
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE i.provider='user_box' AND o.media_id=? AND i.run_id=?""",
            (media_id, run_id),
        ).fetchall()
    finally:
        conn.close()
    face_boxes = []
    for x1, y1, x2, y2 in faces:
        face_boxes.append((int(x1), int(y1), max(1, int(round(x2 - x1))), max(1, int(round(y2 - y1)))))
    user_regions = []
    for x1, y1, x2, y2, payload_json in boxes:
        mask = np.zeros((height, width), dtype=bool)
        xa, ya = max(0, int(x1)), max(0, int(y1))
        xb, yb = min(width, int(round(x2))), min(height, int(round(y2)))
        if xb > xa and yb > ya:
            mask[ya:yb, xa:xb] = True
            payload = json.loads(payload_json or "{}")
            user_regions.append({"mask": mask, "label": payload.get("named")})
    return {"face_boxes": face_boxes, "user_regions": user_regions}
