"""Inc 8 — SAME_AS between ObjectCluster centroids.

Never links a Person node and never writes identity rows.
"""

from __future__ import annotations

import sqlite3

import numpy as np

from semblon.brain.graph import delete_edges_of_type, insert_counted_edge
from semblon.brain.object_cluster import OBJECT_DBSCAN_EPS

# Pairwise int8 dots stay in memory only under this count.
PAIR_CAP = 2000


def _distance(left: bytes, right: bytes) -> float | None:
    a = np.frombuffer(left, dtype=np.int8).astype(np.float32)
    b = np.frombuffer(right, dtype=np.int8).astype(np.float32)
    if a.shape != b.shape or a.size == 0:
        return None
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return None
    return float(1.0 - np.dot(a, b) / (na * nb))


def link_same_as(conn: sqlite3.Connection, *, eps: float = OBJECT_DBSCAN_EPS) -> dict:
    """Candidate links between object clusters inside eps. Persons are ignored."""
    delete_edges_of_type(
        conn,
        "SAME_AS",
        reason="rebuild object SAME_AS links",
        authorized_by="brain.same_as.link_same_as",
    )
    rows = conn.execute(
        """
        SELECT id, canonical_embedding
          FROM brain_nodes
         WHERE node_type='ObjectCluster'
           AND canonical_embedding IS NOT NULL
         ORDER BY id
        """
    ).fetchall()
    if len(rows) > PAIR_CAP:
        conn.commit()
        return {
            "clusters": len(rows),
            "edges": 0,
            "skipped": True,
            "reason": "cluster count above pairwise cap",
        }
    edges = 0
    for i, (left_id, left_blob) in enumerate(rows):
        for right_id, right_blob in rows[i + 1 :]:
            dist = _distance(left_blob, right_blob)
            if dist is None or dist > eps:
                continue
            insert_counted_edge(
                conn,
                source_id=int(left_id),
                target_id=int(right_id),
                edge_type="SAME_AS",
                confidence=max(0.0, 1.0 - dist),
                support_count=1,
            )
            edges += 1
    conn.commit()
    return {"clusters": len(rows), "edges": edges, "skipped": False, "eps": eps}
