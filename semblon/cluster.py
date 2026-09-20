"""0.3 cluster: DBSCAN on ok faces. Clusters are not persons."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import numpy as np

from semblon.compare import CompareError, compare
from semblon.store import connect, init_db

# Frozen by S1 golden 20260913T153515Z-1e915abe. Do not retune to beautify clusters.
DEFAULT_EPS = 0.40  # distance = 1 - cosine; keep together only if sim >= 0.60
DEFAULT_MIN_SAMPLES = 2
METRIC = "1-dot"
MAX_DBSCAN_FACES = 15000


class ClusterError(ValueError):
    pass


def _dbscan_precomputed(dist: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    n = int(dist.shape[0])
    labels = np.full(n, -1, dtype=np.int32)
    visited = np.zeros(n, dtype=bool)
    cid = 0
    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neigh = np.flatnonzero(dist[i] <= eps)
        if neigh.size < min_samples:
            continue
        labels[i] = cid
        seeds = neigh.tolist()
        known = set(seeds)
        s = 0
        while s < len(seeds):
            q = seeds[s]
            if not visited[q]:
                visited[q] = True
                qn = np.flatnonzero(dist[q] <= eps)
                if qn.size >= min_samples:
                    for x in qn.tolist():
                        if x not in known:
                            seeds.append(x)
                            known.add(x)
            if labels[q] == -1:
                labels[q] = cid
            s += 1
        cid += 1
    return labels


def _strategy(eps: float, min_samples: int) -> str:
    return f"dbscan:eps={eps}:min_samples={min_samples}:metric={METRIC}"


def _review_locks(conn, run_id: str) -> tuple[set[str], set[str]]:
    """Faces and clusters covered by human decisions. Re-cluster must not move these.

    Auto clusters are computed and replaceable. A merge/split/ignore decision
    is durable: decisions.cluster_id REFERENCES clusters(cluster_id) with no
    ON DELETE CASCADE. That FK is the guard — do not DELETE every cluster
    for a run after a review decision exists.
    """
    faces: set[str] = set()
    clusters: set[str] = set()
    for d in conn.execute("SELECT * FROM decisions WHERE run_id=?", (run_id,)):
        if d["cluster_id"]:
            clusters.add(d["cluster_id"])
        if d["face_id"]:
            faces.add(d["face_id"])
        try:
            pol = json.loads(d["policy_json"] or "{}")
        except json.JSONDecodeError:
            pol = {}
        if not isinstance(pol, dict):
            continue
        for key in ("survivor", "from_cluster", "new_cluster"):
            if pol.get(key):
                clusters.add(str(pol[key]))
        for cid in pol.get("merged") or []:
            clusters.add(str(cid))
        extra_faces = pol.get("moved_faces")
        if isinstance(extra_faces, list):
            for fid in extra_faces:
                faces.add(str(fid))
        for fid in pol.get("faces") or []:
            if isinstance(fid, str):
                faces.add(fid)
    for r in conn.execute(
        """SELECT cluster_id FROM clusters
           WHERE run_id=? AND status IN ('merged','split','ignored')""",
        (run_id,),
    ):
        clusters.add(r[0])
    if clusters:
        q = ",".join("?" * len(clusters))
        for r in conn.execute(
            f"SELECT face_id FROM faces WHERE cluster_id IN ({q})",
            list(clusters),
        ):
            faces.add(r[0])
    return faces, clusters


def _clear_unprotected_clusters(conn, run_id: str, locked_faces: set[str], locked_clusters: set[str]) -> None:
    rows = conn.execute(
        "SELECT cluster_id FROM clusters WHERE run_id=?", (run_id,)
    ).fetchall()
    drop = [r[0] for r in rows if r[0] not in locked_clusters]
    if locked_faces:
        conn.execute("DROP TABLE IF EXISTS tmp_locked_faces")
        conn.execute("CREATE TEMP TABLE tmp_locked_faces(face_id TEXT PRIMARY KEY)")
        conn.executemany(
            "INSERT OR IGNORE INTO tmp_locked_faces(face_id) VALUES (?)",
            ((fid,) for fid in locked_faces),
        )
        conn.execute(
            """
            UPDATE faces
            SET cluster_id=NULL
            WHERE run_id=? AND face_id NOT IN (SELECT face_id FROM tmp_locked_faces)
            """,
            (run_id,),
        )
        conn.execute("DROP TABLE IF EXISTS tmp_locked_faces")
    else:
        conn.execute("UPDATE faces SET cluster_id=NULL WHERE run_id=?", (run_id,))
    if drop:
        conn.execute("DROP TABLE IF EXISTS tmp_drop_clusters")
        conn.execute("CREATE TEMP TABLE tmp_drop_clusters(cluster_id TEXT PRIMARY KEY)")
        conn.executemany(
            "INSERT OR IGNORE INTO tmp_drop_clusters(cluster_id) VALUES (?)",
            ((cid,) for cid in drop),
        )
        conn.execute(
            "DELETE FROM cluster_person WHERE cluster_id IN (SELECT cluster_id FROM tmp_drop_clusters)"
        )
        conn.execute(
            "DELETE FROM clusters WHERE cluster_id IN (SELECT cluster_id FROM tmp_drop_clusters)"
        )
        conn.execute("DROP TABLE IF EXISTS tmp_drop_clusters")


def _load_ok_faces(conn, run_id: str, pack_id: str):
    total = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM faces f
            JOIN observations o ON o.observation_id = f.observation_id
            JOIN media m ON m.media_id = o.media_id
            WHERE f.run_id=? AND f.status='ok' AND f.embedding IS NOT NULL
              AND m.source_type = 'folder'
            """,
            (run_id,),
        ).fetchone()[0]
    )
    rows = conn.execute(
        """
        SELECT f.face_id, f.embedding, f.embedding_pack, f.embedding_dim
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.run_id=? AND f.status='ok' AND f.embedding IS NOT NULL
          AND f.embedding_pack=?
          AND m.source_type = 'folder'
        ORDER BY f.face_id
        """,
        (run_id, pack_id),
    ).fetchall()
    return rows, max(0, total - len(rows))


