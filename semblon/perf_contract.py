"""A+B no-regression / no-semantic-drift contract utilities.

This module snapshots run semantics and compares two snapshots with explicit
numeric tolerances. It is designed to guard performance work so throughput
changes cannot silently change identity or retrieval behavior.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np

from semblon.cluster import _strategy as cluster_strategy

CONTRACT_VERSION = "1"
DEFAULT_EMBED_TOL = 1e-6
DEFAULT_SCORE_TOL = 1e-6
_FROZEN_CLUSTER_EPS = 0.40
_FROZEN_CLUSTER_MIN_SAMPLES = 2


class ContractError(ValueError):
    pass


def _open_ro(store: Path) -> sqlite3.Connection:
    p = Path(store)
    if not p.is_file():
        raise ContractError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _round_coord(v: float | int | None) -> str:
    if v is None:
        return "na"
    return f"{float(v):.3f}"


def _with_dupe_index(raw_keys: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for k in raw_keys:
        idx = seen.get(k, 0)
        seen[k] = idx + 1
        out.append(f"{k}#{idx}")
    return out


def _quantized_digest(blob: bytes, dim: int, tol: float) -> str:
    if tol <= 0:
        return hashlib.sha256(blob).hexdigest()
    vec = np.frombuffer(blob, dtype=np.float32)
    if int(vec.size) != int(dim):
        raise ContractError(f"embedding dim mismatch: got={vec.size} expected={dim}")
    q = np.rint(vec / float(tol)).astype(np.int64, copy=False)
    return hashlib.sha256(q.tobytes()).hexdigest()


def _frozen_cluster_strategy() -> str:
    return cluster_strategy(_FROZEN_CLUSTER_EPS, _FROZEN_CLUSTER_MIN_SAMPLES)


def _face_rows(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            f.face_id,
            f.status,
            f.embedding,
            f.embedding_dim,
            f.embedding_pack,
            f.cluster_id,
            f.person_id,
            f.bbox_x1,
            f.bbox_y1,
            f.bbox_x2,
            f.bbox_y2,
            o.frame_id,
            o.t_ms,
            m.sha256
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.run_id = ?
        ORDER BY m.sha256, COALESCE(o.frame_id, -1), COALESCE(o.t_ms, -1), f.face_id
        """,
        (run_id,),
    ).fetchall()


def _face_key_parts(row: sqlite3.Row) -> str:
    return "|".join(
        [
            row["sha256"],
            str(row["frame_id"] if row["frame_id"] is not None else "still"),
            str(row["t_ms"] if row["t_ms"] is not None else "na"),
            _round_coord(row["bbox_x1"]),
            _round_coord(row["bbox_y1"]),
            _round_coord(row["bbox_x2"]),
            _round_coord(row["bbox_y2"]),
        ]
    )


def _face_signatures(rows: list[sqlite3.Row], *, tol: float) -> list[dict]:
    raw_keys = [_face_key_parts(r) for r in rows]
    keys = _with_dupe_index(raw_keys)
    out: list[dict] = []
    for key, row in zip(keys, rows, strict=True):
        sig = {
            "key": key,
            "status": row["status"],
            "pack_id": row["embedding_pack"],
            "dim": int(row["embedding_dim"] or 0),
            "person_id": row["person_id"],
            "cluster_id": row["cluster_id"],
        }
        blob = row["embedding"]
        if blob is not None:
            dim = int(row["embedding_dim"] or 0)
            sig["qhash"] = _quantized_digest(blob, dim, tol)
        else:
            sig["qhash"] = None
        out.append(sig)
    return out


