"""Inc 9 — HAS_FACE from an existing faces.cluster_id.

Reads face rows. Does not change scores, cluster membership, or person_id.
"""

from __future__ import annotations

import sqlite3

from semblon.brain.graph import edge_exists, ensure_labeled_node, ensure_photo_node, upsert_edge


def link_faces(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT o.media_id, f.cluster_id
          FROM faces f
          JOIN observations o ON o.observation_id = f.observation_id
         WHERE f.cluster_id IS NOT NULL AND f.cluster_id != ''
        """
    ).fetchall()
    created = 0
    for media_id, cluster_id in rows:
        photo_id = ensure_photo_node(conn, str(media_id))
        face_id = ensure_labeled_node(conn, "FaceCluster", str(cluster_id))
        if edge_exists(conn, photo_id, face_id, "HAS_FACE"):
            continue
        upsert_edge(
            conn,
            source_id=photo_id,
            target_id=face_id,
            edge_type="HAS_FACE",
            confidence=1.0,
        )
        created += 1
    conn.commit()
    return {"clustered_faces": len(rows), "edges_new": created}
