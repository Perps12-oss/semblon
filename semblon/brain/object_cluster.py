"""Batch ObjectCluster rebuild over stored DINOv2 region embeddings.

Zero new inference. Uses in-house DBSCAN (not the hdbscan package).
Schedule: on-demand batch only — not on ingest (Inc 11 owns incremental).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import numpy as np

from semblon.brain.confidence import (
    CONFIDENCE_MODEL_VERSION,
    object_cluster_confidence,
    object_cluster_status,
)
from semblon.brain.edges import require_node_type
from semblon.brain.graph import (
    clear_object_clusters,
    edge_exists,
    ensure_photo_node,
    upsert_edge,
)
from semblon.brain.quantize import mean_l2_int8
from semblon.cluster import _dbscan_precomputed

# Cosine distance band for L2 region vectors (1 - dot). Provisional.
OBJECT_DBSCAN_EPS = 0.35
OBJECT_DBSCAN_MIN_SAMPLES = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_region_members(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT e.embedding_id, e.embedding, e.embedding_dim, e.pack_id, e.modality,
               o.media_id
          FROM embeddings e
          JOIN observation_items oi ON oi.item_id = e.item_id
          JOIN observations o ON o.observation_id = oi.observation_id
         WHERE e.modality IN ('region', 'region_patch')
         ORDER BY e.pack_id, e.embedding_id
        """
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "embedding_id": r[0],
                "embedding": r[1],
                "dim": int(r[2]),
                "pack_id": r[3],
                "modality": r[4],
                "media_id": r[5],
            }
        )
    return out


def _cluster_pack(members: list[dict], *, eps: float, min_samples: int) -> list[list[dict]]:
    """Return groups of members. Noise points each become a singleton group."""
    n = len(members)
    if n == 0:
        return []
    if n == 1:
        return [members]

    dim = members[0]["dim"]
    mat = np.stack(
        [np.frombuffer(m["embedding"], dtype=np.float32) for m in members],
        axis=0,
    )
    # L2 assumed; cosine distance = 1 - dot
    dots = mat @ mat.T
    dist = np.clip(1.0 - dots, 0.0, 2.0).astype(np.float64)
    np.fill_diagonal(dist, 0.0)
    labels = _dbscan_precomputed(dist, eps=eps, min_samples=min_samples)

    groups: dict[int, list[dict]] = {}
    singletons: list[list[dict]] = []
    for i, lab in enumerate(labels.tolist()):
        if lab < 0:
            singletons.append([members[i]])
        else:
            groups.setdefault(int(lab), []).append(members[i])
    return list(groups.values()) + singletons


def rebuild_object_clusters(
    conn: sqlite3.Connection,
    *,
    eps: float = OBJECT_DBSCAN_EPS,
    min_samples: int = OBJECT_DBSCAN_MIN_SAMPLES,
) -> dict:
    """Batch-only rebuild. Clears prior ObjectCluster nodes then recreates."""
    require_node_type("ObjectCluster")
    clear_object_clusters(conn)
    members = _load_region_members(conn)
    by_pack: dict[str, list[dict]] = {}
    for m in members:
        by_pack.setdefault(m["pack_id"], []).append(m)

    clusters_created = 0
    edges_created = 0
    now = _now()

    for pack_id, pack_members in by_pack.items():
        # Align dims within pack
        dim = pack_members[0]["dim"]
        pack_members = [m for m in pack_members if m["dim"] == dim]
        for group in _cluster_pack(pack_members, eps=eps, min_samples=min_samples):
            count = len(group)
            blob = mean_l2_int8([g["embedding"] for g in group], dim)
            conf = object_cluster_confidence(count)
            status = object_cluster_status(count)
            label = f"obj:{pack_id[:16]}:{clusters_created}"
            cur = conn.execute(
                """INSERT INTO brain_nodes(
                     node_type, label, canonical_embedding, embedding_pack_hash,
                     confidence, status, first_seen, last_seen, member_count,
                     confidence_model_version, created_at, updated_at)
                   VALUES ('ObjectCluster',?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    label,
                    blob,
                    pack_id,
                    conf,
                    status,
                    now,
                    now,
                    count,
                    CONFIDENCE_MODEL_VERSION,
                    now,
                    now,
                ),
            )
            cluster_id = int(cur.lastrowid)
            clusters_created += 1
            media_ids = {g["media_id"] for g in group}
            for media_id in media_ids:
                photo_id = ensure_photo_node(conn, str(media_id))
                upsert_edge(
                    conn,
                    source_id=photo_id,
                    target_id=cluster_id,
                    edge_type="HAS_OBJECT",
                    confidence=conf,
                )
                edges_created += 1

    conn.commit()
    return {
        "members": len(members),
        "clusters": clusters_created,
        "has_object_edges": edges_created,
        "eps": eps,
        "min_samples": min_samples,
        "confidence_model_version": CONFIDENCE_MODEL_VERSION,
    }


def approximate_predict(
    conn: sqlite3.Connection,
    vector: bytes,
    *,
    media_id: str,
    dim: int,
    eps: float = OBJECT_DBSCAN_EPS,
) -> dict:
    """Assign one float32 L2 vector to the nearest ObjectCluster centroid.

    Inc 11. Compares against the stored int8 centroid. Does not run DBSCAN,
    does not write region embeddings, and does not hook product ingest.
    """
    query = np.frombuffer(vector, dtype=np.float32).copy()
    if query.shape != (dim,):
        raise ValueError(f"dim mismatch: expected {dim}, got {query.shape[0]}")
    norm = float(np.linalg.norm(query))
    if norm == 0.0:
        return {"matched": False, "reason": "zero vector", "eps": eps}
    query = query / norm
    rows = conn.execute(
        """
        SELECT id, canonical_embedding, confidence
          FROM brain_nodes
         WHERE node_type='ObjectCluster'
           AND canonical_embedding IS NOT NULL
        """
    ).fetchall()
    best_id: int | None = None
    best_dist: float | None = None
    best_conf = 1.0
    for node_id, blob, confidence in rows:
        if blob is None or len(blob) != dim:
            continue
        centre = np.frombuffer(blob, dtype=np.int8).astype(np.float32) / 127.0
        centre_norm = float(np.linalg.norm(centre))
        if centre_norm == 0.0:
            continue
        dist = float(1.0 - float(np.dot(query, centre / centre_norm)))
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_id = int(node_id)
            best_conf = float(confidence)
    if best_id is None or best_dist is None or best_dist > eps:
        return {"matched": False, "distance": best_dist, "eps": eps}
    photo_id = ensure_photo_node(conn, str(media_id))
    created = False
    if not edge_exists(conn, photo_id, best_id, "HAS_OBJECT"):
        upsert_edge(
            conn,
            source_id=photo_id,
            target_id=best_id,
            edge_type="HAS_OBJECT",
            confidence=best_conf,
        )
        created = True
    conn.commit()
    return {
        "matched": True,
        "cluster_id": best_id,
        "distance": best_dist,
        "created": created,
        "eps": eps,
    }
