"""S7b: derived temporal tracks.

Track is temporal association inside one video/live Media item.
It is not embedding clustering, not a person, and not a cluster.
Untracked observations stay valid. Fragments are not fused across gaps.
Embeddings never vote on membership (identity firewall).

When persisted `tracks` + `track_members` exist for a run, that snapshot is
canonical for this run and is returned directly. Re-derive only when empty.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

# 1 Hz sampling: allow ~2.5 s gap (≈ one missed sample at 1 Hz + jitter).
# IoU only — no compare().
DEFAULT_IOU_MIN = 0.30
DEFAULT_MAX_T_MS_GAP = 2500


def stable_track_id(media_id: str, face_ids: list[str]) -> str:
    """Membership-stable id. Same face set → same id regardless of order."""
    blob = "|".join(sorted(face_ids)).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:16]
    return f"t-{media_id}-{digest}"


class TracksError(ValueError):
    pass


def bbox_iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = (float(v) for v in a)
    bx1, by1, bx2, by2 = (float(v) for v in b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _face_rec(row) -> dict:
    return {
        "face_id": row["face_id"],
        "observation_id": row["observation_id"],
        "media_id": row["media_id"],
        "path": row["path"],
        "frame_id": row["frame_id"],
        "t_ms": row["t_ms"],
        "bbox": (row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]),
        "face_w": row["face_w"],
        "face_h": row["face_h"],
        "person_id": row["person_id"],
        "cluster_id": row["cluster_id"],
    }


def _source_faces(conn, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT f.face_id, f.observation_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
               f.face_w, f.face_h, f.person_id, f.cluster_id,
               m.media_id, m.path, o.frame_id, o.t_ms
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.run_id=? AND f.status='ok' AND m.source_type IN ('video','live')
        ORDER BY m.media_id, o.t_ms, o.frame_id, f.face_id
        """,
        (run_id,),
    ).fetchall()
    return [_face_rec(r) for r in rows]


def _associate_media(
    faces: list[dict],
    *,
    iou_min: float,
    max_t_ms_gap: int,
) -> tuple[list[list[dict]], list[dict]]:
    """Greedy IoU+time matching. Exclusive per frame. No embeddings."""
    ordered = sorted(
        faces,
        key=lambda f: (
            f["t_ms"] is None,
            f["t_ms"] if f["t_ms"] is not None else 0,
            f["frame_id"] is None,
            f["frame_id"] if f["frame_id"] is not None else 0,
            f["face_id"],
        ),
    )
    pending: list[list[dict]] = []
    for face in ordered:
        best_i = None
        best_iou = -1.0
        ft = face["t_ms"]
        for i, members in enumerate(pending):
            last = members[-1]
            lt = last["t_ms"]
            if ft is None or lt is None:
                continue
            if ft <= lt:
                continue
            if ft - lt > max_t_ms_gap:
                continue
            iou = bbox_iou(face["bbox"], last["bbox"])
            if iou >= iou_min and iou > best_iou:
                best_iou = iou
                best_i = i
        if best_i is None:
            pending.append([face])
        else:
            pending[best_i].append(face)

    tracks = [m for m in pending if len(m) >= 2]
    untracked = [m[0] for m in pending if len(m) == 1]
    return tracks, untracked


def _track_payload(members: list[dict], *, track_id: str | None = None) -> dict:
    first = members[0]
    last = members[-1]
    face_ids = [m["face_id"] for m in members]
    # Area first; tie-break by earliest face_id (stable, O(N), no index()).
    rep = max(
        members,
        key=lambda m: (int(m["face_w"] or 0) * int(m["face_h"] or 0), m["face_id"]),
    )
    return {
        "track_id": track_id or stable_track_id(first["media_id"], face_ids),
        "media_id": first["media_id"],
        "path": first["path"],
        "face_ids": face_ids,
        "observation_ids": [m["observation_id"] for m in members],
        "face_count": len(members),
        "frame_id_start": first["frame_id"],
        "frame_id_end": last["frame_id"],
        "t_ms_start": first["t_ms"],
        "t_ms_end": last["t_ms"],
        "representative_face_id": rep["face_id"],
        "members": members,
        "note": "temporal association; not a person; not a cluster",
    }


