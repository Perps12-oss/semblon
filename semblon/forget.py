"""Take pictures out of the library after their files were moved to the Recycle Bin.

The library lists only pictures that exist. When a file goes to the Bin, everything the library
learned from it (the entry, the faces found in it, their saved looks) is removed, so it can no longer
appear in the Roll, in People or in a search. Nothing on disk is touched. If the file is restored
from the Bin, looking through its folder again adds it back like any new picture.
"""

from __future__ import annotations

from pathlib import Path

from semblon.store import (
    connect,
    delete_observation_tree,
    exec_in_chunks,
    init_db,
    rows_in_chunks,
    writer_lock,
)


def forget_files(store: Path, paths: list[str], keep: list[str] | None = None) -> int:
    """Remove the library entries for these file paths. Returns how many pictures were removed.

    ``keep`` lists files that stay. An exact copy shares its entry with the copy that stays, so that
    entry is pointed at the kept file instead of being removed.
    """
    wanted = [str(p) for p in paths if p]
    if not wanted or not Path(store).is_file():
        return 0
    conn = connect(Path(store))
    init_db(conn)
    removed = 0
    try:
        with writer_lock():
            media_ids = [
                r[0]
                for r in rows_in_chunks(conn, "SELECT media_id FROM media WHERE path IN", wanted)
            ]
            clusters: set[str] = set()
            for media_id in media_ids:
                if keep:
                    marks = ",".join("?" * len(keep))
                    kept = conn.execute(
                        f"SELECT path FROM work_items WHERE media_id=? AND path IN ({marks})",
                        (media_id, *keep),
                    ).fetchone()
                    if kept:
                        conn.execute("UPDATE media SET path=? WHERE media_id=?", (kept[0], media_id))
                        continue
                for (obs_id,) in conn.execute(
                    "SELECT observation_id FROM observations WHERE media_id=?", (media_id,)
                ).fetchall():
                    for (cid,) in conn.execute(
                        "SELECT DISTINCT cluster_id FROM faces WHERE observation_id=? AND cluster_id IS NOT NULL",
                        (obs_id,),
                    ).fetchall():
                        clusters.add(cid)
                    delete_observation_tree(conn, obs_id)
                track_ids = [r[0] for r in conn.execute("SELECT track_id FROM tracks WHERE media_id=?", (media_id,))]
                if track_ids:
                    exec_in_chunks(conn, "DELETE FROM track_members WHERE track_id IN", track_ids)
                    exec_in_chunks(conn, "DELETE FROM tracks WHERE track_id IN", track_ids)
                conn.execute("DELETE FROM media WHERE media_id=?", (media_id,))
                removed += 1
            exec_in_chunks(conn, "DELETE FROM work_items WHERE path IN", wanted)
            if clusters:
                from semblon.erasure import _clear_centroids_after_erasure

                _clear_centroids_after_erasure(conn, sorted(clusters))
            conn.commit()
    finally:
        conn.close()
    return removed
