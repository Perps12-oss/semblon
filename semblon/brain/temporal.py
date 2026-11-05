"""Inc 6 — TEMPORAL_NEXT along Photo nodes ordered by media mtime."""

from __future__ import annotations

import sqlite3

from semblon.brain.graph import delete_edges_of_type, upsert_edge


def rebuild_temporal_next(conn: sqlite3.Connection) -> dict:
    """Replace the TEMPORAL_NEXT chain. Does not write identity."""
    delete_edges_of_type(
        conn,
        "TEMPORAL_NEXT",
        reason="rebuild temporal chain",
        authorized_by="brain.temporal.rebuild_temporal_next",
    )
    rows = conn.execute(
        """
        SELECT n.id
          FROM brain_nodes n
          LEFT JOIN media m ON m.media_id = n.label
         WHERE n.node_type='Photo'
         ORDER BY (m.mtime_ns IS NULL), m.mtime_ns, COALESCE(m.path, n.label), n.id
        """
    ).fetchall()
    ids = [int(row[0]) for row in rows]
    for source_id, target_id in zip(ids, ids[1:]):
        upsert_edge(
            conn,
            source_id=source_id,
            target_id=target_id,
            edge_type="TEMPORAL_NEXT",
            confidence=1.0,
        )
    conn.commit()
    return {"photos": len(ids), "edges": max(0, len(ids) - 1)}
