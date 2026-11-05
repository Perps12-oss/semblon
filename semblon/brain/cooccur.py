"""Inc 7 — CO_OCCURS between Tag nodes that share a photo."""

from __future__ import annotations

import sqlite3

from semblon.brain.graph import delete_edges_of_type, insert_counted_edge


def rebuild_cooccurs(conn: sqlite3.Connection) -> dict:
    """One undirected pair per tag set. support_count is the photo count."""
    delete_edges_of_type(
        conn,
        "CO_OCCURS",
        reason="rebuild tag co-occurrence",
        authorized_by="brain.cooccur.rebuild_cooccurs",
    )
    rows = conn.execute(
        """
        SELECT e.source_node_id, e.target_node_id
          FROM brain_edges e
          JOIN brain_nodes tag ON tag.id = e.target_node_id
         WHERE e.edge_type='HAS_TAG' AND tag.node_type='Tag'
        """
    ).fetchall()
    by_photo: dict[int, list[int]] = {}
    for source_id, target_id in rows:
        by_photo.setdefault(int(source_id), []).append(int(target_id))
    counts: dict[tuple[int, int], int] = {}
    for tags in by_photo.values():
        unique = sorted(set(tags))
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                key = (left, right)
                counts[key] = counts.get(key, 0) + 1
    for (left, right), support in counts.items():
        insert_counted_edge(
            conn,
            source_id=left,
            target_id=right,
            edge_type="CO_OCCURS",
            confidence=1.0,
            support_count=support,
        )
    conn.commit()
    return {"photos": len(by_photo), "pairs": len(counts)}
