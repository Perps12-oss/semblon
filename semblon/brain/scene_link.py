"""Inc 10 — HAS_SCENE from existing scene embeddings, plus a gap query.

brain_gaps is a SELECT. This module does not create a table.
"""

from __future__ import annotations

import sqlite3

from semblon.brain.graph import edge_exists, ensure_labeled_node, ensure_photo_node, upsert_edge


def link_scenes(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT DISTINCT o.media_id
          FROM embeddings e
          JOIN observation_items oi ON oi.item_id = e.item_id
          JOIN observations o ON o.observation_id = oi.observation_id
         WHERE e.modality = 'scene'
        """
    ).fetchall()
    created = 0
    for (media_id,) in rows:
        photo_id = ensure_photo_node(conn, str(media_id))
        scene_id = ensure_labeled_node(conn, "Scene", str(media_id))
        if edge_exists(conn, photo_id, scene_id, "HAS_SCENE"):
            continue
        upsert_edge(
            conn,
            source_id=photo_id,
            target_id=scene_id,
            edge_type="HAS_SCENE",
            confidence=1.0,
        )
        created += 1
    conn.commit()
    return {"scenes": len(rows), "edges_new": created}


def brain_gaps(conn: sqlite3.Connection) -> dict:
    """Counts of media still missing a link this increment can see.

    tag: no HAS_TAG. scene: a scene embedding and no HAS_SCENE.
    face: a clustered face and no HAS_FACE. face_unclustered is reported
    and left alone.
    """
    tag = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM media m
             WHERE NOT EXISTS (
               SELECT 1
                 FROM brain_nodes photo
                 JOIN brain_edges edge ON edge.source_node_id = photo.id
                WHERE photo.node_type='Photo'
                  AND photo.label = m.media_id
                  AND edge.edge_type='HAS_TAG'
             )
            """
        ).fetchone()[0]
    )
    scene = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM media m
             WHERE EXISTS (
               SELECT 1
                 FROM embeddings e
                 JOIN observation_items oi ON oi.item_id = e.item_id
                 JOIN observations o ON o.observation_id = oi.observation_id
                WHERE o.media_id = m.media_id AND e.modality = 'scene'
             )
               AND NOT EXISTS (
               SELECT 1
                 FROM brain_nodes photo
                 JOIN brain_edges edge ON edge.source_node_id = photo.id
                WHERE photo.node_type='Photo'
                  AND photo.label = m.media_id
                  AND edge.edge_type='HAS_SCENE'
             )
            """
        ).fetchone()[0]
    )
    face = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM media m
             WHERE EXISTS (
               SELECT 1
                 FROM faces f
                 JOIN observations o ON o.observation_id = f.observation_id
                WHERE o.media_id = m.media_id
                  AND f.cluster_id IS NOT NULL
                  AND f.cluster_id != ''
             )
               AND NOT EXISTS (
               SELECT 1
                 FROM brain_nodes photo
                 JOIN brain_edges edge ON edge.source_node_id = photo.id
                WHERE photo.node_type='Photo'
                  AND photo.label = m.media_id
                  AND edge.edge_type='HAS_FACE'
             )
            """
        ).fetchone()[0]
    )
    unclustered = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM faces
             WHERE cluster_id IS NULL OR cluster_id = ''
            """
        ).fetchone()[0]
    )
    return {
        "tag": tag,
        "scene": scene,
        "face": face,
        "face_unclustered": unclustered,
    }