def _space_signatures(conn: sqlite3.Connection, run_id: str, *, tol: float) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            e.embedding,
            e.embedding_dim,
            e.pack_id,
            e.modality,
            i.kind,
            i.provider,
            i.bbox_x1,
            i.bbox_y1,
            i.bbox_x2,
            i.bbox_y2,
            o.frame_id,
            o.t_ms,
            m.sha256
        FROM embeddings e
        JOIN observation_items i ON i.item_id = e.item_id
        JOIN observations o ON o.observation_id = i.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE i.run_id = ?
        ORDER BY m.sha256, COALESCE(o.frame_id, -1), COALESCE(o.t_ms, -1), i.kind, i.provider, e.modality
        """,
        (run_id,),
    ).fetchall()
    raw_keys = []
    for r in rows:
        raw_keys.append(
            "|".join(
                [
                    r["sha256"],
                    str(r["frame_id"] if r["frame_id"] is not None else "still"),
                    str(r["t_ms"] if r["t_ms"] is not None else "na"),
                    r["kind"],
                    r["provider"],
                    r["modality"],
                    r["pack_id"],
                    _round_coord(r["bbox_x1"]),
                    _round_coord(r["bbox_y1"]),
                    _round_coord(r["bbox_x2"]),
                    _round_coord(r["bbox_y2"]),
                ]
            )
        )
    keys = _with_dupe_index(raw_keys)
    out: list[dict] = []
    for key, row in zip(keys, rows, strict=True):
        dim = int(row["embedding_dim"])
        out.append(
            {
                "key": key,
                "kind": row["kind"],
                "provider": row["provider"],
                "modality": row["modality"],
                "pack_id": row["pack_id"],
                "dim": dim,
                "qhash": _quantized_digest(row["embedding"], dim, tol),
            }
        )
    return out


def _cluster_membership(conn: sqlite3.Connection, run_id: str) -> list[list[str]]:
    rows = _face_rows(conn, run_id)
    sigs = _face_signatures(rows, tol=DEFAULT_EMBED_TOL)
    key_by_face: dict[str, str] = {}
    for row, sig in zip(rows, sigs, strict=True):
        key_by_face[row["face_id"]] = sig["key"]

    cluster_rows = conn.execute(
        "SELECT cluster_id, strategy FROM clusters WHERE run_id=? ORDER BY cluster_id",
        (run_id,),
    ).fetchall()
    members: list[list[str]] = []
    for c in cluster_rows:
        mids = conn.execute(
            "SELECT face_id FROM faces WHERE cluster_id=? ORDER BY face_id",
            (c["cluster_id"],),
        ).fetchall()
        keys = sorted([key_by_face.get(m["face_id"], f"missing:{m['face_id']}") for m in mids])
        members.append(keys)
    members.sort()
    return members


def _identify_latest(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        WITH latest_identify AS (
            SELECT
                d.face_id,
                d.person_id,
                d.score_top1,
                d.score_top2,
                d.margin,
                d.created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY d.face_id
                    ORDER BY d.created_at DESC, d.decision_id DESC
                ) AS rn
            FROM decisions d
            WHERE d.kind='identify' AND d.run_id=?
        )
        SELECT
            li.face_id, li.person_id, li.score_top1, li.score_top2, li.margin,
            f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
            o.frame_id, o.t_ms, m.sha256
        FROM latest_identify li
        JOIN faces f ON f.face_id = li.face_id
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE li.rn = 1
        ORDER BY m.sha256, COALESCE(o.frame_id, -1), COALESCE(o.t_ms, -1), li.face_id
        """,
        (run_id,),
    ).fetchall()
    raw_keys = []
    for r in rows:
        raw_keys.append(
            "|".join(
                [
                    r["sha256"],
                    str(r["frame_id"] if r["frame_id"] is not None else "still"),
                    str(r["t_ms"] if r["t_ms"] is not None else "na"),
                    _round_coord(r["bbox_x1"]),
                    _round_coord(r["bbox_y1"]),
                    _round_coord(r["bbox_x2"]),
                    _round_coord(r["bbox_y2"]),
                ]
            )
        )
    keys = _with_dupe_index(raw_keys)
    out: list[dict] = []
    for key, r in zip(keys, rows, strict=True):
        decision = "UNKNOWN" if r["person_id"] is None else "ACCEPT"
        out.append(
            {
                "key": key,
                "decision": decision,
                "person_id": r["person_id"],
                "score_top1": None if r["score_top1"] is None else float(r["score_top1"]),
                "score_top2": None if r["score_top2"] is None else float(r["score_top2"]),
                "margin": None if r["margin"] is None else float(r["margin"]),
            }
        )
    return out


