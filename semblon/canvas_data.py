"""UI-free canvas overlay payload. The Tk workspace is a client.

Cluster is not a person. Track is not a person. Does not import tkinter.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.process import latest_run_id
from semblon.state_triple import (
    media_inspector_triple_line,
    triples_for_board,
)

class CanvasError(ValueError):
    pass

CANVAS_NOTE = (
    "Canvas overlays observations. Face identity stays FaceKit. "
    "Canvas never writes faces.person_id. Track ≠ person. Cluster ≠ person. "
    "Media cards expose Artifact 2 state triple (Ingest, Analysis, Identity)."
)

def face_evidence_tag(face: dict) -> str:
    """Evidence-axis label for a face box (R3-BRIEF). Does not read person_id."""
    from semblon.r3_chrome import face_evidence_label

    return face_evidence_label(face)

def load_canvas(store: Path, run_id: str | None = None) -> dict:
    """Overlay payload: media + boxes + persisted track lanes. Cluster ≠ person."""
    store = Path(store)
    if not store.is_file():
        raise CanvasError(f"store not found: {store}")
    conn = sqlite3.connect(f"file:{store.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    rid = run_id or latest_run_id(store, with_faces=True) or latest_run_id(store)
    if rid is None:
        conn.close()
        raise CanvasError("store has no runs")
    try:
        media = conn.execute(
            """SELECT DISTINCT m.media_id, m.path, m.source_type
               FROM media m
               JOIN observations o ON o.media_id = m.media_id
               WHERE o.run_id=?
               ORDER BY m.path""",
            (rid,),
        ).fetchall()
        faces = conn.execute(
            """SELECT f.face_id, f.observation_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
                      f.status, f.cluster_id, f.person_id, o.media_id, o.frame_id, o.t_ms
               FROM faces f JOIN observations o ON o.observation_id=f.observation_id
               WHERE f.run_id=?""",
            (rid,),
        ).fetchall()
    except sqlite3.DatabaseError as e:
        conn.close()
        raise CanvasError(f"canvas load failed: {e}") from e
    warnings: list[str] = []
    items = []
    tracks = []
    track_members = []
    try:
        items = conn.execute(
            """SELECT i.item_id, i.kind, i.provider, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2,
                      i.score, i.payload_json, o.media_id
               FROM observation_items i JOIN observations o ON o.observation_id=i.observation_id
               WHERE i.run_id=?""",
            (rid,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        warnings.append(f"items unavailable: {e}")
    try:
        tracks = conn.execute(
            "SELECT track_id, media_id, kind, t_ms_start, t_ms_end, item_count FROM tracks WHERE run_id=?",
            (rid,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        warnings.append(f"tracks unavailable: {e}")
    try:
        track_members = conn.execute(
            """
            SELECT tm.track_id, tm.item_id, oi.face_id, oi.observation_id, o.media_id
            FROM track_members tm
            JOIN tracks t ON t.track_id = tm.track_id
            JOIN observation_items oi ON oi.item_id = tm.item_id
            JOIN observations o ON o.observation_id = oi.observation_id
            WHERE t.run_id=?
            """,
            (rid,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        warnings.append(f"track memberships unavailable: {e}")
    decisions: list[dict] = []
    clusters: list[dict] = []
    persons: list[dict] = []
    run_finished = None
    try:
        decisions = [
            dict(r)
            for r in conn.execute(
                "SELECT kind, face_id, person_id, cluster_id, policy_json, run_id "
                "FROM decisions WHERE run_id=?",
                (rid,),
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        warnings.append(f"decisions unavailable: {e}")
    try:
        clusters = [
            dict(r)
            for r in conn.execute(
                "SELECT cluster_id, status FROM clusters WHERE run_id=?",
                (rid,),
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        warnings.append(f"clusters unavailable: {e}")
    try:
        persons = [
            dict(r)
            for r in conn.execute(
                "SELECT person_id, display_name FROM persons ORDER BY display_name"
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        warnings.append(f"persons unavailable: {e}")
    try:
        run_row = conn.execute(
            "SELECT finished_at FROM runs WHERE run_id=?", (rid,)
        ).fetchone()
        if run_row is not None:
            run_finished = run_row["finished_at"] is not None
    except sqlite3.OperationalError as e:
        warnings.append(f"run status unavailable: {e}")
    conn.close()
    lane_by_face: dict[str, str] = {}
    lane_by_item: dict[str, str] = {}
    for row in track_members:
        d = dict(row)
        lane_by_item[d["item_id"]] = d["track_id"]
        if d.get("face_id"):
            lane_by_face[d["face_id"]] = d["track_id"]
    note = CANVAS_NOTE
    if warnings:
        note = note + " " + " | ".join(warnings)
    return {
        "run_id": rid,
        "media": [dict(r) for r in media],
        "faces": [dict(r) for r in faces],
        "items": [
            {**dict(r), "payload": json.loads(r["payload_json"] or "{}")}
            for r in items
        ],
        "tracks": [dict(r) for r in tracks],
        "track_members": [dict(r) for r in track_members],
        "track_lane_by_face": lane_by_face,
        "track_lane_by_item": lane_by_item,
        "decisions": decisions,
        "clusters": clusters,
        "persons": persons,
        "run_finished": run_finished,
        "note": note,
    }

def overlay_boxes(board: dict, media_id: str) -> list[dict]:
    """Display boxes for one media. Never includes person_id in the payload."""
    boxes = []
    lane_by_face = board.get("track_lane_by_face") or {}
    lane_by_item = board.get("track_lane_by_item") or {}
    for f in board.get("faces") or []:
        if f.get("media_id") != media_id:
            continue
        lane = lane_by_face.get(f.get("face_id"))
        tag = face_evidence_tag(f)
        if lane:
            tag = f"{tag} lane={lane}"
        boxes.append(
            {
                "kind": "face",
                "id": f.get("face_id"),
                "bbox": [f.get("bbox_x1"), f.get("bbox_y1"), f.get("bbox_x2"), f.get("bbox_y2")],
                "tag": tag,
                "color": "#2e8b57",
            }
        )
    for it in board.get("items") or []:
        if it.get("media_id") != media_id or it.get("kind") == "face":
            continue
        if it.get("bbox_x1") is None:
            continue
        payload = it.get("payload") if isinstance(it.get("payload"), dict) else None
        if payload is None:
            raw_payload = it.get("payload_json")
            if isinstance(raw_payload, str) and raw_payload:
                try:
                    import json

                    parsed = json.loads(raw_payload)
                    payload = parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    payload = {}
            else:
                payload = {}
        if payload.get("display") is False:
            continue
        lane = lane_by_item.get(it.get("item_id"))
        tag = it.get("provider") or it.get("kind") or "item"
        if lane:
            tag = f"{tag} lane={lane}"
        boxes.append(
            {
                "kind": it.get("kind"),
                "id": it.get("item_id"),
                "bbox": [it.get("bbox_x1"), it.get("bbox_y1"), it.get("bbox_x2"), it.get("bbox_y2")],
                "tag": tag,
                "color": "#c47a1a",
            }
        )
    return boxes

def _cluster_status_map(board: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in board.get("clusters") or []:
        cid = c.get("cluster_id")
        if cid:
            out[str(cid)] = str(c.get("status") or "auto")
    return out

def media_state_triples(board: dict, media_rows: list[dict] | None = None) -> dict:
    """Artifact 2 triples for board media. Read-only; never writes person_id."""
    return triples_for_board(
        board,
        media_rows=media_rows,
        decisions=board.get("decisions"),
        cluster_status=_cluster_status_map(board),
        run_finished=board.get("run_finished"),
    )

def media_inspector_lines(board: dict, media_id: str | None) -> list[str]:
    """Inspector evidence lines for one media selection. Group ≠ person.

    Labels distinguish Evidence (machine) from Proposed action (human).
    Actual verb buttons live on Home Inspector; this is read-only chrome.
    """
    from semblon.r3_chrome import chrome_legend_lines, face_display_state

    if not media_id:
        return [
            "Evidence relationship (machine)",
            board.get("note") or CANVAS_NOTE,
            f"run={board.get('run_id')}",
            f"media={len(board.get('media') or [])}  faces={len(board.get('faces') or [])}",
            *chrome_legend_lines()[:3],
            "Proposed action (human): use Home Inspector verbs",
            "Merge observations ≠ Assign to person",
        ]
    media = next((m for m in (board.get("media") or []) if m.get("media_id") == media_id), None)
    faces = [f for f in (board.get("faces") or []) if f.get("media_id") == media_id]
    items = [i for i in (board.get("items") or []) if i.get("media_id") == media_id]
    tracks = [t for t in (board.get("tracks") or []) if t.get("media_id") == media_id]
    clustered = sum(1 for f in faces if f.get("cluster_id"))
    unassigned = sum(1 for f in faces if not f.get("cluster_id"))
    cluster_ids = sorted({f.get("cluster_id") for f in faces if f.get("cluster_id")})
    triples = media_state_triples(board, [media] if media else [])
    triple = triples.get(media_id) if media_id else None
    display_counts: dict[str, int] = {}
    for f in faces:
        label = face_display_state(f)
        display_counts[label] = display_counts.get(label, 0) + 1
    display_bits = "  ".join(f"{k}={v}" for k, v in sorted(display_counts.items())) or "none"
    lines = [
        "Evidence relationship (machine)",
        f"path={media.get('path') if media else '?'}",
        f"source_type={media.get('source_type') if media else '?'}",
        f"faces={len(faces)}  clustered={clustered}  unassigned={unassigned}",
        f"cluster membership: {', '.join(c[:12] for c in cluster_ids) or 'none'}",
        f"display: {display_bits}",
        f"items={len(items)}  tracks={len(tracks)}  (track ≠ person)",
        "Boxes/tracks only. Group ≠ person. Similarity is not identity.",
        "Proposed action (human): Home Inspector — Merge · Assign · Split · Name · Rule out · Ignore",
        "Merge observations ≠ Assign to person",
        CANVAS_NOTE,
    ]
    if triple is not None:
        # After source_type (index 2): Evidence, path, source, then triple.
        lines.insert(3, media_inspector_triple_line(triple))
    if not faces:
        # After faces= line: index 4 without triple; index 5 when triple shifted faces.
        insert_at = 5 if triple is not None else 4
        lines.insert(insert_at, "Zero faces — still Library (not failed ingest)")
    return lines
