"""Graph writer — Photo/Tag nodes and HAS_TAG edges from C1 observations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from semblon.brain.confidence import (
    CONFIDENCE_MODEL_VERSION,
    photo_confidence,
    tag_confidence,
)
from semblon.brain.edges import normalise_tag_label, require_edge_type, require_node_type
from semblon.erasure_intent import ErasureIntent, erasure_authorized


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_photo_node(conn: sqlite3.Connection, media_id: str) -> int:
    require_node_type("Photo")
    row = conn.execute(
        "SELECT id FROM brain_nodes WHERE node_type='Photo' AND label=?",
        (media_id,),
    ).fetchone()
    if row:
        return int(row[0])
    now = _now()
    cur = conn.execute(
        """INSERT INTO brain_nodes(
             node_type, label, canonical_embedding, embedding_pack_hash,
             confidence, status, first_seen, last_seen, member_count,
             confidence_model_version, created_at, updated_at)
           VALUES ('Photo',?,NULL,NULL,?,?,?,?,0,?,?,?)""",
        (
            media_id,
            photo_confidence(),
            "confirmed",
            now,
            now,
            CONFIDENCE_MODEL_VERSION,
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def ensure_tag_node(conn: sqlite3.Connection, label: str) -> int:
    """One Tag node per normalised label (vocabulary, not per-photo)."""
    require_node_type("Tag")
    name = normalise_tag_label(label)
    if not name:
        raise ValueError("empty tag label")
    row = conn.execute(
        "SELECT id, member_count FROM brain_nodes WHERE node_type='Tag' AND label=?",
        (name,),
    ).fetchone()
    now = _now()
    if row:
        return int(row[0])
    cur = conn.execute(
        """INSERT INTO brain_nodes(
             node_type, label, canonical_embedding, embedding_pack_hash,
             confidence, status, first_seen, last_seen, member_count,
             confidence_model_version, created_at, updated_at)
           VALUES ('Tag',?,NULL,NULL,?,?,?,?,0,?,?,?)""",
        (
            name,
            tag_confidence(0),
            "candidate",
            now,
            now,
            CONFIDENCE_MODEL_VERSION,
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def upsert_edge(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    target_id: int,
    edge_type: str,
    confidence: float = 1.0,
) -> int:
    require_edge_type(edge_type)
    now = _now()
    row = conn.execute(
        """SELECT id, support_count FROM brain_edges
           WHERE source_node_id=? AND target_node_id=? AND edge_type=?""",
        (source_id, target_id, edge_type),
    ).fetchone()
    if row:
        eid, support = int(row[0]), int(row[1]) + 1
        conn.execute(
            """UPDATE brain_edges
                  SET support_count=?, last_seen=?, updated_at=?, confidence=?
                WHERE id=?""",
            (support, now, now, float(confidence), eid),
        )
        return eid
    cur = conn.execute(
        """INSERT INTO brain_edges(
             source_node_id, target_node_id, edge_type, confidence,
             support_count, contradict_count, first_seen, last_seen,
             contradiction_state, created_at, updated_at)
           VALUES (?,?,?,?,1,0,?,?, 'none',?,?)""",
        (source_id, target_id, edge_type, float(confidence), now, now, now, now),
    )
    return int(cur.lastrowid)


def _refresh_tag_aggregate(conn: sqlite3.Connection, tag_id: int) -> None:
    """Tag member_count is the number of HAS_TAG edges, each support_count=1."""
    n = int(
        conn.execute(
            """SELECT COUNT(*) FROM brain_edges
               WHERE target_node_id=? AND edge_type='HAS_TAG'""",
            (tag_id,),
        ).fetchone()[0]
    )
    status = "tentative" if n >= 2 else "candidate"
    conn.execute(
        """UPDATE brain_nodes
              SET member_count=?, confidence=?, status=?, updated_at=?,
                  confidence_model_version=?
            WHERE id=?""",
        (n, tag_confidence(n), status, _now(), CONFIDENCE_MODEL_VERSION, tag_id),
    )


def _c1_tag_scores(conn: sqlite3.Connection, media_id: str) -> dict[str, float]:
    """One score per normalised label on this photo. Duplicates do not stack."""
    scores: dict[str, float] = {}
    rows = conn.execute(
        """SELECT payload_json FROM brain_observations
           WHERE capability_id='C1' AND media_id=?""",
        (media_id,),
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row[0] or "{}")
        except json.JSONDecodeError:
            continue
        tag_list = payload.get("tags") if isinstance(payload, dict) else None
        if not isinstance(tag_list, list):
            continue
        for tag in tag_list:
            label = tag.get("label") if isinstance(tag, dict) else tag
            name = normalise_tag_label(str(label or ""))
            if not name:
                continue
            score = float(tag.get("score") or 1.0) if isinstance(tag, dict) else 1.0
            prev = scores.get(name)
            if prev is None or score > prev:
                scores[name] = score
    return scores


def _reconcile_media_ids(
    conn: sqlite3.Connection, photo_id: str | None
) -> list[str]:
    if photo_id is not None:
        return [str(photo_id)]
    found: set[str] = set()
    for row in conn.execute(
        "SELECT DISTINCT media_id FROM brain_observations WHERE capability_id='C1'"
    ):
        found.add(str(row[0]))
    for row in conn.execute(
        """SELECT p.label
             FROM brain_nodes p
             JOIN brain_edges e ON e.source_node_id = p.id
            WHERE p.node_type='Photo'
              AND e.edge_type='HAS_TAG'
              AND p.label IS NOT NULL"""
    ):
        found.add(str(row[0]))
    return sorted(found)


def _replace_has_tag(
    conn: sqlite3.Connection,
    source_id: int,
    target_id: int,
    confidence: float,
) -> int:
    """One HAS_TAG edge. support_count stays 1; a repeat call does not add support."""
    require_edge_type("HAS_TAG")
    now = _now()
    row = conn.execute(
        """SELECT id FROM brain_edges
           WHERE source_node_id=? AND target_node_id=? AND edge_type='HAS_TAG'""",
        (source_id, target_id),
    ).fetchone()
    if row:
        eid = int(row[0])
        conn.execute(
            """UPDATE brain_edges
                  SET support_count=1, confidence=?, last_seen=?, updated_at=?
                WHERE id=?""",
            (float(confidence), now, now, eid),
        )
        return eid
    cur = conn.execute(
        """INSERT INTO brain_edges(
             source_node_id, target_node_id, edge_type, confidence,
             support_count, contradict_count, first_seen, last_seen,
             contradiction_state, created_at, updated_at)
           VALUES (?, ?, 'HAS_TAG', ?, 1, 0, ?, ?, 'none', ?, ?)""",
        (source_id, target_id, float(confidence), now, now, now, now),
    )
    return int(cur.lastrowid)


def _reconcile_photo_tags(conn: sqlite3.Connection, media_id: str) -> int:
    """Delete this photo's HAS_TAG edges, then insert the current C1 labels."""
    scores = _c1_tag_scores(conn, media_id)
    photo_row = conn.execute(
        "SELECT id FROM brain_nodes WHERE node_type='Photo' AND label=?",
        (media_id,),
    ).fetchone()
    if photo_row is None and not scores:
        return 0
    if photo_row is None:
        photo_node_id = ensure_photo_node(conn, media_id)
        previous: set[int] = set()
    else:
        photo_node_id = int(photo_row[0])
        previous = {
            int(row[0])
            for row in conn.execute(
                """SELECT target_node_id FROM brain_edges
                   WHERE edge_type='HAS_TAG' AND source_node_id=?""",
                (photo_node_id,),
            )
        }
        conn.execute(
            """DELETE FROM brain_edges
               WHERE edge_type='HAS_TAG' AND source_node_id=?""",
            (photo_node_id,),
        )
    affected = set(previous)
    inserted = 0
    for label, score in scores.items():
        tag_id = ensure_tag_node(conn, label)
        _replace_has_tag(conn, photo_node_id, tag_id, score)
        affected.add(tag_id)
        inserted += 1
    for tag_id in affected:
        _refresh_tag_aggregate(conn, tag_id)
    return inserted