def _require_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        raise ContractError(f"unknown run: {run_id}")
    return row


def _parse_json_blob(blob: str | None) -> dict:
    if not blob:
        return {}
    try:
        out = json.loads(blob)
    except json.JSONDecodeError:
        return {}
    return out if isinstance(out, dict) else {}


def build_semantic_snapshot(
    store: Path,
    run_id: str,
    *,
    embedding_tol: float = DEFAULT_EMBED_TOL,
) -> dict:
    """Capture semantic contract state for one run."""
    if embedding_tol < 0:
        raise ContractError("embedding_tol must be >= 0")
    conn = _open_ro(store)
    try:
        run = _require_run(conn, run_id)
        runtime = _parse_json_blob(run["runtime_json"])
        timings = _parse_json_blob(run["timings_json"])
        media_rows = conn.execute(
            """
            SELECT DISTINCT m.media_id, m.sha256, m.source_type
            FROM observations o
            JOIN media m ON m.media_id = o.media_id
            WHERE o.run_id=?
            ORDER BY m.sha256, m.media_id
            """,
            (run_id,),
        ).fetchall()
        faces = _face_rows(conn, run_id)
        face_sigs = _face_signatures(faces, tol=embedding_tol)
        space_sigs = _space_signatures(conn, run_id, tol=embedding_tol)
        identify_latest = _identify_latest(conn, run_id)

        identify_unknown = sum(1 for r in identify_latest if r["decision"] == "UNKNOWN")
        identify_accept = sum(1 for r in identify_latest if r["decision"] == "ACCEPT")

        cluster_rows = conn.execute(
            "SELECT strategy FROM clusters WHERE run_id=? ORDER BY cluster_id",
            (run_id,),
        ).fetchall()
        strategies = sorted({r["strategy"] for r in cluster_rows})
        frozen = _frozen_cluster_strategy()

        has_face_modality = (
            conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0] > 0
        )
        non_face_with_face_id = conn.execute(
            "SELECT COUNT(*) FROM observation_items WHERE kind!='face' AND face_id IS NOT NULL"
        ).fetchone()[0]

        track_person_overlap = conn.execute(
            """
            SELECT COUNT(*)
            FROM tracks t
            JOIN persons p ON p.person_id = t.track_id
            WHERE t.run_id=?
            """,
            (run_id,),
        ).fetchone()[0]
        track_cluster_overlap = conn.execute(
            """
            SELECT COUNT(*)
            FROM tracks t
            JOIN clusters c ON c.cluster_id = t.track_id
            WHERE t.run_id=?
            """,
            (run_id,),
        ).fetchone()[0]
        person_cluster_overlap = conn.execute(
            """
            SELECT COUNT(*)
            FROM persons p
            JOIN clusters c ON c.cluster_id = p.person_id
            WHERE c.run_id=?
            """,
            (run_id,),
        ).fetchone()[0]

        corpus_sha = [r["sha256"] for r in media_rows]
        counts = {
            "files": int(timings.get("files") or len(media_rows)),
            "new_media": int(timings.get("new_media") or 0),
            "skipped_seen": int(timings.get("skipped_seen") or 0),
            "skipped_same_run": int(timings.get("skipped_same_run") or 0),
            "failed": int(timings.get("failed") or 0),
            "faces": int(timings.get("faces") or len(faces)),
            "ok": int(timings.get("ok") or sum(1 for f in faces if f["status"] == "ok")),
            "low_quality": int(timings.get("low_quality") or sum(1 for f in faces if f["status"] == "low_quality")),
            "rejected": int(timings.get("rejected") or sum(1 for f in faces if f["status"] == "rejected")),
        }
        counts["accepted"] = max(
            0,
            int(counts["files"])
            - int(counts["skipped_seen"])
            - int(counts["skipped_same_run"])
            - int(counts["failed"]),
        )

        runtime_evidence = {
            "workers": runtime.get("workers", timings.get("workers")),
            "provider": runtime.get("provider"),
            "execution_provider": runtime.get("execution_provider"),
            "onnx_providers": runtime.get("onnx_providers"),
            "gpu": runtime.get("gpu"),
            "device": runtime.get("device"),
            "arch": runtime.get("arch", run["arch"]),
            "execution": runtime.get("execution", run["execution"]),
            "timings": {
                "model_load_s": timings.get("model_load_s", runtime.get("model_load_s")),
                "ingest_s": timings.get("ingest_s"),
                "images_per_second": timings.get("images_per_second"),
                "faces_per_second": timings.get("faces_per_second"),
            },
            "fallback_used": bool(
                isinstance(runtime.get("execution_provider"), str)
                and runtime.get("execution_provider") == "CPUExecutionProvider"
                and bool(runtime.get("gpu"))
            ),
        }
        runtime_evidence["complete"] = all(
            runtime_evidence.get(k) is not None
            for k in ("workers", "provider", "execution_provider", "arch", "execution")
        )

        return {
            "contract_version": CONTRACT_VERSION,
            "embedding_tolerance": float(embedding_tol),
            "run_id": run_id,
            "pack_id": run["pack_id"],
            "corpus": {
                "media_count": len(media_rows),
                "sha256": corpus_sha,
                "source_types": sorted({r["source_type"] for r in media_rows}),
            },
            "counts": counts,
            "face_signatures": sorted(face_sigs, key=lambda r: r["key"]),
            "space_signatures": sorted(space_sigs, key=lambda r: r["key"]),
            "clusters": {
                "strategy_set": strategies,
                "frozen_strategy": frozen,
                "frozen_strategy_present": frozen in strategies if strategies else True,
                "membership": _cluster_membership(conn, run_id),
            },
            "identify": {
                "latest": identify_latest,
                "accept_count": identify_accept,
                "unknown_count": identify_unknown,
            },
            "isolation": {
                "face_modality_rows": int(has_face_modality),
                "non_face_rows_with_face_id": int(non_face_with_face_id),
                "ok": (not has_face_modality) and int(non_face_with_face_id) == 0,
            },
            "guards": {
                "track_person_overlap": int(track_person_overlap),
                "track_cluster_overlap": int(track_cluster_overlap),
                "person_cluster_overlap": int(person_cluster_overlap),
                "observation_track_person_ok": (
                    int(track_person_overlap) == 0
                    and int(track_cluster_overlap) == 0
                    and int(person_cluster_overlap) == 0
                ),
            },
            "runtime_evidence": runtime_evidence,
        }
    finally:
        conn.close()


