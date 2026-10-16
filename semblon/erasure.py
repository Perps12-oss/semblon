"""Erase biometric rows. This is not Reset, which keeps the library on purpose.

Original photo and video files are never deleted. Names are not returned.
"""

from __future__ import annotations

from pathlib import Path

from semblon.store import (
    LIBRARY_TABLES,
    connect,
    exec_in_chunks,
    init_db,
    rows_in_chunks,
    writer_lock,
)


class ErasureError(ValueError):
    pass


def delete_person(store: Path, person_id: str) -> dict:
    """Delete one person and the face templates, decisions, and links for them."""
    person_id = str(person_id or "").strip()
    if not person_id:
        raise ErasureError("person_id is required")
    conn = connect(Path(store))
    init_db(conn)
    try:
        row = conn.execute(
            "SELECT person_id FROM persons WHERE person_id=?",
            (person_id,),
        ).fetchone()
        if row is None:
            raise ErasureError(f"unknown person: {person_id}")
        face_ids = [
            r[0]
            for r in conn.execute(
                "SELECT face_id FROM faces WHERE person_id=?",
                (person_id,),
            ).fetchall()
        ]
        obs_ids = []
        if face_ids:
            obs_ids = [
                r[0]
                for r in rows_in_chunks(
                    conn,
                    "SELECT DISTINCT observation_id FROM faces WHERE face_id IN",
                    face_ids,
                )
            ]
        with writer_lock():
            conn.execute("DELETE FROM cluster_person WHERE person_id=?", (person_id,))
            conn.execute("DELETE FROM decisions WHERE person_id=?", (person_id,))
            conn.execute(
                "DELETE FROM relationships WHERE src_person_id=?",
                (person_id,),
            )
            if face_ids:
                exec_in_chunks(conn, "DELETE FROM decisions WHERE face_id IN", face_ids)
            # Other faces may share the observation. Delete only this person's faces.
            if face_ids:
                item_ids = [
                    r[0]
                    for r in rows_in_chunks(
                        conn,
                        "SELECT item_id FROM observation_items WHERE face_id IN",
                        face_ids,
                    )
                ]
                if item_ids:
                    exec_in_chunks(conn, "DELETE FROM group_members WHERE item_id IN", item_ids)
                    exec_in_chunks(conn, "DELETE FROM track_members WHERE item_id IN", item_ids)
                    exec_in_chunks(conn, "DELETE FROM embeddings WHERE item_id IN", item_ids)
                    exec_in_chunks(
                        conn, "DELETE FROM relationships WHERE src_item_id IN", item_ids
                    )
                    exec_in_chunks(
                        conn, "DELETE FROM relationships WHERE dst_item_id IN", item_ids
                    )
                    exec_in_chunks(
                        conn, "DELETE FROM observation_items WHERE item_id IN", item_ids
                    )
                exec_in_chunks(conn, "DELETE FROM eval_pairs WHERE face_a IN", face_ids)
                exec_in_chunks(conn, "DELETE FROM eval_pairs WHERE face_b IN", face_ids)
                exec_in_chunks(conn, "DELETE FROM faces WHERE face_id IN", face_ids)
            conn.execute("DELETE FROM persons WHERE person_id=?", (person_id,))
            conn.commit()
        return {
            "person_id": person_id,
            "faces_deleted": len(face_ids),
            "observations_touched": len(obs_ids),
            "erased": True,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def wipe_library(store: Path) -> dict:
    """Delete library rows. Does not delete original files or reset preferences."""
    conn = connect(Path(store))
    init_db(conn)
    cleared: list[str] = []
    try:
        with writer_lock():
            conn.commit()
            previous = conn.isolation_level
            conn.isolation_level = None
            try:
                conn.execute("PRAGMA foreign_keys=OFF")
                conn.execute("BEGIN IMMEDIATE")
                try:
                    for table in LIBRARY_TABLES:
                        row = conn.execute(
                            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                            (table,),
                        ).fetchone()
                        if row is None:
                            continue
                        conn.execute(f"DELETE FROM {table}")
                        cleared.append(table)
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
                conn.execute("PRAGMA foreign_keys=ON")
            finally:
                conn.isolation_level = previous
        return {"erased": True, "tables": cleared, "files_deleted": False}
    finally:
        conn.close()
