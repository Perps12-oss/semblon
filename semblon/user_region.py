"""Persist a user-drawn Lens box as an Observation.

The box is authoritative. Similarity and capability hits are optional extras.
This module never writes persons, faces.person_id, or embeddings.modality='face'.
No new columns. Unknown remains valid until a human names the payload.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from semblon.observers import persist_item
from semblon.process import latest_run_id
from semblon.store import connect, init_db

PROVIDER = "user_box"
KIND = "object"


class RegionError(ValueError):
    pass


def _norm(x: float, y: float, w: float, h: float, image_w: int, image_h: int) -> dict:
    if image_w <= 0 or image_h <= 0:
        raise RegionError("media has no size")
    x1 = max(0.0, min(1.0, float(x) / float(image_w)))
    y1 = max(0.0, min(1.0, float(y) / float(image_h)))
    x2 = max(0.0, min(1.0, float(x + w) / float(image_w)))
    y2 = max(0.0, min(1.0, float(y + h) / float(image_h)))
    if x2 <= x1 or y2 <= y1:
        raise RegionError("region has no area")
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _ensure_observation(conn, *, media_id: str, run_id: str) -> str:
    row = conn.execute(
        """SELECT observation_id FROM observations
           WHERE media_id=? AND run_id=? AND frame_id IS NULL""",
        (media_id, run_id),
    ).fetchone()
    if row is not None:
        return str(row[0])
    oid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,NULL,NULL,?)",
        (oid, media_id, run_id),
    )
    return oid


def persist_user_region(
    store: Path,
    *,
    media_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    run_id: str | None = None,
    report=None,
) -> dict:
    """Write the user's rectangle. Capability hits are extra, never identity."""
    if w <= 0 or h <= 0:
        raise RegionError("region has no area")
    path = Path(store)
    conn = connect(path)
    init_db(conn)
    rid = run_id or latest_run_id(path)
    if not rid:
        conn.close()
        raise RegionError("no run on store")
    media = conn.execute(
        "SELECT media_id, width, height FROM media WHERE media_id=?",
        (media_id,),
    ).fetchone()
    if media is None:
        conn.close()
        raise RegionError(f"unknown media: {media_id}")
    image_w = int(media[1] or 0)
    image_h = int(media[2] or 0)
    norm = _norm(x, y, w, h, image_w, image_h)
    observation_id = _ensure_observation(conn, media_id=media_id, run_id=rid)
    payload = {
        "class": "user_region",
        "named": None,
        "identity": "not facekit",
        "contract_status": "SUCCESS",
        "norm": norm,
        "pixels": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
    }
    item_id = persist_item(
        conn,
        observation_id=observation_id,
        run_id=rid,
        kind=KIND,
        provider=PROVIDER,
        payload=payload,
        bbox=(float(x), float(y), float(x + w), float(y + h)),
        score=1.0,
    )
    extra = {"object": 0, "text": 0, "embedding": 0}
    if report is not None:
        from semblon.lens import persist_successes

        extra = persist_successes(conn, observation_id=observation_id, run_id=rid, report=report)
    conn.commit()
    persons = int(conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0])
    face_emb = int(
        conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    )
    conn.close()
    if persons != 0:
        raise RuntimeError("persist_user_region must not create persons")
    return {
        "item_id": item_id,
        "observation_id": observation_id,
        "run_id": rid,
        "media_id": media_id,
        "named": None,
        "norm": norm,
        "hits": extra,
        "persons": 0,
        "face_embeddings": face_emb,
    }


def list_user_regions(store: Path, *, run_id: str | None = None) -> list[dict]:
    """Unnamed and named user boxes. None of these are persons."""
    path = Path(store)
    if not path.is_file():
        return []
    conn = connect(path)
    rid = run_id or latest_run_id(path)
    sql = """SELECT i.item_id, i.observation_id, i.run_id, o.media_id, i.payload_json,
                    i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2
             FROM observation_items i
             JOIN observations o ON o.observation_id = i.observation_id
             WHERE i.provider=? AND i.kind=?"""
    args: list = [PROVIDER, KIND]
    if rid:
        sql += " AND i.run_id=?"
        args.append(rid)
    sql += " ORDER BY i.rowid DESC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    out = []
    for row in rows:
        try:
            payload = json.loads(row[4] or "{}")
        except json.JSONDecodeError:
            payload = {}
        out.append(
            {
                "item_id": row[0],
                "observation_id": row[1],
                "run_id": row[2],
                "media_id": row[3],
                "named": payload.get("named"),
                "norm": payload.get("norm"),
                "bbox": [row[5], row[6], row[7], row[8]],
                "entity": False,
                "person": False,
            }
        )
    return out


def name_user_region(store: Path, item_id: str, name: str) -> dict:
    """Human label on the observation payload. Does not create a person."""
    label = (name or "").strip()
    if not label:
        raise RegionError("name is empty")
    conn = connect(Path(store))
    row = conn.execute(
        "SELECT payload_json, provider FROM observation_items WHERE item_id=?",
        (item_id,),
    ).fetchone()
    if row is None:
        conn.close()
        raise RegionError(f"unknown region: {item_id}")
    if row[1] != PROVIDER:
        conn.close()
        raise RegionError("not a user region")
    try:
        payload = json.loads(row[0] or "{}")
    except json.JSONDecodeError:
        payload = {}
    payload["named"] = label
    payload["identity"] = "not facekit"
    conn.execute(
        "UPDATE observation_items SET payload_json=? WHERE item_id=?",
        (json.dumps(payload), item_id),
    )
    conn.commit()
    persons = int(conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0])
    conn.close()
    return {"item_id": item_id, "named": label, "persons": persons, "entity": False}