def _index_by_key(rows: list[dict], *, key_fields: tuple[str, ...] = ("key",)) -> dict[str, dict]:
    out = {}
    for row in rows:
        key = "|".join(str(row.get(f)) for f in key_fields)
        out[key] = row
    return out


def _float_close(a: float | None, b: float | None, tol: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= float(tol)


def compare_semantic_snapshots(
    before: dict,
    after: dict,
    *,
    score_tol: float = DEFAULT_SCORE_TOL,
) -> dict:
    """Compare semantic snapshots under the no-drift contract."""
    diffs: list[str] = []
    if before.get("contract_version") != after.get("contract_version"):
        diffs.append("contract_version changed")
    if before.get("embedding_tolerance") != after.get("embedding_tolerance"):
        diffs.append("embedding tolerance changed")
    if before.get("corpus", {}).get("sha256") != after.get("corpus", {}).get("sha256"):
        diffs.append("fixed corpus sha256 set changed")

    for k in (
        "accepted",
        "skipped_seen",
        "skipped_same_run",
        "failed",
        "faces",
        "ok",
        "low_quality",
        "rejected",
    ):
        if before.get("counts", {}).get(k) != after.get("counts", {}).get(k):
            diffs.append(f"count mismatch: {k}")

    bf = _index_by_key(before.get("face_signatures") or [])
    af = _index_by_key(after.get("face_signatures") or [])
    if set(bf) != set(af):
        diffs.append("face signature keys changed")
    else:
        for key in sorted(bf):
            x = bf[key]
            y = af[key]
            if x.get("status") != y.get("status"):
                diffs.append(f"face status changed: {key}")
            if x.get("pack_id") != y.get("pack_id") or x.get("dim") != y.get("dim"):
                diffs.append(f"face embedding space changed: {key}")
            if x.get("qhash") != y.get("qhash"):
                diffs.append(f"face embedding changed beyond tolerance: {key}")
            if x.get("person_id") != y.get("person_id"):
                diffs.append(f"face person assignment changed: {key}")

    bs = _index_by_key(
        before.get("space_signatures") or [],
        key_fields=("key", "modality", "pack_id", "dim"),
    )
    a_s = _index_by_key(
        after.get("space_signatures") or [],
        key_fields=("key", "modality", "pack_id", "dim"),
    )
    if set(bs) != set(a_s):
        diffs.append("non-face embedding signature keys changed")
    else:
        for key in sorted(bs):
            if bs[key].get("qhash") != a_s[key].get("qhash"):
                diffs.append(f"non-face embedding changed beyond tolerance: {key}")

    if before.get("clusters", {}).get("frozen_strategy_present") != after.get("clusters", {}).get("frozen_strategy_present"):
        diffs.append("frozen cluster strategy presence changed")
    if before.get("clusters", {}).get("membership") != after.get("clusters", {}).get("membership"):
        diffs.append("cluster membership changed")

    bi = _index_by_key(before.get("identify", {}).get("latest") or [])
    ai = _index_by_key(after.get("identify", {}).get("latest") or [])
    if set(bi) != set(ai):
        diffs.append("identify decision keys changed")
    else:
        for key in sorted(bi):
            x = bi[key]
            y = ai[key]
            if x.get("decision") != y.get("decision") or x.get("person_id") != y.get("person_id"):
                diffs.append(f"identify decision changed: {key}")
            for fld in ("score_top1", "score_top2", "margin"):
                if not _float_close(x.get(fld), y.get(fld), score_tol):
                    diffs.append(f"identify score drift {fld}: {key}")
    if before.get("identify", {}).get("unknown_count") != after.get("identify", {}).get("unknown_count"):
        diffs.append("UNKNOWN identify count changed")

    if not bool(before.get("isolation", {}).get("ok")) or not bool(after.get("isolation", {}).get("ok")):
        diffs.append("non-face modality/pack/dimension isolation broken")
    if not bool(before.get("guards", {}).get("observation_track_person_ok")) or not bool(
        after.get("guards", {}).get("observation_track_person_ok")
    ):
        diffs.append("observation != track != person guard broken")

    rt = after.get("runtime_evidence", {})
    for fld in ("workers", "provider", "execution_provider", "arch", "execution", "timings"):
        if rt.get(fld) is None:
            diffs.append(f"runtime evidence missing field: {fld}")

    return {
        "ok": len(diffs) == 0,
        "diffs": sorted(set(diffs)),
        "summary": {
            "before_run_id": before.get("run_id"),
            "after_run_id": after.get("run_id"),
            "checked_counts": [
                "accepted",
                "skipped_seen",
                "skipped_same_run",
                "failed",
                "faces",
                "ok",
                "low_quality",
                "rejected",
            ],
            "embedding_tolerance": before.get("embedding_tolerance"),
            "score_tolerance": float(score_tol),
        },
        "note": "A performance gain that changes semantics is rejected.",
    }


def write_snapshot(path: Path, snapshot: dict) -> dict:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return {"out": str(out.resolve()), "bytes": out.stat().st_size}


def read_snapshot(path: Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ContractError(f"snapshot not found: {p}")
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContractError(f"bad snapshot JSON: {p}") from e
    if not isinstance(rec, dict):
        raise ContractError("snapshot must be a JSON object")
    return rec
