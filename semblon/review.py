"""Review ops: name / merge / split / ignore / note / rule-out (flagged).

Invariant: cluster → review → person → name.
Ruled out is experimental: set SEMBLON_RULED_OUT=1 (see docs/CONTRACTS-RULED-OUT.md).
Human corrections are decisions (evidence), not training.
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from semblon.compare import CompareError, compare
from semblon.gates import RULED_OUT, enabled as gate_enabled, require_human_note
from semblon.store import connect, init_db

_ENTERED_S3_LOCK = threading.Lock()
_ENTERED_S3: set[str] = set()
_SQL_IN_CHUNK = 500


class ReviewError(ValueError):
    pass


def _memory_snapshot(store: Path, run_id: str) -> dict:
    try:
        from semblon.observers import snapshot_memory_graph

        return snapshot_memory_graph(store, run_id)
    except Exception as e:  # noqa: BLE001 — snapshot must not block review
        print(f"memory_snapshot failed: {e}", file=sys.stderr)
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _warn_enter_s3(store: Path, run_id: str) -> dict | None:
    """Observatory auto-evoke when starting S3 work. Warn only — never refuse."""
    key = f"{Path(store).resolve()}|{run_id}"
    with _ENTERED_S3_LOCK:
        if key in _ENTERED_S3:
            return None
        _ENTERED_S3.add(key)
    try:
        from semblon.observatory import enter_stage

        rec = enter_stage(store, run_id, "S3", promote=False)
    except Exception as e:  # noqa: BLE001 — observatory must not block review
        print(f"observatory: {e}", file=sys.stderr)
        return None
    verdict = rec.get("verdict")
    notes = rec.get("notes") or []
    if verdict == "not_measurable":
        print(
            "observatory: S1 golden missing — not_measurable (review continues)",
            file=sys.stderr,
        )
    elif verdict == "regression":
        print(
            "observatory: S1 golden shows regression (warning; review continues)",
            file=sys.stderr,
        )
        for n in notes:
            print(f"observatory: {n}", file=sys.stderr)
    elif notes:
        for n in notes:
            print(f"observatory: {n}", file=sys.stderr)
    return rec


def _require_run(conn, run_id: str):
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise ReviewError(f"unknown run: {run_id}")
    return run


def _require_cluster(conn, run_id: str, cluster_id: str):
    row = conn.execute(
        "SELECT * FROM clusters WHERE cluster_id=? AND run_id=?",
        (cluster_id, run_id),
    ).fetchone()
    if row is None:
        raise ReviewError(f"unknown cluster for run: {cluster_id}")
    return row


def _faces_in_cluster(conn, cluster_id: str):
    return conn.execute(
        """
        SELECT face_id, embedding, embedding_pack, embedding_dim, person_id, status
        FROM faces WHERE cluster_id=?
        ORDER BY face_id
        """,
        (cluster_id,),
    ).fetchall()


def _person_links(conn, cluster_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT person_id FROM cluster_person WHERE cluster_id=? ORDER BY person_id",
        (cluster_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _exec_in_chunks(conn, sql_prefix: str, ids: list[str], params_prefix: tuple = ()) -> None:
    """Run UPDATE/DELETE … IN (…) in chunks (SQLite parameter limits)."""
    for i in range(0, len(ids), _SQL_IN_CHUNK):
        chunk = ids[i : i + _SQL_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        conn.execute(f"{sql_prefix} ({placeholders})", (*params_prefix, *chunk))


def _pairwise_min(faces, pack_id: str) -> float | None:
    best = None
    n = len(faces)
    for i in range(n):
        a = faces[i]
        if a["embedding"] is None or a["embedding_pack"] != pack_id:
            continue
        for j in range(i + 1, n):
            b = faces[j]
            if b["embedding"] is None or b["embedding_pack"] != pack_id:
                continue
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
    return best


def _cross_min(faces_a, faces_b, pack_id: str) -> float | None:
    best = None
    for a in faces_a:
        if a["embedding"] is None or a["embedding_pack"] != pack_id:
            continue
        for b in faces_b:
            if b["embedding"] is None or b["embedding_pack"] != pack_id:
                continue
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
    return best


def _unit_vec(blob, dim: int) -> np.ndarray | None:
    if blob is None or dim is None:
        return None
    if len(blob) != 4 * int(dim):
        return None
    vec = np.frombuffer(blob, dtype=np.float32)
    if vec.size != int(dim):
        return None
    out = vec.copy()
    nrm = float(np.linalg.norm(out))
    if nrm > 0:
        out = out / nrm
    return out


def _centroid(faces) -> bytes | None:
    mats = []
    for f in faces:
        v = _unit_vec(f["embedding"], f["embedding_dim"])
        if v is not None:
            mats.append(v)
    if not mats:
        return None
    c = np.mean(np.stack(mats, axis=0), axis=0)
    nrm = float(np.linalg.norm(c))
    if nrm > 0:
        c = c / nrm
    return c.astype(np.float32).tobytes()


def _centroid_merge(faces_groups: list) -> bytes | None:
    """Weighted mean of per-group unit centroids (by face count with embeddings)."""
    parts = []
    weights = []
    for faces in faces_groups:
        mats = []
        for f in faces:
            v = _unit_vec(f["embedding"], f["embedding_dim"])
            if v is not None:
                mats.append(v)
        if not mats:
            continue
        c = np.mean(np.stack(mats, axis=0), axis=0)
        nrm = float(np.linalg.norm(c))
        if nrm > 0:
            c = c / nrm
        parts.append(c)
        weights.append(float(len(mats)))
    if not parts:
        return None
    w = np.asarray(weights, dtype=np.float64)
    stacked = np.stack(parts, axis=0)
    c = np.average(stacked, axis=0, weights=w)
    nrm = float(np.linalg.norm(c))
    if nrm > 0:
        c = c / nrm
    return c.astype(np.float32).tobytes()


def _refresh_cluster(
    conn,
    cluster_id: str,
    pack_id: str,
    *,
    pairwise: bool = True,
    keep_min_intra: float | None = None,
) -> int:
    faces = _faces_in_cluster(conn, cluster_id)
    n = len(faces)
    if n == 0:
        conn.execute("DELETE FROM cluster_person WHERE cluster_id=?", (cluster_id,))
        conn.execute("DELETE FROM clusters WHERE cluster_id=?", (cluster_id,))
        return 0
    if pairwise:
        min_intra = _pairwise_min(faces, pack_id)
    else:
        min_intra = keep_min_intra
    centroid = _centroid(faces)
    conn.execute(
        "UPDATE clusters SET face_count=?, centroid=?, min_intra=? WHERE cluster_id=?",
        (n, centroid, min_intra, cluster_id),
    )
    return n


def _record_decision(
    conn,
    *,
    kind: str,
    run_id: str,
    pack_id: str,
    cluster_id: str | None = None,
    person_id: str | None = None,
    face_id: str | None = None,
    policy: dict | None = None,
) -> str:
    did = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO decisions(
             decision_id, kind, face_id, person_id, cluster_id,
             pack_id, score_top1, score_top2, margin, policy_json, run_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            did,
            kind,
            face_id,
            person_id,
            cluster_id,
            pack_id,
            None,
            None,
            None,
            json.dumps(policy or {}, sort_keys=True),
            run_id,
            _now(),
        ),
    )
    return did


def _resolve_person(
    conn,
    *,
    display_name: str,
    run_id: str,
    attach_to_person_id: str | None,
    create_new: bool,
) -> tuple[str, bool]:
    """Return (person_id, created). Default create_new=True; no silent name reuse."""
    if attach_to_person_id and create_new:
        raise ReviewError("pass attach_to_person_id or create_new=True, not both as conflicting intents")
    if attach_to_person_id:
        row = conn.execute(
            "SELECT person_id, display_name, status FROM persons WHERE person_id=?",
            (attach_to_person_id,),
        ).fetchone()
        if row is None:
            raise ReviewError(f"unknown person: {attach_to_person_id}")
        if row["status"] != "active":
            raise ReviewError(f"person is not active: {attach_to_person_id}")
        conn.execute(
            "UPDATE persons SET display_name=? WHERE person_id=?",
            (display_name, attach_to_person_id),
        )
        return attach_to_person_id, False
    if not create_new:
        raise ReviewError("create_new=False requires attach_to_person_id")
    person_id = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO persons(person_id, display_name, status, created_run)
           VALUES (?,?,?,?)""",
        (person_id, display_name, "active", run_id),
    )
    return person_id, True