def _payload_from_persisted(conn, run_id: str, *, iou_min: float, max_t_ms_gap: int) -> dict | None:
    n_tracks = int(conn.execute("SELECT COUNT(*) FROM tracks WHERE run_id=?", (run_id,)).fetchone()[0])
    if n_tracks == 0:
        return None

    rows = conn.execute(
        """
        SELECT tm.track_id, tm.t_ms AS member_t_ms,
               oi.item_id, oi.face_id, oi.observation_id,
               oi.bbox_x1, oi.bbox_y1, oi.bbox_x2, oi.bbox_y2,
               o.media_id, o.frame_id, o.t_ms AS obs_t_ms, m.path,
               f.face_w, f.face_h, f.person_id, f.cluster_id
        FROM track_members tm
        JOIN tracks t ON t.track_id = tm.track_id
        JOIN observation_items oi ON oi.item_id = tm.item_id
        JOIN observations o ON o.observation_id = oi.observation_id
        JOIN media m ON m.media_id = o.media_id
        LEFT JOIN faces f ON f.face_id = oi.face_id
        WHERE t.run_id=?
        ORDER BY tm.track_id,
                 COALESCE(tm.t_ms, o.t_ms, -1),
                 COALESCE(o.frame_id, -1),
                 oi.item_id
        """,
        (run_id,),
    ).fetchall()
    if not rows:
        # Legacy rows with empty memberships should re-derive from faces.
        return None

    by_track: dict[str, list[dict]] = {}
    for r in rows:
        face_id = r["face_id"] or f"item:{r['item_id']}"
        t_ms = r["member_t_ms"] if r["member_t_ms"] is not None else r["obs_t_ms"]
        bw = bh = 0
        if None not in (r["bbox_x1"], r["bbox_x2"], r["bbox_y1"], r["bbox_y2"]):
            bw = max(0, int(round(float(r["bbox_x2"]) - float(r["bbox_x1"]))))
            bh = max(0, int(round(float(r["bbox_y2"]) - float(r["bbox_y1"]))))
        member = {
            "face_id": face_id,
            "observation_id": r["observation_id"],
            "media_id": r["media_id"],
            "path": r["path"],
            "frame_id": r["frame_id"],
            "t_ms": t_ms,
            "bbox": (r["bbox_x1"], r["bbox_y1"], r["bbox_x2"], r["bbox_y2"]),
            "face_w": int(r["face_w"] or bw),
            "face_h": int(r["face_h"] or bh),
            "person_id": r["person_id"],
            "cluster_id": r["cluster_id"],
        }
        by_track.setdefault(r["track_id"], []).append(member)

    tracks: list[dict] = []
    tracked_face_ids: set[str] = set()
    for track_id, members in by_track.items():
        members_sorted = sorted(
            members,
            key=lambda m: (
                m["t_ms"] is None,
                m["t_ms"] if m["t_ms"] is not None else 0,
                m["frame_id"] is None,
                m["frame_id"] if m["frame_id"] is not None else 0,
                m["face_id"],
            ),
        )
        if len(members_sorted) < 2:
            continue
        tracks.append(_track_payload(members_sorted, track_id=track_id))
        for m in members_sorted:
            if not str(m["face_id"]).startswith("item:"):
                tracked_face_ids.add(m["face_id"])

    all_faces = _source_faces(conn, run_id)
    untracked = [f for f in all_faces if f["face_id"] not in tracked_face_ids]
    tracked_faces = sum(t["face_count"] for t in tracks)
    return {
        "run_id": run_id,
        "store": None,
        "iou_min": iou_min,
        "max_t_ms_gap": max_t_ms_gap,
        "tracks": tracks,
        "untracked": untracked,
        "counts": {
            "video_ok_faces": len(all_faces),
            "tracks": len(tracks),
            "tracked_faces": tracked_faces,
            "untracked": len(untracked),
            "media": len({f['media_id'] for f in all_faces}),
        },
        "note": "persisted S7 tracks snapshot is canonical for this run; track ≠ person",
    }


def _derive_from_faces(conn, run_id: str, *, iou_min: float, max_t_ms_gap: int) -> dict:
    by_media: dict[str, list[dict]] = {}
    faces = _source_faces(conn, run_id)
    for rec in faces:
        by_media.setdefault(rec["media_id"], []).append(rec)

    tracks: list[dict] = []
    untracked: list[dict] = []
    for media_id in sorted(by_media):
        media_tracks, media_untracked = _associate_media(
            by_media[media_id], iou_min=iou_min, max_t_ms_gap=max_t_ms_gap
        )
        tracks.extend(_track_payload(m) for m in media_tracks)
        untracked.extend(media_untracked)

    tracked_faces = sum(t["face_count"] for t in tracks)
    return {
        "run_id": run_id,
        "store": None,
        "iou_min": iou_min,
        "max_t_ms_gap": max_t_ms_gap,
        "tracks": tracks,
        "untracked": untracked,
        "counts": {
            "video_ok_faces": len(faces),
            "tracks": len(tracks),
            "tracked_faces": tracked_faces,
            "untracked": len(untracked),
            "media": len(by_media),
        },
        "note": (
            "derived S7b tracks; not written to the store; "
            "observation ≠ track ≠ person; embeddings did not vote"
        ),
    }


def derive_tracks(
    store: Path,
    run_id: str,
    *,
    iou_min: float = DEFAULT_IOU_MIN,
    max_t_ms_gap: int = DEFAULT_MAX_T_MS_GAP,
    prefer_persisted: bool = True,
) -> dict:
    """Read tracks for one run. Uses persisted snapshot when available."""
    store = Path(store)
    if not store.is_file():
        raise TracksError(f"store not found: {store}")
    if iou_min <= 0 or iou_min > 1:
        raise TracksError("iou_min must be in (0, 1]")
    if max_t_ms_gap <= 0:
        raise TracksError("max_t_ms_gap must be > 0")

    conn = sqlite3.connect(f"file:{store.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    run = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise TracksError(f"unknown run: {run_id}")

    if prefer_persisted:
        persisted = _payload_from_persisted(
            conn,
            run_id,
            iou_min=iou_min,
            max_t_ms_gap=max_t_ms_gap,
        )
        if persisted is not None:
            conn.close()
            persisted["store"] = str(store.resolve())
            return persisted

    rec = _derive_from_faces(
        conn,
        run_id,
        iou_min=iou_min,
        max_t_ms_gap=max_t_ms_gap,
    )
    conn.close()
    rec["store"] = str(store.resolve())
    return rec
