"""UI-free review board. Tk review_ui is a client of these functions.

People exist only after an explicit Name action. Does not retune clustering.
Does not identify. Does not import tkinter, Home, canvas, or Qt.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.export import STRONG_MIN_INTRA
from semblon.process import empty_state_line, latest_run_id
from semblon.review import (
    ignore_subject,
    merge_clusters,
    name_cluster,
    name_face,
    name_faces,
    note_subject,
    rule_out_subject,
    split_cluster,
)
from semblon.tracks import TracksError, derive_tracks

class ReviewUiError(ValueError):
    pass

class ReviewExpectedEmpty(ReviewUiError):
    """No store or no runs yet — coaching empty state, not an Error dialog."""

    def __init__(self, reason: str):
        self.reason = reason  # "no_store" | "no_runs"
        super().__init__(reason)

def _ro_connect(store: Path) -> sqlite3.Connection:
    """Read-only store connection. Waits on the existing writer (busy_timeout=5000)."""
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def resolve_run_id(store: Path, run_id: str | None) -> str:
    """Use --run when given; otherwise the latest run that still has faces.

    Empty incremental runs (FACE-005 skip-all) must not hide a prior populated run.
    Expected empty (no store / no runs) raises ReviewExpectedEmpty — not a hard Error.
    """
    store = Path(store)
    if not store.is_file():
        raise ReviewExpectedEmpty("no_store")
    if run_id:
        try:
            conn = _ro_connect(store)
            row = conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone()
            conn.close()
        except sqlite3.Error as e:
            raise ReviewUiError(f"couldn't read the library: {e}") from e
        if row is None:
            raise ReviewUiError(f"unknown run: {run_id}")
        return run_id
    try:
        rid = latest_run_id(store, with_faces=True) or latest_run_id(store)
    except sqlite3.Error as e:
        raise ReviewUiError(f"couldn't read the library: {e}") from e
    if rid is None:
        raise ReviewExpectedEmpty("no_runs")
    return rid

def _basename(path: str) -> str:
    return Path(path or "").name or (path or "")

def _decision_sets(decisions) -> tuple[set[str], set[str], set[str], set[str]]:
    """ignored_faces, ignored_clusters, noted_faces, noted_clusters."""
    ignored_faces: set[str] = set()
    ignored_clusters: set[str] = set()
    noted_faces: set[str] = set()
    noted_clusters: set[str] = set()
    for d in decisions:
        try:
            pol = json.loads(d["policy_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            pol = {}
        if not isinstance(pol, dict):
            pol = {}
        kind = d["kind"]
        fid = d["face_id"]
        cid = d["cluster_id"]
        if kind == "reject" and pol.get("action") == "ignore":
            if fid:
                ignored_faces.add(fid)
            elif cid:
                ignored_clusters.add(cid)
        if kind == "note":
            if fid:
                noted_faces.add(fid)
            if cid:
                noted_clusters.add(cid)
    return ignored_faces, ignored_clusters, noted_faces, noted_clusters

def _track_items(
    store: Path,
    run_id: str,
    video_faces: list[dict],
    *,
    cached: dict | None = None,
) -> tuple[list[dict], list[dict], dict | None]:
    """Render derived S7 tracks. Leftovers stay untracked observations."""
    if not video_faces:
        return [], [], cached
    face_key = tuple(sorted(f["face_id"] for f in video_faces))
    if cached and cached.get("face_key") == face_key:
        rec = cached["rec"]
    else:
        try:
            rec = derive_tracks(store, run_id)
        except TracksError:
            return [], list(video_faces), None
        cached = {"face_key": face_key, "rec": rec}
    by_id = {f["face_id"]: f for f in video_faces}
    used: set[str] = set()
    items: list[dict] = []
    for tr in rec["tracks"]:
        members = [by_id[fid] for fid in tr["face_ids"] if fid in by_id]
        if len(members) < 2:
            continue
        used.update(m["face_id"] for m in members)
        person_names = sorted({m["person_name"] for m in members if m["person_name"]})
        items.append(
            {
                "kind": "track",
                "track_id": tr["track_id"],
                "media_id": tr["media_id"],
                "path": tr["path"],
                "face_id": "",
                "band": "unassigned",
                "face_count": len(members),
                "min_intra": None,
                "status": "ok",
                "person_names": person_names,
                "named": bool(person_names),
                "t_ms_start": tr["t_ms_start"],
                "t_ms_end": tr["t_ms_end"],
                "representative_face_id": tr["representative_face_id"],
                "members": members,
                "has_note": False,
                "note": "temporal association; not a person",
            }
        )
    leftover = [f for f in video_faces if f["face_id"] not in used]
    return items, leftover, cached

def load_board(
    store: Path,
    run_id: str,
    *,
    strong_min_intra: float = STRONG_MIN_INTRA,
    tracks_cache: dict | None = None,
) -> dict:
    """Read-only board for the review UI. Does not enrol anyone."""
    store = Path(store)
    conn = _ro_connect(store)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise ReviewUiError(f"unknown run: {run_id}")

    clusters = conn.execute(
        """SELECT * FROM clusters WHERE run_id=?
           ORDER BY min_intra ASC, face_count DESC""",
        (run_id,),
    ).fetchall()
    faces = conn.execute(
        """
        SELECT f.*, m.path, m.source_type, m.media_id,
               o.observation_id AS obs_id, o.frame_id, o.t_ms,
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
    persons = conn.execute(
        """SELECT person_id, display_name, status FROM persons
           WHERE status='active' ORDER BY display_name"""
    ).fetchall()

    ignored_faces, ignored_clusters, noted_faces, noted_clusters = _decision_sets(decisions)

    by_cluster: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    for f in faces:
        if f["face_id"] in ignored_faces:
            continue
        rec = {
            "face_id": f["face_id"],
            "observation_id": f["obs_id"],
            "cluster_id": f["cluster_id"],
            "person_id": f["person_id"],
            "person_name": f["person_name"],
            "status": f["status"],
            "source_type": f["source_type"],
            "media_id": f["media_id"],
            "path": f["path"],
            "frame_id": f["frame_id"],
            "t_ms": f["t_ms"],
            "bbox": (f["bbox_x1"], f["bbox_y1"], f["bbox_x2"], f["bbox_y2"]),
            "face_w": f["face_w"],
            "face_h": f["face_h"],
            "has_note": f["face_id"] in noted_faces,
        }
        if f["cluster_id"]:
            by_cluster.setdefault(f["cluster_id"], []).append(rec)
        elif f["status"] == "ok":
            unassigned.append(rec)

    items: list[dict] = []
    for c in clusters:
        if c["status"] in ("ignored", "merged") or c["cluster_id"] in ignored_clusters:
            continue
        members = by_cluster.get(c["cluster_id"], [])
        mi = c["min_intra"]
        band = "review" if (mi is None or mi < strong_min_intra) else "strong"
        person_names = sorted(
            {m["person_name"] for m in members if m["person_name"]}
        )
        items.append(
            {
                "kind": "cluster",
                "cluster_id": c["cluster_id"],
                "band": band,
                # Honest count = faces on the board, not a possibly-stale clusters.face_count.
                "face_count": len(members),
                "min_intra": mi,
                "status": c["status"],
                "person_names": person_names,
                "named": bool(person_names),
                "members": members,
                "has_note": c["cluster_id"] in noted_clusters,
            }
        )

    items.sort(
        key=lambda it: (
            0 if it["band"] == "review" else 1,
            it["min_intra"] is None,
            it["min_intra"] if it["min_intra"] is not None else 0.0,
            -it["face_count"],
        )
    )

    still_unassigned: list[dict] = []
    video_unassigned: list[dict] = []
    for u in unassigned:
        if u["source_type"] == "video":
            video_unassigned.append(u)
        else:
            still_unassigned.append(u)

    track_items, leftover_video, tracks_cache = _track_items(
        store, run_id, video_unassigned, cached=tracks_cache
    )
    items.extend(track_items)
    for u in leftover_video + still_unassigned:
        items.append(
            {
                "kind": "unassigned",
                "face_id": u["face_id"],
                "band": "unassigned",
                "face_count": 1,
                "min_intra": None,
                "status": u["status"],
                "person_names": [u["person_name"]] if u["person_name"] else [],
                "named": bool(u["person_name"]),
                "members": [u],
                "has_note": bool(u.get("has_note")),
            }
        )

    board = {
        "store": str(store.resolve()),
        "run_id": run_id,
        "pack_id": run["pack_id"],
        "strong_min_intra": strong_min_intra,
        "items": items,
        "decisions": [
            {
                "kind": d["kind"],
                "cluster_id": d["cluster_id"],
                "face_id": d["face_id"],
                "person_id": d["person_id"],
                "created_at": d["created_at"],
            }
            for d in decisions
        ],
        "persons": [
            {
                "person_id": p["person_id"],
                "display_name": p["display_name"],
            }
            for p in persons
        ],
        "counts": {
            "clusters": sum(1 for c in clusters if c["status"] != "ignored"),
            "review_required": sum(1 for it in items if it["band"] == "review"),
            "strong": sum(1 for it in items if it["band"] == "strong"),
            "unassigned": len(unassigned),
            "tracks": sum(1 for it in items if it["kind"] == "track"),
            "untracked": sum(
                1
                for it in items
                if it["kind"] == "unassigned"
                and it["members"]
                and it["members"][0].get("source_type") == "video"
            ),
            "named_persons": len(persons),
            "decisions": len(decisions),
            "faces": len(faces),
            "ok": sum(1 for f in faces if f["status"] == "ok"),
            "ignored_faces": len(ignored_faces),
            "ignored_clusters": len(ignored_clusters),
        },
        "empty_state": empty_state_line(store, run_id),
        "_tracks_cache": tracks_cache,
    }
    conn.close()
    return board