def name_cluster(
    store: Path,
    run_id: str,
    cluster_id: str,
    display_name: str,
    *,
    attach_to_person_id: str | None = None,
    create_new: bool = True,
) -> dict:
    """Create (or explicitly attach) a person for a reviewed cluster. Does not equate cluster=person."""
    display_name = (display_name or "").strip()
    if not display_name:
        raise ReviewError("display name must be non-empty")

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        cluster = _require_cluster(conn, run_id, cluster_id)
        if cluster["status"] == "ignored":
            raise ReviewError("cluster is ignored; cannot name until un-ignored")
        faces = _faces_in_cluster(conn, cluster_id)
        if not faces:
            raise ReviewError(f"cluster has no faces: {cluster_id}")

        existing = _person_links(conn, cluster_id)
        created = False
        if existing:
            if len(existing) > 1:
                raise ReviewError(
                    f"cluster linked to multiple persons ({len(existing)}); resolve before rename"
                )
            person_id = existing[0]
            conn.execute(
                "UPDATE persons SET display_name=? WHERE person_id=?",
                (display_name, person_id),
            )
        else:
            person_id, created = _resolve_person(
                conn,
                display_name=display_name,
                run_id=run_id,
                attach_to_person_id=attach_to_person_id,
                create_new=False if attach_to_person_id else create_new,
            )
            conn.execute(
                "INSERT INTO cluster_person(cluster_id, person_id) VALUES (?,?)",
                (cluster_id, person_id),
            )

        conn.execute(
            "UPDATE faces SET person_id=? WHERE cluster_id=?",
            (person_id, cluster_id),
        )
        decision_id = _record_decision(
            conn,
            kind="name",
            run_id=run_id,
            pack_id=pack_id,
            cluster_id=cluster_id,
            person_id=person_id,
            policy={
                "display_name": display_name,
                "face_count": len(faces),
                "created_person": created,
                "cluster_status": cluster["status"],
                "attach_to_person_id": attach_to_person_id,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    snap = _memory_snapshot(store, run_id)
    return {
        "run_id": run_id,
        "cluster_id": cluster_id,
        "person_id": person_id,
        "display_name": display_name,
        "faces_named": len(faces),
        "created_person": created,
        "decision_id": decision_id,
        "memory_snapshot": snap,
        "note": "cluster is not a person; person linked via cluster_person",
    }


def name_face(
    store: Path,
    run_id: str,
    face_id: str,
    display_name: str,
    *,
    attach_to_person_id: str | None = None,
    create_new: bool = True,
) -> dict:
    """Enrol an unassigned inbox face as a person. Does not create a cluster."""
    display_name = (display_name or "").strip()
    if not display_name:
        raise ReviewError("display name must be non-empty")

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        face = conn.execute(
            "SELECT * FROM faces WHERE face_id=? AND run_id=?",
            (face_id, run_id),
        ).fetchone()
        if face is None:
            raise ReviewError(f"unknown face for run: {face_id}")
        if face["status"] != "ok":
            raise ReviewError(f"face is not nameable (status={face['status']})")
        if face["cluster_id"]:
            raise ReviewError("face is in a cluster; name the cluster, not the face")
        if face["person_id"]:
            raise ReviewError("face already has a person")

        person_id, created = _resolve_person(
            conn,
            display_name=display_name,
            run_id=run_id,
            attach_to_person_id=attach_to_person_id,
            create_new=False if attach_to_person_id else create_new,
        )
        conn.execute("UPDATE faces SET person_id=? WHERE face_id=?", (person_id, face_id))
        decision_id = _record_decision(
            conn,
            kind="name",
            run_id=run_id,
            pack_id=pack_id,
            face_id=face_id,
            person_id=person_id,
            policy={
                "display_name": display_name,
                "created_person": created,
                "source": "inbox_face",
                "attach_to_person_id": attach_to_person_id,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    snap = _memory_snapshot(store, run_id)
    return {
        "run_id": run_id,
        "face_id": face_id,
        "person_id": person_id,
        "display_name": display_name,
        "faces_named": 1,
        "created_person": created,
        "decision_id": decision_id,
        "memory_snapshot": snap,
        "note": "cluster is not a person; unassigned face enrolled as person",
    }


def name_faces(
    store: Path,
    run_id: str,
    face_ids: list[str],
    display_name: str,
    *,
    source: str = "faces",
    track_id: str | None = None,
    attach_to_person_id: str | None = None,
    create_new: bool = True,
) -> dict:
    """Enrol unassigned ok faces as one person. Does not create a cluster.

    Used to Name a derived Track. Track id is never the person id.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ReviewError("display name must be non-empty")
    ids: list[str] = []
    for fid in face_ids:
        fid = (fid or "").strip()
        if fid and fid not in ids:
            ids.append(fid)
    if not ids:
        raise ReviewError("name faces requires at least one face id")
    if len(ids) == 1 and source != "track":
        return name_face(
            store,
            run_id,
            ids[0],
            display_name,
            attach_to_person_id=attach_to_person_id,
            create_new=create_new,
        )

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        rows = []
        for fid in ids:
            face = conn.execute(
                "SELECT * FROM faces WHERE face_id=? AND run_id=?",
                (fid, run_id),
            ).fetchone()
            if face is None:
                raise ReviewError(f"unknown face for run: {fid}")
            if face["status"] != "ok":
                raise ReviewError(f"face is not nameable (status={face['status']}): {fid}")
            if face["cluster_id"]:
                raise ReviewError("face is in a cluster; name the cluster, not the track")
            rows.append(face)

        existing_persons = {r["person_id"] for r in rows if r["person_id"]}
        if len(existing_persons) > 1:
            raise ReviewError("faces already linked to different persons")

        created = False
        if existing_persons:
            person_id = next(iter(existing_persons))
            named = conn.execute(
                "SELECT display_name FROM persons WHERE person_id=?",
                (person_id,),
            ).fetchone()
            if named and named["display_name"] and named["display_name"] != display_name:
                raise ReviewError(
                    f"faces already named {named['display_name']!r}; will not attach {display_name!r}"
                )
            conn.execute(
                "UPDATE persons SET display_name=? WHERE person_id=?",
                (display_name, person_id),
            )
        else:
            person_id, created = _resolve_person(
                conn,
                display_name=display_name,
                run_id=run_id,
                attach_to_person_id=attach_to_person_id,
                create_new=False if attach_to_person_id else create_new,
            )

        if track_id and track_id == person_id:
            raise ReviewError("track id must not equal person id")

        _exec_in_chunks(
            conn,
            "UPDATE faces SET person_id=? WHERE face_id IN",
            ids,
            params_prefix=(person_id,),
        )
        decision_id = _record_decision(
            conn,
            kind="name",
            run_id=run_id,
            pack_id=pack_id,
            face_id=ids[0],
            person_id=person_id,
            policy={
                "display_name": display_name,
                "created_person": created,
                "source": source,
                "track_id": track_id,
                "face_ids": ids,
                "face_count": len(ids),
                "attach_to_person_id": attach_to_person_id,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    snap = _memory_snapshot(store, run_id)
    return {
        "run_id": run_id,
        "track_id": track_id,
        "face_ids": ids,
        "person_id": person_id,
        "display_name": display_name,
        "faces_named": len(ids),
        "created_person": created,
        "decision_id": decision_id,
        "memory_snapshot": snap,
        "note": "track is not a person; human named member observations",
    }


def name_track(
    store: Path,
    run_id: str,
    track_id: str,
    display_name: str,
    *,
    attach_to_person_id: str | None = None,
    create_new: bool = True,
) -> dict:
    """Name current members of a derived/persisted track. Track ≠ person."""
    track_id = (track_id or "").strip()
    if not track_id:
        raise ReviewError("track id must be non-empty")
    from semblon.tracks import TracksError, derive_tracks

    try:
        rec = derive_tracks(store, run_id)
    except TracksError as e:
        raise ReviewError(str(e)) from e
    tr = next((t for t in rec["tracks"] if t["track_id"] == track_id), None)
    if tr is None:
        raise ReviewError(f"unknown track for run: {track_id}")
    return name_faces(
        store,
        run_id,
        tr["face_ids"],
        display_name,
        source="track",
        track_id=track_id,
        attach_to_person_id=attach_to_person_id,
        create_new=create_new,
    )


def merge_clusters(
    store: Path,
    run_id: str,
    cluster_ids: list[str],
) -> dict:
    """Merge clusters into the first id. Clustering correction — not person merge."""
    ids = []
    for c in cluster_ids:
        c = (c or "").strip()
        if c and c not in ids:
            ids.append(c)
    if len(ids) < 2:
        raise ReviewError("merge requires at least two distinct cluster ids")

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]

        clusters = [_require_cluster(conn, run_id, cid) for cid in ids]
        survivor = ids[0]
        donors = ids[1:]

        person_sets = []
        for cid in ids:
            links = _person_links(conn, cid)
            person_sets.append(set(links))
        non_empty = [s for s in person_sets if s]
        if any(len(s) > 1 for s in person_sets):
            raise ReviewError("a cluster is linked to multiple persons; resolve before merge")
        if non_empty:
            common = set.intersection(*non_empty) if len(non_empty) > 1 else non_empty[0]
            if len(non_empty) > 1 and not common:
                raise ReviewError("cannot merge clusters linked to different persons")
            person_id = next(iter(non_empty[0]))
        else:
            person_id = None

        face_groups = [_faces_in_cluster(conn, cid) for cid in ids]
        survivor_faces = face_groups[0]
        donor_faces: list = []
        for g in face_groups[1:]:
            donor_faces.extend(g)

        mins: list[float] = []
        for c in clusters:
            if c["min_intra"] is not None:
                mins.append(float(c["min_intra"]))
        cross = _cross_min(survivor_faces, donor_faces, pack_id)
        if cross is not None:
            mins.append(cross)
        new_min = min(mins) if mins else None
        new_centroid = _centroid_merge(face_groups)

        moved = 0
        for cid in donors:
            n = conn.execute(
                "UPDATE faces SET cluster_id=? WHERE cluster_id=?",
                (survivor, cid),
            ).rowcount
            moved += n
            conn.execute("DELETE FROM cluster_person WHERE cluster_id=?", (cid,))
            conn.execute("DELETE FROM clusters WHERE cluster_id=?", (cid,))

        if person_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO cluster_person(cluster_id, person_id) VALUES (?,?)",
                (survivor, person_id),
            )
            conn.execute(
                "UPDATE faces SET person_id=? WHERE cluster_id=?",
                (person_id, survivor),
            )

        face_count = conn.execute(
            "SELECT COUNT(*) FROM faces WHERE cluster_id=?", (survivor,)
        ).fetchone()[0]
        # Do not clobber status (e.g. ignored). Merge is recorded as a decision;
        # cluster_run locks via decision policy survivor/merged.
        conn.execute(
            "UPDATE clusters SET face_count=?, centroid=?, min_intra=? WHERE cluster_id=?",
            (face_count, new_centroid, new_min, survivor),
        )
        decision_id = _record_decision(
            conn,
            kind="merge",
            run_id=run_id,
            pack_id=pack_id,
            cluster_id=survivor,
            person_id=person_id,
            policy={
                "survivor": survivor,
                "merged": donors,
                "moved_faces": moved,
                "strategies": [c["strategy"] for c in clusters],
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "run_id": run_id,
        "survivor": survivor,
        "merged": donors,
        "moved_faces": moved,
        "face_count": face_count,
        "person_id": person_id,
        "decision_id": decision_id,
        "note": "merge corrects clusters; it does not create a person",
    }


def split_cluster(
    store: Path,
    run_id: str,
    cluster_id: str,
    face_ids: list[str],
) -> dict:
    """Move listed faces into a new cluster. Split-off faces lose person_id until re-named."""
    want = []
    for f in face_ids:
        f = (f or "").strip()
        if f and f not in want:
            want.append(f)
    if not want:
        raise ReviewError("split requires at least one face id")

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        old = _require_cluster(conn, run_id, cluster_id)
        members = _faces_in_cluster(conn, cluster_id)
        member_ids = {m["face_id"] for m in members}
        missing = [f for f in want if f not in member_ids]
        if missing:
            raise ReviewError(f"faces not in cluster: {', '.join(missing)}")
        if len(want) >= len(members):
            raise ReviewError("split must leave at least one face in the original cluster")

        new_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO clusters(cluster_id, run_id, strategy, face_count,
               centroid, min_intra, status)
               VALUES (?,?,?,?,?,?,?)""",
            (new_id, run_id, "split", len(want), None, None, "split"),
        )
        _exec_in_chunks(
            conn,
            "UPDATE faces SET cluster_id=?, person_id=NULL WHERE face_id IN",
            want,
            params_prefix=(new_id,),
        )

        remaining_n = len(members) - len(want)
        # Full pairwise on the smaller side; larger keeps prior min_intra (conservative).
        if len(want) <= remaining_n:
            right = _refresh_cluster(conn, new_id, pack_id, pairwise=True)
            left = _refresh_cluster(
                conn,
                cluster_id,
                pack_id,
                pairwise=False,
                keep_min_intra=old["min_intra"],
            )
        else:
            left = _refresh_cluster(conn, cluster_id, pack_id, pairwise=True)
            right = _refresh_cluster(conn, new_id, pack_id, pairwise=True)

        links = _person_links(conn, cluster_id)
        if links:
            conn.execute(
                "UPDATE faces SET person_id=? WHERE cluster_id=?",
                (links[0], cluster_id),
            )

        decision_id = _record_decision(
            conn,
            kind="split",
            run_id=run_id,
            pack_id=pack_id,
            cluster_id=cluster_id,
            person_id=links[0] if links else None,
            policy={
                "from_cluster": cluster_id,
                "new_cluster": new_id,
                "moved_faces": want,
                "from_strategy": old["strategy"],
                "faces_remaining": left,
            },
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "run_id": run_id,
        "from_cluster": cluster_id,
        "new_cluster": new_id,
        "moved_faces": want,
        "faces_remaining": left,
        "new_face_count": right,
        "decision_id": decision_id,
        "note": "split-off cluster is not a person until named",
    }


FACE_DISPOSITIONS = ("singleton", "junk", "needs-review")
CLUSTER_DISPOSITIONS = ("not_a_person",)


def _require_face(conn, run_id: str, face_id: str):
    row = conn.execute(
        "SELECT * FROM faces WHERE face_id=? AND run_id=?",
        (face_id, run_id),
    ).fetchone()
    if row is None:
        raise ReviewError(f"unknown face for run: {face_id}")
    return row


def ignore_subject(
    store: Path,
    run_id: str,
    *,
    cluster_id: str | None = None,
    face_id: str | None = None,
    disposition: str | None = None,
) -> dict:
    """Leave a cluster as not-a-person, or mark an unassigned face. Held-out statuses stay held-out."""
    if bool(cluster_id) == bool(face_id):
        raise ReviewError("ignore requires exactly one of --cluster or --face")
    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        if cluster_id:
            disp = disposition or "not_a_person"
            if disp not in CLUSTER_DISPOSITIONS:
                raise ReviewError("cluster ignore disposition must be not_a_person")
            cluster = _require_cluster(conn, run_id, cluster_id)
            if _person_links(conn, cluster_id):
                raise ReviewError("cluster is already linked to a person")
            conn.execute(
                "UPDATE clusters SET status=? WHERE cluster_id=?",
                ("ignored", cluster_id),
            )
            decision_id = _record_decision(
                conn,
                kind="reject",
                run_id=run_id,
                pack_id=pack_id,
                cluster_id=cluster_id,
                policy={
                    "action": "ignore",
                    "disposition": disp,
                    "face_count": cluster["face_count"],
                },
            )
            conn.commit()
            return {
                "run_id": run_id,
                "cluster_id": cluster_id,
                "disposition": disp,
                "decision_id": decision_id,
                "person_id": None,
                "note": "cluster is not a person",
            }

        disp = disposition or "needs-review"
        if disp not in FACE_DISPOSITIONS:
            raise ReviewError("face ignore disposition must be singleton, junk, or needs-review")
        face = _require_face(conn, run_id, face_id)
        decision_id = _record_decision(
            conn,
            kind="reject",
            run_id=run_id,
            pack_id=pack_id,
            face_id=face_id,
            cluster_id=face["cluster_id"],
            policy={
                "action": "ignore",
                "disposition": disp,
                "face_status": face["status"],
                "held_out": face["status"] != "ok",
                "hidden": True,
            },
        )
        conn.commit()
        return {
            "run_id": run_id,
            "face_id": face_id,
            "disposition": disp,
            "face_status": face["status"],
            "decision_id": decision_id,
            "person_id": None,
            "note": "unassigned mark; rejected/low_quality stay held-out",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def note_subject(
    store: Path,
    run_id: str,
    text: str,
    *,
    cluster_id: str | None = None,
    face_id: str | None = None,
) -> dict:
    """Durable review note. Stored as decisions.kind=note."""
    text = (text or "").strip()
    if not text:
        raise ReviewError("note text must be non-empty")
    if bool(cluster_id) == bool(face_id):
        raise ReviewError("note requires exactly one of --cluster or --face")
    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        if cluster_id:
            _require_cluster(conn, run_id, cluster_id)
            subject_face = None
        else:
            row = _require_face(conn, run_id, face_id)
            subject_face = face_id
            cluster_id = row["cluster_id"]
        decision_id = _record_decision(
            conn,
            kind="note",
            run_id=run_id,
            pack_id=run["pack_id"],
            cluster_id=cluster_id,
            face_id=subject_face,
            policy={"action": "note", "text": text},
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "run_id": run_id,
        "cluster_id": cluster_id,
        "face_id": subject_face,
        "text": text,
        "decision_id": decision_id,
        "person_id": None,
    }


RULED_OUT_ENV = RULED_OUT


def ruled_out_enabled() -> bool:
    """Feature flag for Ruled out. Default OFF — UNWIRED pending human verify."""
    return gate_enabled(RULED_OUT)


def require_ruled_out_enabled() -> None:
    if not ruled_out_enabled():
        raise ReviewError(
            "Ruled out is experimental/UNWIRED; set SEMBLON_RULED_OUT=1 "
            f"({require_human_note(RULED_OUT)})"
        )


def _require_active_person(conn, person_id: str):
    row = conn.execute(
        "SELECT person_id, status FROM persons WHERE person_id=?",
        (person_id,),
    ).fetchone()
    if row is None:
        raise ReviewError(f"unknown person: {person_id}")
    if row["status"] != "active":
        raise ReviewError(f"person is not active: {person_id}")
    return row


def rule_out_subject(
    store: Path,
    run_id: str,
    *,
    cluster_id: str | None = None,
    face_id: str | None = None,
    person_id: str | None = None,
    text: str | None = None,
) -> dict:
    """Durable negative identity decision. Distinct from Ignore (deferred).

    Store: decisions.kind=reject + policy_json.action=rule_out. No new columns.
    Does not set clusters.status='ignored' and does not hide the subject.
    Requires SEMBLON_RULED_OUT=1.
    """
    require_ruled_out_enabled()
    if bool(cluster_id) == bool(face_id):
        raise ReviewError("rule-out requires exactly one of --cluster or --face")
    note = (text or "").strip() or None
    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        target_person = None
        if person_id:
            _require_active_person(conn, person_id)
            target_person = person_id

        if cluster_id:
            cluster = _require_cluster(conn, run_id, cluster_id)
            decision_id = _record_decision(
                conn,
                kind="reject",
                run_id=run_id,
                pack_id=pack_id,
                cluster_id=cluster_id,
                person_id=target_person,
                policy={
                    "action": "rule_out",
                    "subject": "cluster",
                    "target_person_id": target_person,
                    "face_count": cluster["face_count"],
                    **({"text": note} if note else {}),
                },
            )
            conn.commit()
            return {
                "run_id": run_id,
                "cluster_id": cluster_id,
                "face_id": None,
                "person_id": target_person,
                "decision_id": decision_id,
                "action": "rule_out",
                "note": "durable reject; not Ignore; cluster status unchanged",
            }

        face = _require_face(conn, run_id, face_id)
        decision_id = _record_decision(
            conn,
            kind="reject",
            run_id=run_id,
            pack_id=pack_id,
            face_id=face_id,
            cluster_id=face["cluster_id"],
            person_id=target_person,
            policy={
                "action": "rule_out",
                "subject": "face",
                "target_person_id": target_person,
                "face_status": face["status"],
                "hidden": False,
                **({"text": note} if note else {}),
            },
        )
        conn.commit()
        return {
            "run_id": run_id,
            "cluster_id": face["cluster_id"],
            "face_id": face_id,
            "person_id": target_person,
            "decision_id": decision_id,
            "action": "rule_out",
            "note": "durable reject; not Ignore; subject not hidden",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
