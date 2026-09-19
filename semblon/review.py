"""0.4 review ops: name / merge / split. Clusters are not persons.

Invariant: cluster → review → person → name.
Human corrections are decisions (evidence), not training.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from semblon.compare import CompareError, compare
from semblon.store import connect, init_db

_ENTERED_S3: set[str] = set()


class ReviewError(ValueError):
    pass


def _memory_snapshot(store: Path, run_id: str) -> dict:
    try:
        from semblon.observers import snapshot_memory_graph

        return snapshot_memory_graph(store, run_id)
    except Exception:
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _warn_enter_s3(store: Path, run_id: str) -> dict | None:
    """Observatory auto-evoke when starting S3 work. Warn only — never refuse."""
    key = f"{Path(store).resolve()}|{run_id}"
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


def _centroid(faces) -> bytes | None:
    mats = []
    for f in faces:
        if f["embedding"] is None or f["embedding_dim"] is None:
            continue
        dim = int(f["embedding_dim"])
        if len(f["embedding"]) != 4 * dim:
            continue
        vec = np.frombuffer(f["embedding"], dtype=np.float32)
        if vec.size != dim:
            continue
        mats.append(vec.copy())
    if not mats:
        return None
    c = np.mean(np.stack(mats, axis=0), axis=0)
    nrm = float(np.linalg.norm(c))
    if nrm > 0:
        c = c / nrm
    return c.astype(np.float32).tobytes()


def _refresh_cluster(conn, cluster_id: str, pack_id: str) -> int:
    faces = _faces_in_cluster(conn, cluster_id)
    n = len(faces)
    if n == 0:
        conn.execute("DELETE FROM cluster_person WHERE cluster_id=?", (cluster_id,))
        conn.execute("DELETE FROM clusters WHERE cluster_id=?", (cluster_id,))
        return 0
    min_intra = _pairwise_min(faces, pack_id)
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


def name_cluster(
    store: Path,
    run_id: str,
    cluster_id: str,
    display_name: str,
) -> dict:
    """Create (or attach) a person for a reviewed cluster. Does not equate cluster=person."""
    display_name = (display_name or "").strip()
    if not display_name:
        raise ReviewError("display name must be non-empty")

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    run = _require_run(conn, run_id)
    pack_id = run["pack_id"]
    cluster = _require_cluster(conn, run_id, cluster_id)
    faces = _faces_in_cluster(conn, cluster_id)
    if not faces:
        conn.close()
        raise ReviewError(f"cluster has no faces: {cluster_id}")

    existing = _person_links(conn, cluster_id)
    created = False
    if existing:
        if len(existing) > 1:
            conn.close()
            raise ReviewError(
                f"cluster linked to multiple persons ({len(existing)}); resolve before rename"
            )
        person_id = existing[0]
        conn.execute(
            "UPDATE persons SET display_name=? WHERE person_id=?",
            (display_name, person_id),
        )
    else:
        # Reuse active person with the same display_name if the user assigns another cluster.
        row = conn.execute(
            """SELECT person_id FROM persons
               WHERE status='active' AND display_name=?
               ORDER BY person_id LIMIT 1""",
            (display_name,),
        ).fetchone()
        if row:
            person_id = row[0]
        else:
            person_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO persons(person_id, display_name, status, created_run)
                   VALUES (?,?,?,?)""",
                (person_id, display_name, "active", run_id),
            )
            created = True
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
        },
    )
    conn.commit()
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
) -> dict:
    """Enrol an unassigned inbox face as a person. Does not create a cluster."""
    display_name = (display_name or "").strip()
    if not display_name:
        raise ReviewError("display name must be non-empty")

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    run = _require_run(conn, run_id)
    pack_id = run["pack_id"]
    face = conn.execute(
        "SELECT * FROM faces WHERE face_id=? AND run_id=?",
        (face_id, run_id),
    ).fetchone()
    if face is None:
        conn.close()
        raise ReviewError(f"unknown face for run: {face_id}")
    if face["status"] != "ok":
        conn.close()
        raise ReviewError(f"face is not nameable (status={face['status']})")
    if face["cluster_id"]:
        conn.close()
        raise ReviewError("face is in a cluster; name the cluster, not the face")
    if face["person_id"]:
        conn.close()
        raise ReviewError("face already has a person")

    row = conn.execute(
        """SELECT person_id FROM persons
           WHERE status='active' AND display_name=?
           ORDER BY person_id LIMIT 1""",
        (display_name,),
    ).fetchone()
    created = False
    if row:
        person_id = row[0]
    else:
        person_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO persons(person_id, display_name, status, created_run)
               VALUES (?,?,?,?)""",
            (person_id, display_name, "active", run_id),
        )
        created = True
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
        },
    )
    conn.commit()
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
        return name_face(store, run_id, ids[0], display_name)

    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
    run = _require_run(conn, run_id)
    pack_id = run["pack_id"]
    rows = []
    for fid in ids:
        face = conn.execute(
            "SELECT * FROM faces WHERE face_id=? AND run_id=?",
            (fid, run_id),
        ).fetchone()
        if face is None:
            conn.close()
            raise ReviewError(f"unknown face for run: {fid}")
        if face["status"] != "ok":
            conn.close()
            raise ReviewError(f"face is not nameable (status={face['status']}): {fid}")
        if face["cluster_id"]:
            conn.close()
            raise ReviewError("face is in a cluster; name the cluster, not the track")
        rows.append(face)

    existing_persons = {r["person_id"] for r in rows if r["person_id"]}
    if len(existing_persons) > 1:
        conn.close()
        raise ReviewError("faces already linked to different persons")

    created = False
    if existing_persons:
        person_id = next(iter(existing_persons))
        named = conn.execute(
            "SELECT display_name FROM persons WHERE person_id=?",
            (person_id,),
        ).fetchone()
        if named and named["display_name"] and named["display_name"] != display_name:
            conn.close()
            raise ReviewError(
                f"faces already named {named['display_name']!r}; will not attach {display_name!r}"
            )
        conn.execute(
            "UPDATE persons SET display_name=? WHERE person_id=?",
            (display_name, person_id),
        )
    else:
        row = conn.execute(
            """SELECT person_id FROM persons
               WHERE status='active' AND display_name=?
               ORDER BY person_id LIMIT 1""",
            (display_name,),
        ).fetchone()
        if row:
            person_id = row[0]
        else:
            person_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO persons(person_id, display_name, status, created_run)
                   VALUES (?,?,?,?)""",
                (person_id, display_name, "active", run_id),
            )
            created = True

    if track_id and track_id == person_id:
        conn.close()
        raise ReviewError("track id must not equal person id")

    conn.execute(
        f"UPDATE faces SET person_id=? WHERE face_id IN ({','.join('?' * len(ids))})",
        (person_id, *ids),
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
        },
    )
    conn.commit()
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
) -> dict:
    """Name current members of a derived track. Re-derives; does not persist a track row."""
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
    run = _require_run(conn, run_id)
    pack_id = run["pack_id"]

    clusters = [_require_cluster(conn, run_id, cid) for cid in ids]
    survivor = ids[0]
    donors = ids[1:]

    # Person links: all unnamed, or all the same single person.
    person_sets = []
    for cid in ids:
        links = _person_links(conn, cid)
        person_sets.append(set(links))
    non_empty = [s for s in person_sets if s]
    if any(len(s) > 1 for s in person_sets):
        conn.close()
        raise ReviewError("a cluster is linked to multiple persons; resolve before merge")
    if non_empty:
        common = set.intersection(*non_empty) if len(non_empty) > 1 else non_empty[0]
        if len(non_empty) > 1 and not common:
            conn.close()
            raise ReviewError("cannot merge clusters linked to different persons")
        person_id = next(iter(non_empty[0]))
    else:
        person_id = None

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

    face_count = _refresh_cluster(conn, survivor, pack_id)
    conn.execute(
        "UPDATE clusters SET status=? WHERE cluster_id=?",
        ("merged", survivor),
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
    run = _require_run(conn, run_id)
    pack_id = run["pack_id"]
    old = _require_cluster(conn, run_id, cluster_id)
    members = _faces_in_cluster(conn, cluster_id)
    member_ids = {m["face_id"] for m in members}
    missing = [f for f in want if f not in member_ids]
    if missing:
        conn.close()
        raise ReviewError(f"faces not in cluster: {', '.join(missing)}")
    if len(want) >= len(members):
        conn.close()
        raise ReviewError("split must leave at least one face in the original cluster")

    new_id = uuid.uuid4().hex
    strategy = f"split:from={cluster_id}:faces={len(want)}"
    conn.execute(
        """INSERT INTO clusters(cluster_id, run_id, strategy, face_count,
           centroid, min_intra, status)
           VALUES (?,?,?,?,?,?,?)""",
        (new_id, run_id, strategy, len(want), None, None, "split"),
    )
    q = ",".join("?" * len(want))
    conn.execute(
        f"UPDATE faces SET cluster_id=?, person_id=NULL WHERE face_id IN ({q})",
        [new_id, *want],
    )

    left = _refresh_cluster(conn, cluster_id, pack_id)
    right = _refresh_cluster(conn, new_id, pack_id)
    # Original cluster keeps any person link; split cluster is not auto-named.
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
    run = _require_run(conn, run_id)
    pack_id = run["pack_id"]
    if cluster_id:
        disp = disposition or "not_a_person"
        if disp not in CLUSTER_DISPOSITIONS:
            conn.close()
            raise ReviewError("cluster ignore disposition must be not_a_person")
        cluster = _require_cluster(conn, run_id, cluster_id)
        if _person_links(conn, cluster_id):
            conn.close()
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
        conn.close()
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
        conn.close()
        raise ReviewError("face ignore disposition must be singleton, junk, or needs-review")
    face = _require_face(conn, run_id, face_id)
    if face["status"] in ("rejected", "low_quality"):
        # Held-out observations stay held-out. Record the note only.
        pass
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
        },
    )
    conn.commit()
    conn.close()
    return {
        "run_id": run_id,
        "face_id": face_id,
        "disposition": disp,
        "face_status": face["status"],
        "decision_id": decision_id,
        "person_id": None,
        "note": "unassigned mark; rejected/low_quality stay held-out",
    }


def note_subject(
    store: Path,
    run_id: str,
    text: str,
    *,
    cluster_id: str | None = None,
    face_id: str | None = None,
) -> dict:
    """Durable review note. Stored as decisions.kind=reject (schema has no note kind)."""
    text = (text or "").strip()
    if not text:
        raise ReviewError("note text must be non-empty")
    if bool(cluster_id) == bool(face_id):
        raise ReviewError("note requires exactly one of --cluster or --face")
    _warn_enter_s3(store, run_id)
    conn = connect(store)
    init_db(conn)
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
        kind="reject",
        run_id=run_id,
        pack_id=run["pack_id"],
        cluster_id=cluster_id,
        face_id=subject_face,
        policy={"action": "note", "text": text},
    )
    conn.commit()
    conn.close()
    return {
        "run_id": run_id,
        "cluster_id": cluster_id,
        "face_id": subject_face,
        "text": text,
        "decision_id": decision_id,
        "person_id": None,
    }
