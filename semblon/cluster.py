"""0.3 cluster: DBSCAN on ok faces. Clusters are not persons."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import numpy as np

from semblon.compare import CompareError, compare
from semblon.store import connect, init_db

# Hypothesis — not frozen. Use review.html to decide whether this survives.
DEFAULT_EPS = 0.40  # distance = 1 - cosine; keep together only if sim >= 0.60
DEFAULT_MIN_SAMPLES = 2
METRIC = "1-dot"


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
        s = 0
        while s < len(seeds):
            q = seeds[s]
            if not visited[q]:
                visited[q] = True
                qn = np.flatnonzero(dist[q] <= eps)
                if qn.size >= min_samples:
                    known = set(seeds)
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


def _clear_run_clusters(conn, run_id: str) -> None:
    rows = conn.execute(
        "SELECT cluster_id FROM clusters WHERE run_id=?", (run_id,)
    ).fetchall()
    ids = [r[0] for r in rows]
    conn.execute("UPDATE faces SET cluster_id=NULL WHERE run_id=?", (run_id,))
    if ids:
        q = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM cluster_person WHERE cluster_id IN ({q})", ids)
        conn.execute("DELETE FROM clusters WHERE run_id=?", (run_id,))


def _load_ok_faces(conn, run_id: str, pack_id: str):
    rows = conn.execute(
        """
        SELECT face_id, embedding, embedding_pack, embedding_dim
        FROM faces
        WHERE run_id=? AND status='ok' AND embedding IS NOT NULL
        ORDER BY face_id
        """,
        (run_id,),
    ).fetchall()
    faces = []
    skipped_pack = 0
    for r in rows:
        if r["embedding_pack"] != pack_id:
            skipped_pack += 1
            continue
        faces.append(r)
    return faces, skipped_pack


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
    faces, skipped_pack = _load_ok_faces(conn, run_id, pack_id)

    t0 = time.perf_counter()
    _clear_run_clusters(conn, run_id)

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
    conn.commit()
    conn.close()
    return {
        "run_id": run_id,
        "pack_id": pack_id,
        "strategy": _strategy(eps, min_samples),
        "ok_faces": len(faces),
        "skipped_pack_mismatch": skipped_pack,
        "clusters": n_clusters,
        "clustered": n_clustered,
        "unassigned": n_noise if faces else 0,
        "eps": eps,
        "min_samples": min_samples,
        "cluster_s": round(elapsed, 3),
    }
