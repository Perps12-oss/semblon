"""Inc 8 — SAME_AS between ObjectCluster centroids.

Never links a Person node and never writes identity rows.
"""

from __future__ import annotations

import sqlite3

import numpy as np

from semblon.brain.graph import insert_counted_edge
from semblon.brain.object_cluster import OBJECT_DBSCAN_EPS
from semblon.erasure_intent import ErasureIntent, erasure_authorized

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


def _drop_unprotected_same_as(conn: sqlite3.Connection) -> None:
    """Drop model SAME_AS edges. Edges with human: evidence stay."""
    intent = ErasureIntent(
        requestor="system",
        scope="library",
        reason="rebuild object SAME_AS links",
        authorized_by="brain.same_as.link_same_as",
    )
    with erasure_authorized(intent):
        conn.execute(
            """
            DELETE FROM brain_edges
             WHERE edge_type='SAME_AS'
               AND id NOT IN (
                    SELECT e.id
                      FROM brain_edges e
                      JOIN brain_evidence ev ON ev.edge_id = e.id
                     WHERE e.edge_type='SAME_AS'
                       AND ev.claim_key LIKE 'human:%'
               )
            """
        )


def _protected_pairs(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    rows = conn.execute(
        """
        SELECT source_node_id, target_node_id
          FROM brain_edges
         WHERE edge_type='SAME_AS'
        """
    ).fetchall()
    for src, tgt in rows:
        left, right = int(src), int(tgt)
        pairs.add((left, right) if left < right else (right, left))
    return pairs


def link_same_as(conn: sqlite3.Connection, *, eps: float = OBJECT_DBSCAN_EPS) -> dict:
    """Candidate links between object clusters inside eps. Persons are ignored.

    A human same or different decision is evidence, not a distance. Those
    edges are kept, and the model does not write a new link over that pair.
    """
    _drop_unprotected_same_as(conn)
    protected = _protected_pairs(conn)
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
            if (int(left_id), int(right_id)) in protected:
                continue
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
