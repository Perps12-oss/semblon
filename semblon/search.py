"""Evidence-based retrieval over owned memory. Not a vector database.

Person search is named-entity lookup. Face search is identify vs persons.
Similarity is not identity.
"""

from __future__ import annotations

from pathlib import Path

from semblon.identify import IdentifyError, identify_face
from semblon.memory import MemoryError, history
from semblon.store import connect, init_db


class SearchError(ValueError):
    pass


def _open(store: Path):
    p = Path(store)
    if not p.is_file():
        raise SearchError(f"store not found: {p}")
    conn = connect(p)
    init_db(conn)
    return conn


def search_person(store: Path, query: str) -> dict:
    """Find active persons by id or display_name. Provenance is the person row."""
    q = (query or "").strip()
    if not q:
        raise SearchError("person query is empty")
    conn = _open(store)
    rows = conn.execute(
        """SELECT person_id, display_name, status, created_run,
                  (SELECT COUNT(*) FROM faces f WHERE f.person_id = p.person_id) AS faces
           FROM persons p
           WHERE status='active'
             AND (person_id = ? OR display_name = ? OR display_name LIKE ?)
           ORDER BY display_name, person_id""",
        (q, q, f"%{q}%"),
    ).fetchall()
    conn.close()
    items = [
        {
            "person_id": r["person_id"],
            "display_name": r["display_name"],
            "status": r["status"],
            "created_run": r["created_run"],
            "faces": int(r["faces"] or 0),
            "why": "named person match (not a cluster, not automatic identity)",
        }
        for r in rows
    ]
    rec = {
        "kind": "person",
        "query": q,
        "count": len(items),
        "items": items,
        "note": "search is lookup of human-named persons; cluster ≠ person",
    }
    if len(items) == 1:
        try:
            rec["history"] = history(store, person=items[0]["person_id"])
        except MemoryError:
            pass
    return rec


def search_face(store: Path, run_id: str, face_id: str) -> dict:
    """1:N identify vs persons. UNKNOWN is valid. Does not enrol."""
    try:
        ident = identify_face(store, run_id, face_id)
    except IdentifyError as e:
        raise SearchError(str(e)) from e
    return {
        "kind": "face",
        "query": face_id,
        "run_id": run_id,
        "identify": ident,
        "why": "identify vs named persons only; does not auto-assign person_id",
        "note": "similarity is not identity",
    }


def search_people(store: Path) -> dict:
    conn = _open(store)
    rows = conn.execute(
        """SELECT person_id, display_name, status,
                  (SELECT COUNT(*) FROM faces f WHERE f.person_id = p.person_id) AS faces
           FROM persons p WHERE status='active'
           ORDER BY display_name, person_id"""
    ).fetchall()
    conn.close()
    items = [
        {
            "person_id": r["person_id"],
            "display_name": r["display_name"],
            "faces": int(r["faces"] or 0),
            "why": "active named person",
        }
        for r in rows
    ]
    return {"kind": "people", "count": len(items), "items": items}