def apply_name(store: Path, run_id: str, item: dict, display_name: str) -> dict:
    if item["kind"] == "cluster":
        return name_cluster(store, run_id, item["cluster_id"], display_name)
    if item["kind"] == "track":
        members = [m["face_id"] for m in item.get("members") or []]
        rec = name_faces(
            store,
            run_id,
            members,
            display_name,
            source="track",
            track_id=item.get("track_id"),
        )
        if rec.get("track_id") and rec.get("person_id") and rec["track_id"] == rec["person_id"]:
            raise ReviewUiError("track id must not equal person id")
        return rec
    fid = item.get("face_id")
    if not fid:
        raise ReviewUiError("select an unassigned face to Name")
    return name_face(store, run_id, fid, display_name)

def apply_merge(store: Path, run_id: str, cluster_ids: list[str]) -> dict:
    return merge_clusters(store, run_id, cluster_ids)

def apply_split(store: Path, run_id: str, cluster_id: str, face_ids: list[str]) -> dict:
    return split_cluster(store, run_id, cluster_id, face_ids)

def apply_ignore(store: Path, run_id: str, item: dict, disposition: str | None = None) -> dict:
    if item["kind"] == "cluster":
        return ignore_subject(
            store, run_id, cluster_id=item["cluster_id"], disposition=disposition or "not_a_person"
        )
    fid = item.get("face_id")
    if item["kind"] == "track" and not fid:
        raise ReviewUiError("click a face in the video to Ignore (a track is not a person)")
    # Pass disposition through; backend defaults face ignore to needs-review.
    return ignore_subject(store, run_id, face_id=fid, disposition=disposition)

def apply_rule_out(
    store: Path,
    run_id: str,
    item: dict,
    *,
    person_id: str | None = None,
    text: str | None = None,
) -> dict:
    """Durable Ruled out. Gated by SEMBLON_RULED_OUT (default ON; opt out =0)."""
    if item["kind"] == "cluster":
        return rule_out_subject(
            store,
            run_id,
            cluster_id=item["cluster_id"],
            person_id=person_id,
            text=text,
        )
    fid = item.get("face_id")
    if item["kind"] == "track" and not fid:
        raise ReviewUiError("click a face in the video to Rule out (a track is not a person)")
    if not fid:
        raise ReviewUiError("select a cluster or face to Rule out")
    return rule_out_subject(
        store, run_id, face_id=fid, person_id=person_id, text=text
    )

def apply_note(store: Path, run_id: str, item: dict, text: str) -> dict:
    if item["kind"] == "cluster":
        return note_subject(store, run_id, cluster_id=item["cluster_id"], text=text)
    fid = item.get("face_id")
    if item["kind"] == "track" and not fid:
        raise ReviewUiError("click a face in the video to Note (a track is not a person)")
    return note_subject(store, run_id, face_id=fid, text=text)