def sync_tags_from_observations(
    conn: sqlite3.Connection,
    photo_id: str | None = None,
) -> dict:
    """Reconcile Photo→HAS_TAG→Tag with current C1 observations.

    Each photo is delete-then-insert inside one transaction. A HAS_TAG edge
    is one observation of one label: support_count is 1 and is not incremented.
    Tag member_count is the count of those edges, and confidence is
    ``tag_confidence(member_count)``. Calling this again with the same
    observations leaves that confidence unchanged. Labels removed from the
    C1 payload lose their edge.

    ``photo_id`` is a media id. Omit it to reconcile every C1 photo and any
    photo that still has a HAS_TAG edge.
    """
    media_ids = _reconcile_media_ids(conn, photo_id)
    intent = ErasureIntent(
        requestor="system",
        scope="library",
        reason="reconcile tag edges from C1 observations",
        authorized_by="brain.graph.sync_tags_from_observations",
    )
    inserted = 0
    with erasure_authorized(intent):
        with conn:
            for media_id in media_ids:
                inserted += _reconcile_photo_tags(conn, media_id)
    return {
        "photos": conn.execute(
            "SELECT COUNT(*) FROM brain_nodes WHERE node_type='Photo'"
        ).fetchone()[0],
        "tags": conn.execute(
            "SELECT COUNT(*) FROM brain_nodes WHERE node_type='Tag'"
        ).fetchone()[0],
        "has_tag_edges": conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='HAS_TAG'"
        ).fetchone()[0],
        "edges_upserted": inserted,
    }


def clear_object_clusters(conn: sqlite3.Connection) -> None:
    """Batch rebuild helper — remove ObjectCluster nodes (edges CASCADE)."""
    intent = ErasureIntent(
        requestor="system",
        scope="library",
        reason="batch object cluster rebuild",
        authorized_by="brain.graph.clear_object_clusters",
    )
    with erasure_authorized(intent):
        conn.execute("DELETE FROM brain_nodes WHERE node_type='ObjectCluster'")
    conn.commit()
