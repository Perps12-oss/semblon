"""Shared Cluster Review board DTO for export (snapshot) and Home / review-ui (live).

No new SQLite columns. Classification is binary GOOD / REVIEW at STRONG_MIN_INTRA.
Cluster ≠ person. UI does not import FaceKit.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from semblon.compare import CompareError, compare
from semblon.export import STRONG_MIN_INTRA, _crop_jpeg, _file_uri, _stored_json
from semblon.process import empty_state_line
from semblon.tracks import TracksError, derive_tracks

CARD_THUMB_MAX = 10
INSPECTOR_THUMB_MAX = 18
THUMB_SIDE = 96
WORST_SIDE = 160
# Cap pairwise work for huge clusters (sim_max / worst pair).
_PAIRWISE_FACE_CAP = 48


def _connect_ro(store: Path) -> sqlite3.Connection:
    p = Path(store).resolve()
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _face_row(row) -> dict[str, Any]:
    return {
        "face_id": row["face_id"],
        "observation_id": row["observation_id"],
        "path": row["path"],
        "source_type": row["source_type"],
        "frame_id": row["frame_id"],
        "t_ms": row["t_ms"],
        "status": row["status"],
        "cluster_id": row["cluster_id"],
        "person_id": row["person_id"] if "person_id" in row.keys() else None,
        "person_name": row["person_name"] if "person_name" in row.keys() else None,
        "bbox": (row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]),
        "embedding": row["embedding"],
        "embedding_pack": row["embedding_pack"],
        "embedding_dim": row["embedding_dim"],
    }


def _thumb_obj(member: dict, *, include_data_uri: bool, max_side: int = THUMB_SIDE) -> dict:
    path = member.get("path") or ""
    obj: dict[str, Any] = {
        "face_id": member["face_id"],
        "path": path,
        "source_type": member.get("source_type"),
        "frame_id": member.get("frame_id"),
        "t_ms": member.get("t_ms"),
        "bbox": list(member.get("bbox") or ()),
        "status": member.get("status"),
        "path_uri": _file_uri(path) if path else "",
    }
    if include_data_uri:
        uri = _crop_jpeg(
            path,
            member.get("bbox"),
            max_side,
            frame_id=member.get("frame_id"),
            source_type=member.get("source_type"),
        )
        obj["data_uri"] = uri
    return obj


def _pairwise(
    members: list[dict],
    pack_id: str,
) -> tuple[float | None, tuple[dict, dict] | None, float | None]:
    """Return (min_sim, worst_pair, max_sim) among ok faces sharing pack_id."""
    usable = [
        m
        for m in members
        if m.get("embedding") is not None and m.get("embedding_pack") == pack_id
    ][:_PAIRWISE_FACE_CAP]
    best_min = None
    best_max = None
    pair = None
    for i, a in enumerate(usable):
        for b in usable[i + 1 :]:
            try:
                s = float(
                    compare(
                        pack_id,
                        a["embedding_dim"],
                        a["embedding"],
                        pack_id,
                        b["embedding_dim"],
                        b["embedding"],
                    )
                )
            except CompareError:
                continue
            if best_min is None or s < best_min:
                best_min = s
                pair = (a, b)
            if best_max is None or s > best_max:
                best_max = s
    return best_min, pair, best_max


def _decision_sets(decisions) -> tuple[set[str], set[str]]:
    ignored_faces: set[str] = set()
    ignored_clusters: set[str] = set()
    for d in decisions:
        try:
            pol = json.loads(d["policy_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            pol = {}
        if not isinstance(pol, dict):
            pol = {}
        if d["kind"] == "reject" and pol.get("action") == "ignore":
            if d["face_id"]:
                ignored_faces.add(d["face_id"])
            elif d["cluster_id"]:
                ignored_clusters.add(d["cluster_id"])
    return ignored_faces, ignored_clusters


def _classify(min_intra: float | None, strong_min_intra: float) -> str:
    if min_intra is None or min_intra < strong_min_intra:
        return "review"
    return "good"


def build_chrome_board(
    store: Path,
    run_id: str,
    *,
    mode: str = "snapshot",
    strong_min_intra: float = STRONG_MIN_INTRA,
    include_thumbs: bool | None = None,
) -> dict:
    """Board JSON shared by snapshot HTML and live WebView hosts."""
    if mode not in ("snapshot", "live"):
        raise ValueError(f"mode must be snapshot|live, got {mode!r}")
    if include_thumbs is None:
        include_thumbs = True  # forensic file and live both need visible thumbs

    store = Path(store)
    conn = _connect_ro(store)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise ValueError(f"unknown run: {run_id}")

    clusters = conn.execute(
        """SELECT * FROM clusters WHERE run_id=?
           ORDER BY min_intra ASC, face_count DESC""",
        (run_id,),
    ).fetchall()
    faces = conn.execute(
        """
        SELECT f.*, m.path, m.source_type, m.media_id,
               o.observation_id AS observation_id, o.frame_id, o.t_ms,
               p.display_name AS person_name
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        LEFT JOIN persons p ON p.person_id = f.person_id
        WHERE f.run_id=?
        ORDER BY f.face_id
        """,
        (run_id,),
    ).fetchall()
    decisions = conn.execute(
        """SELECT * FROM decisions WHERE run_id=?
           ORDER BY created_at, decision_id""",
        (run_id,),
    ).fetchall()
    # media has no run_id column — count distinct media via this run's observations.
    n_photos = conn.execute(
        """SELECT COUNT(DISTINCT m.media_id)
           FROM media m
           JOIN observations o ON o.media_id = m.media_id
           WHERE o.run_id=?""",
        (run_id,),
    ).fetchone()[0]
    conn.close()

    pack_id = run["pack_id"]
    ignored_faces, ignored_clusters = _decision_sets(decisions)

    by_cluster: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    rejected_list: list[dict] = []
    n_ok = 0
    n_lq = 0
    for raw in faces:
        st = raw["status"]
        if st == "ok":
            n_ok += 1
        elif st == "low_quality":
            n_lq += 1
        if raw["face_id"] in ignored_faces:
            continue
        d = _face_row(raw)
        if d["status"] == "rejected":
            rejected_list.append(d)
        elif d["cluster_id"]:
            by_cluster.setdefault(d["cluster_id"], []).append(d)
        elif d["status"] == "ok":
            unassigned.append(d)

    # Stable display_index by sorted cluster_id (mutations use hex id).
    active_clusters = [
        c
        for c in clusters
        if c["status"] != "ignored" and c["cluster_id"] not in ignored_clusters
    ]
    index_by_id = {
        cid: f"{i:04d}"
        for i, cid in enumerate(sorted(c["cluster_id"] for c in active_clusters), start=1)
    }

    cluster_rows: list[dict] = []
    n_good = n_review = n_mixed = n_low = 0
    for c in active_clusters:
        members = by_cluster.get(c["cluster_id"], [])
        mi = c["min_intra"]
        classification = _classify(mi if mi is None else float(mi), strong_min_intra)
        computed_min, pair, computed_max = _pairwise(members, pack_id)
        # Prefer stored min_intra; fall back to computed.
        sim_min = float(mi) if mi is not None else computed_min
        sim_max = computed_max if computed_max is not None else sim_min
        person_names = sorted({m["person_name"] for m in members if m.get("person_name")})
        person_ids = {m["person_id"] for m in members if m.get("person_id")}
        named = bool(person_names)
        if classification == "good":
            n_good += 1
        else:
            n_review += 1
            n_mixed += 1
            if sim_min is None or sim_min < 0.40:
                n_low += 1

        worst_ids = None
        worst_thumbs: list[dict] = []
        if pair is not None:
            worst_ids = [pair[0]["face_id"], pair[1]["face_id"]]
            worst_thumbs = [
                _thumb_obj(pair[0], include_data_uri=include_thumbs, max_side=WORST_SIDE),
                _thumb_obj(pair[1], include_data_uri=include_thumbs, max_side=WORST_SIDE),
            ]

        thumbs = [
            _thumb_obj(m, include_data_uri=include_thumbs)
            for m in members
        ]
        cluster_rows.append(
            {
                "cluster_id": c["cluster_id"],
                "display_index": index_by_id[c["cluster_id"]],
                "classification": classification,
                "face_count": len(members),
                "min_intra": float(mi) if mi is not None else None,
                "sim_min": sim_min,
                "sim_max": sim_max,
                "named": named,
                "person_id": next(iter(person_ids), None) if len(person_ids) == 1 else None,
                "display_name": person_names[0] if len(person_names) == 1 else None,
                "status": c["status"],
                "strategy": c["strategy"] if "strategy" in c.keys() else "",
                "worst_pair": worst_ids,
                "worst_pair_thumbs": worst_thumbs,
                "thumbs": thumbs,
                "created_at": run["started_at"],
                "mixed_note": classification == "review",
            }
        )

    # Priority order for default board: review (lowest min_intra), then good.
    cluster_rows.sort(
        key=lambda it: (
            0 if it["classification"] == "review" else 1,
            it["min_intra"] is None,
            it["min_intra"] if it["min_intra"] is not None else 0.0,
            -it["face_count"],
        )
    )

    tracks_rec = None
    try:
        tracks_rec = derive_tracks(store, run_id)
    except TracksError:
        tracks_rec = None

    track_summaries: list[dict] = []
    if tracks_rec:
        by_id = {m["face_id"]: m for m in unassigned if m.get("source_type") == "video"}
        for tr in tracks_rec.get("tracks") or []:
            members = [by_id[fid] for fid in tr.get("face_ids") or [] if fid in by_id]
            if len(members) < 2:
                continue
            track_summaries.append(
                {
                    "track_id": tr.get("track_id"),
                    "path": tr.get("path"),
                    "face_count": len(members),
                    "face_ids": [m["face_id"] for m in members],
                    "t_ms_start": tr.get("t_ms_start"),
                    "t_ms_end": tr.get("t_ms_end"),
                    "note": "temporal association; not a person",
                }
            )

    unassigned_thumbs = [
        _thumb_obj(m, include_data_uri=include_thumbs)
        for m in unassigned[: max(CARD_THUMB_MAX, INSPECTOR_THUMB_MAX)]
    ]
    rejected_thumbs = [
        _thumb_obj(m, include_data_uri=include_thumbs)
        for m in rejected_list[:CARD_THUMB_MAX]
    ]

    timings = run["timings_json"]
    if isinstance(timings, (bytes, bytearray)):
        timings = timings.decode("utf-8", errors="replace")
    timings_s = "" if timings is None else str(timings)

    board = {
        "mode": mode,
        "run_id": run_id,
        "run_started_at": run["started_at"],
        "store": str(store.resolve()),
        "pack_id": pack_id,
        "arch": run["arch"],
        "execution": run["execution"],
        "timings": timings_s,
        "strong_min_intra": strong_min_intra,
        "empty_state": empty_state_line(store, run_id),
        "stats": {
            "photos_processed": int(n_photos or 0),
            "faces_detected": len(faces),
            "clusters": len(cluster_rows),
            "unassigned": len(unassigned),
            "rejected": len(rejected_list),
            "good": n_good,
            "review": n_review,
            "mixed": n_mixed,
            "low_confidence": n_low,
            "ok": n_ok,
            "low_quality": n_lq,
        },
        "clusters": cluster_rows,
        "unassigned": {
            "face_count": len(unassigned),
            "thumbs": unassigned_thumbs,
            "tracks": track_summaries,
        },
        "rejected": {
            "face_count": len(rejected_list),
            "thumbs": rejected_thumbs,
        },
        "decisions": [
            {
                "kind": d["kind"],
                "cluster_id": d["cluster_id"],
                "face_id": d["face_id"],
                "created_at": d["created_at"],
                "policy": _stored_json(d["policy_json"]),
            }
            for d in decisions
        ],
    }
    return board


def evidence_counts_from_board(board: dict, *, n_faces: int | None = None) -> dict:
    """Map chrome board stats onto the legacy evidence ``counts`` keys."""
    stats = board.get("stats") or {}
    clusters = board.get("clusters") or []
    decisions = board.get("decisions") or []
    faces = n_faces if n_faces is not None else stats.get("faces_detected", 0)
    return {
        "faces": faces,
        "ok": max(0, int(faces) - int(stats.get("rejected", 0))),  # approx; refined by caller
        "low_quality": 0,
        "rejected": int(stats.get("rejected", 0)),
        "clusters": int(stats.get("clusters", 0)),
        "review_required": int(stats.get("review", 0)),
        "strong": int(stats.get("good", 0)),
        "unassigned": int(stats.get("unassigned", 0)),
        "decisions": len(decisions),
        "_clusters_raw": clusters,
    }
