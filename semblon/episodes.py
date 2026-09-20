"""Derived temporal episodes from persisted tracks.

Episodes are hypotheses for human review. They are not identities.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.process import latest_run_id

DEFAULT_EPISODE_GAP_MS = 3000


class EpisodeError(ValueError):
    pass


def _open_ro(store: Path) -> sqlite3.Connection:
    p = Path(store)
    if not p.is_file():
        raise EpisodeError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _pick_run_id(conn: sqlite3.Connection, store: Path, run_id: str | None) -> str:
    if run_id:
        row = conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise EpisodeError(f"unknown run: {run_id}")
        return run_id
    rid = latest_run_id(store, with_faces=True) or latest_run_id(store)
    if rid is None:
        raise EpisodeError("store has no runs")
    return rid


def derive_episodes(
    store: Path,
    *,
    run_id: str | None = None,
    max_gap_ms: int = DEFAULT_EPISODE_GAP_MS,
) -> dict:
    if max_gap_ms < 0:
        raise EpisodeError("max_gap_ms must be >= 0")
    p = Path(store)
    conn = _open_ro(p)
    try:
        rid = _pick_run_id(conn, p, run_id)
        rows = conn.execute(
            """
            SELECT
              t.track_id,
              t.media_id,
              t.t_ms_start,
              t.t_ms_end,
              t.item_count,
              m.path,
              m.source_type
            FROM tracks t
            JOIN media m ON m.media_id = t.media_id
            WHERE t.run_id=?
            ORDER BY t.media_id, COALESCE(t.t_ms_start, -1), t.track_id
            """,
            (rid,),
        ).fetchall()
        if not rows:
            return {
                "run_id": rid,
                "episodes": [],
                "counts": {"tracks": 0, "episodes": 0, "named_people": 0},
                "note": "No tracks. observation != track != person.",
            }

        person_rows = conn.execute(
            """
            SELECT tm.track_id, f.person_id
            FROM track_members tm
            JOIN observation_items oi ON oi.item_id = tm.item_id
            JOIN faces f ON f.face_id = oi.face_id
            JOIN tracks t ON t.track_id = tm.track_id
            WHERE t.run_id=? AND f.person_id IS NOT NULL
            """,
            (rid,),
        ).fetchall()
        persons_by_track: dict[str, set[str]] = {}
        for r in person_rows:
            persons_by_track.setdefault(r["track_id"], set()).add(r["person_id"])

        by_media: dict[str, list[sqlite3.Row]] = {}
        for r in rows:
            by_media.setdefault(r["media_id"], []).append(r)

        episodes: list[dict] = []
        for media_id, tracks in sorted(by_media.items()):
            cur = None
            idx = 0
            for t in tracks:
                ts = int(t["t_ms_start"] or 0)
                te = int(t["t_ms_end"] or ts)
                if cur is None:
                    idx += 1
                    cur = {
                        "episode_id": f"{media_id}:{idx}",
                        "media_id": media_id,
                        "path": t["path"],
                        "source_type": t["source_type"],
                        "t_ms_start": ts,
                        "t_ms_end": te,
                        "track_ids": [t["track_id"]],
                        "track_count": 1,
                        "item_count": int(t["item_count"] or 0),
                        "person_ids": set(persons_by_track.get(t["track_id"], set())),
                    }
                    continue

                if ts <= int(cur["t_ms_end"]) + int(max_gap_ms):
                    cur["t_ms_end"] = max(int(cur["t_ms_end"]), te)
                    cur["track_ids"].append(t["track_id"])
                    cur["track_count"] = int(cur["track_count"]) + 1
                    cur["item_count"] = int(cur["item_count"]) + int(t["item_count"] or 0)
                    cur["person_ids"].update(persons_by_track.get(t["track_id"], set()))
                else:
                    episodes.append(
                        {
                            **cur,
                            "person_ids": sorted(cur["person_ids"]),
                            "people": len(cur["person_ids"]),
                        }
                    )
                    idx += 1
                    cur = {
                        "episode_id": f"{media_id}:{idx}",
                        "media_id": media_id,
                        "path": t["path"],
                        "source_type": t["source_type"],
                        "t_ms_start": ts,
                        "t_ms_end": te,
                        "track_ids": [t["track_id"]],
                        "track_count": 1,
                        "item_count": int(t["item_count"] or 0),
                        "person_ids": set(persons_by_track.get(t["track_id"], set())),
                    }
            if cur is not None:
                episodes.append(
                    {
                        **cur,
                        "person_ids": sorted(cur["person_ids"]),
                        "people": len(cur["person_ids"]),
                    }
                )

        named_people = set()
        for ep in episodes:
            named_people.update(ep["person_ids"])

        return {
            "run_id": rid,
            "max_gap_ms": int(max_gap_ms),
            "episodes": episodes,
            "counts": {
                "tracks": len(rows),
                "episodes": len(episodes),
                "named_people": len(named_people),
            },
            "note": "Derived episode hypotheses from tracks; observation != track != person.",
        }
    finally:
        conn.close()