def _pairwise_min(faces_in_cluster, pack_id: str) -> tuple[float | None, tuple[str, str] | None]:
    best = None
    pair = None
    n = len(faces_in_cluster)
    for i in range(n):
        a = faces_in_cluster[i]
        for j in range(i + 1, n):
            b = faces_in_cluster[j]
            try:
                s = compare(
                    pack_id,
                    a["embedding_dim"],
                    a["embedding"],
                    pack_id,
                    b["embedding_dim"],
                    b["embedding"],
                )
            except CompareError:
                continue
            if best is None or s < best:
                best = float(s)
                pair = (a["face_id"], b["face_id"])
    return best, pair


def cluster_run(
    store: Path,
    run_id: str,
    eps: float = DEFAULT_EPS,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> dict:
    if eps <= 0:
        raise ClusterError("eps must be > 0")
    if min_samples < 1:
        raise ClusterError("min_samples must be >= 1")

    conn = connect(store)
    init_db(conn)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise ClusterError(f"unknown run: {run_id}")

    pack_id = run["pack_id"]
    dim = int(run["embedding_dim"])
    locked_faces, locked_clusters = _review_locks(conn, run_id)
    faces, skipped_pack = _load_ok_faces(conn, run_id, pack_id)
    n_ok_total = len(faces)
    faces = [f for f in faces if f["face_id"] not in locked_faces]
    n_ok_active = len(faces)
    if n_ok_active > MAX_DBSCAN_FACES:
        conn.close()
        raise ClusterError(
            f"too many active still faces for in-memory DBSCAN ({n_ok_active} > {MAX_DBSCAN_FACES})"
        )

    t0 = time.perf_counter()
    _clear_unprotected_clusters(conn, run_id, locked_faces, locked_clusters)

    n_clustered = 0
    n_noise = 0
    n_clusters = 0

    if faces:
        mats = []
        keep = []
        for f in faces:
            if int(f["embedding_dim"]) != dim:
                continue
            if len(f["embedding"]) != 4 * dim:
                continue
            vec = np.frombuffer(f["embedding"], dtype=np.float32)
            if vec.size != dim:
                continue
            mats.append(vec.copy())
            keep.append(f)
        faces = keep
        if faces:
            X = np.stack(mats, axis=0)
            sims = X @ X.T
            dist = np.clip(1.0 - sims, 0.0, 2.0).astype(np.float64, copy=False)
            np.fill_diagonal(dist, 0.0)
            labels = _dbscan_precomputed(dist, eps=eps, min_samples=min_samples)

            by_label: dict[int, list[int]] = {}
            for i, lab in enumerate(labels.tolist()):
                if lab < 0:
                    n_noise += 1
                    continue
                by_label.setdefault(lab, []).append(i)

            for lab in sorted(by_label):
                idxs = by_label[lab]
                members = [faces[i] for i in idxs]
                min_intra, _pair = _pairwise_min(members, pack_id)
                centroid = np.mean(np.stack([mats[i] for i in idxs], axis=0), axis=0)
                nrm = float(np.linalg.norm(centroid))
                if nrm > 0:
                    centroid = centroid / nrm
                cid = uuid.uuid4().hex
                conn.execute(
                    """INSERT INTO clusters(cluster_id, run_id, strategy, face_count,
                       centroid, min_intra, status)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        cid,
                        run_id,
                        _strategy(eps, min_samples),
                        len(members),
                        centroid.astype(np.float32).tobytes(),
                        min_intra,
                        "auto",
                    ),
                )
                for m in members:
                    conn.execute(
                        "UPDATE faces SET cluster_id=? WHERE face_id=?",
                        (cid, m["face_id"]),
                    )
                n_clustered += len(members)
                n_clusters += 1

    elapsed = time.perf_counter() - t0
    from semblon.observers import snapshot_groups_from_clusters

    groups = snapshot_groups_from_clusters(conn, run_id)
    conn.commit()
    conn.close()
    return {
        "run_id": run_id,
        "pack_id": pack_id,
        "strategy": _strategy(eps, min_samples),
        "ok_faces": n_ok_total,
        "ok_faces_active": n_ok_active,
        "skipped_pack_mismatch": skipped_pack,
        "review_locked": len(locked_faces),
        "clusters": n_clusters,
        "clustered": n_clustered,
        "unassigned": n_noise,
        "eps": eps,
        "min_samples": min_samples,
        "cluster_s": round(elapsed, 3),
        "groups": groups.get("groups"),
        "note": "clusters are groups, not persons",
    }
