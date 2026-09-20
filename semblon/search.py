"""Evidence-based retrieval over owned memory. Not a vector database.

Person search is named-entity lookup. Face search is identify vs persons.
Similarity is not identity. Search does not write the store.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.identify import IdentifyError, identify_face
from semblon.memory import MemoryError, history
from semblon.observers import ocr_image
from semblon.retrieval import RetrievalError, query_by_image, query_text, similar_from_item


class SearchError(ValueError):
    pass


def _open_ro(store: Path) -> sqlite3.Connection:
    p = Path(store)
    if not p.is_file():
        raise SearchError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _open(store: Path) -> sqlite3.Connection:
    """Compatibility alias for tests and legacy callers."""
    return _open_ro(store)


def _like_pattern(q: str) -> str:
    """Escape LIKE wildcards so user input is literal substring match."""
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def search_person(store: Path, query: str) -> dict:
    """Find active persons by id or display_name. Provenance is the person row."""
    q = (query or "").strip()
    if not q:
        raise SearchError("person query is empty")
    conn = _open_ro(store)
    try:
        rows = conn.execute(
            """SELECT person_id, display_name, status, created_run,
                      (SELECT COUNT(*) FROM faces f WHERE f.person_id = p.person_id) AS faces
               FROM persons p
               WHERE status='active'
                 AND (person_id = ? OR display_name = ? OR display_name LIKE ? ESCAPE '\\')
               ORDER BY display_name, person_id""",
            (q, q, _like_pattern(q)),
        ).fetchall()
    finally:
        conn.close()
    items = []
    for r in rows:
        if r["person_id"] == q:
            why = "person_id exact"
        elif r["display_name"] == q:
            why = "display_name exact"
        else:
            why = "display_name substring"
        items.append(
            {
                "person_id": r["person_id"],
                "display_name": r["display_name"],
                "status": r["status"],
                "created_run": r["created_run"],
                "faces": int(r["faces"] or 0),
                "why": why,
            }
        )
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
    """1:N identify vs persons. UNKNOWN is valid. Does not enrol or write decisions."""
    try:
        ident = identify_face(store, run_id, face_id, record=False)
    except IdentifyError as e:
        raise SearchError(str(e)) from e
    return {
        "kind": "face",
        "query": face_id,
        "run_id": run_id,
        "identify": ident,
        "why": "identify vs named persons only; does not auto-assign person_id",
        "note": "similarity is not identity; search does not write decisions",
    }


def search_people(store: Path) -> dict:
    conn = _open_ro(store)
    try:
        rows = conn.execute(
            """SELECT person_id, display_name, status,
                      (SELECT COUNT(*) FROM faces f WHERE f.person_id = p.person_id) AS faces
               FROM persons p WHERE status='active'
               ORDER BY display_name, person_id"""
        ).fetchall()
    finally:
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


def search_similar(store: Path, item_id: str, *, limit: int = 10) -> dict:
    try:
        return similar_from_item(store, item_id, limit=limit)
    except RetrievalError as e:
        raise SearchError(str(e)) from e


def search_image(
    store: Path,
    image: Path,
    *,
    limit: int = 20,
    modality: str | None = None,
    provider: str | None = None,
    pack_id: str | None = None,
) -> dict:
    """Query-by-image retrieval over non-identity spaces."""
    try:
        return query_by_image(
            store,
            image,
            limit=limit,
            modality=modality,
            provider=provider,
            pack_id=pack_id,
        )
    except RetrievalError as e:
        raise SearchError(str(e)) from e


def search_text(store: Path, text: str, *, limit: int = 20) -> dict:
    """OCR/text retrieval over non-identity observations."""
    try:
        return query_text(store, text, limit=limit)
    except RetrievalError as e:
        raise SearchError(str(e)) from e


def _people_from_retrieved_items(conn, item_ids: list[str], *, limit: int = 8) -> list[dict]:
    if not item_ids:
        return []
    marks = ",".join(["?"] * len(item_ids))
    rows = conn.execute(
        f"""
        SELECT
          p.person_id,
          p.display_name,
          COUNT(*) AS hits,
          COUNT(DISTINCT oi.item_id) AS matched_items
        FROM observation_items oi
        JOIN faces f ON f.observation_id = oi.observation_id
        JOIN persons p ON p.person_id = f.person_id
        WHERE oi.item_id IN ({marks})
          AND f.person_id IS NOT NULL
          AND p.status='active'
        GROUP BY p.person_id, p.display_name
        ORDER BY hits DESC, matched_items DESC, p.display_name, p.person_id
        LIMIT ?
        """,
        [*item_ids, int(limit)],
    ).fetchall()
    return [
        {
            "person_id": r["person_id"],
            "display_name": r["display_name"],
            "hits": int(r["hits"] or 0),
            "matched_items": int(r["matched_items"] or 0),
            "why": "named person appears in observations linked to retrieved items",
        }
        for r in rows
    ]


def _memory_sections(store: Path, people: list[dict], *, max_people: int = 5) -> tuple[list[dict], list[dict]]:
    memories: list[dict] = []
    videos: list[dict] = []
    seen_video = set()
    for p in people[:max_people]:
        try:
            rec = history(store, person=p["person_id"])
        except MemoryError:
            continue
        memories.append(
            {
                "person_id": p["person_id"],
                "display_name": p.get("display_name"),
                "sightings": rec.get("sightings", 0),
                "presence_count": len(rec.get("presence") or []),
                "why": "person memory timeline",
            }
        )
        for pr in rec.get("presence") or []:
            key = (pr.get("media_id"), p["person_id"])
            if key in seen_video:
                continue
            seen_video.add(key)
            videos.append(
                {
                    "person_id": p["person_id"],
                    "display_name": p.get("display_name"),
                    "media_id": pr.get("media_id"),
                    "path": pr.get("path"),
                    "t_ms_start": pr.get("t_ms_start"),
                    "t_ms_end": pr.get("t_ms_end"),
                    "sightings": pr.get("sightings"),
                    "why": "video presence interval from memory",
                }
            )
    videos.sort(key=lambda r: (str(r.get("path") or ""), str(r.get("media_id") or "")))
    return memories, videos


def _query_text_from_image(store: Path, image: Path, *, limit: int = 20) -> dict:
    import cv2

    img = cv2.imread(str(image))
    if img is None:
        return {"status": "error", "reason": "cannot decode image", "query_text": "", "matches": []}
    ocr = ocr_image(img)
    if ocr is None:
        return {"status": "unavailable", "reason": "ocr library unavailable", "query_text": "", "matches": []}
    if ocr.get("error"):
        return {
            "status": "error",
            "reason": str(ocr.get("error")),
            "query_text": "",
            "matches": [],
        }
    text = str(ocr.get("text") or "").strip()
    if not text:
        return {"status": "ok", "reason": "no text extracted", "query_text": "", "matches": []}
    rec = search_text(store, text, limit=limit)
    return {"status": "ok", "reason": "ocr text query", "query_text": text, "matches": rec.get("items") or []}


def search_lens_workflow(
    store: Path,
    image: Path,
    *,
    limit: int = 24,
    modality: str | None = None,
    provider: str | None = None,
    pack_id: str | None = None,
) -> dict:
    """One coherent Lens-style local workflow over non-identity retrieval + memory."""
    img_rec = search_image(
        store,
        image,
        limit=limit,
        modality=modality,
        provider=provider,
        pack_id=pack_id,
    )
    items = list(img_rec.get("items") or [])
    item_ids = [str(i.get("item_id")) for i in items if i.get("item_id")]
    conn = _open_ro(store)
    try:
        people = _people_from_retrieved_items(conn, item_ids, limit=8)
    finally:
        conn.close()

    memories, related_videos = _memory_sections(store, people, max_people=5)
    text_q = _query_text_from_image(store, image, limit=max(8, limit))
    objects = [i for i in items if i.get("kind") == "object"]
    concepts = [i for i in items if i.get("kind") == "clip" or i.get("modality") == "clip"]
    similar_images = [i for i in items if i.get("kind") in {"appearance", "clip", "object", "text", "pose"}]

    return {
        "kind": "lens_workflow",
        "query": str(Path(image)),
        "count": len(items),
        "sections": {
            "people": people,
            "similar_images": similar_images,
            "objects": objects,
            "text": text_q,
            "visual_concepts": concepts,
            "related_memories": memories,
            "related_videos": related_videos,
        },
        "filters": {
            "modality": modality,
            "provider": provider,
            "pack_id": pack_id,
            "limit": int(limit),
        },
        "identity_firewall": {
            "face_identity_path": "identify.py",
            "retrieval_path": "retrieval.py/search.py non-identity spaces",
            "note": "face results remain identity semantics; retrieval is evidence only",
        },
        "note": "Local Lens-style retrieval + memory workflow; no cloud/web lookup.",
    }
