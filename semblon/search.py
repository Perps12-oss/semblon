"""Evidence-based retrieval over owned memory. Not a vector database.

Person search is named-entity lookup. Face search is identify vs persons.
Similarity is not identity. OCR text search is payload substring lookup.
Search does not write the store.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.compare import CompareError, compare_space
from semblon.identify import IdentifyError, identify_face
from semblon.memory import MemoryError, history


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
    """Modality-scoped nearest items. Face identity is forbidden here."""
    conn = _open_ro(store)
    try:
        row = conn.execute(
            """SELECT e.embedding, e.embedding_dim, e.pack_id, e.modality, i.kind, i.provider
               FROM embeddings e JOIN observation_items i ON i.item_id=e.item_id
               WHERE e.item_id=?""",
            (item_id,),
        ).fetchone()
        if row is None:
            raise SearchError(f"no non-identity embedding for item {item_id}")
        if row["modality"] == "face":
            raise SearchError("face identity must use search --face / identify, not --similar")
        others = conn.execute(
            """SELECT e.item_id, e.embedding, e.embedding_dim, e.pack_id, e.modality, i.kind, i.provider
               FROM embeddings e JOIN observation_items i ON i.item_id=e.item_id
               WHERE e.item_id != ? AND e.modality != 'face'""",
            (item_id,),
        ).fetchall()
        scored = []
        for o in others:
            try:
                s = compare_space(
                    row["modality"],
                    row["pack_id"],
                    int(row["embedding_dim"]),
                    row["embedding"],
                    o["modality"],
                    o["pack_id"],
                    int(o["embedding_dim"]),
                    o["embedding"],
                )
            except CompareError:
                continue
            scored.append(
                {
                    "item_id": o["item_id"],
                    "kind": o["kind"],
                    "provider": o["provider"],
                    "score": s,
                    "why": "same modality+pack only; not a person",
                }
            )
    finally:
        conn.close()
    scored.sort(key=lambda x: -x["score"])
    return {
        "kind": "similar",
        "query": item_id,
        "modality": row["modality"],
        "pack_id": row["pack_id"],
        "count": min(limit, len(scored)),
        "items": scored[:limit],
        "note": "Lens-like lookup in owned memory. Similarity is not identity.",
    }


def _text_evidence(payload: dict) -> str:
    """evidence | ran-empty | failed | ignore. Failures are not empty reads."""
    status = str(payload.get("contract_status") or "").upper()
    raw = str(payload.get("status") or "").lower()
    if status in {"UNAVAILABLE", "TIMEOUT", "CANCELLED", "ERROR"} or raw in {
        "unavailable",
        "error",
    }:
        return "failed"
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return "evidence"
    if isinstance(text, str) or status in {"SUCCESS", "NO_RESULT"}:
        return "ran-empty"
    return "ignore"


def search_text(store: Path, query: str, *, limit: int = 50) -> dict:
    """Substring lookup over OCR observation_items payloads. Not identity.

    No new columns. Reads ``kind='text'`` payload_json only. Does not write
    the store and never touches faces.person_id or face embeddings.

    A library with no completed read is UNAVAILABLE, not an empty match.
    A completed read with no hit is NO_RESULT. SUCCESS requires items.
    """
    q = (query or "").strip()
    if not q:
        raise SearchError("text query is empty")
    q_lower = q.lower()
    conn = _open_ro(store)
    try:
        rows = conn.execute(
            """SELECT item_id, observation_id, run_id, provider, score, payload_json
               FROM observation_items
               WHERE kind='text'
               ORDER BY item_id"""
        ).fetchall()
    finally:
        conn.close()
    items = []
    saw_evidence = False
    saw_ran = False
    saw_failed = False
    for r in rows:
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            continue
        kind = _text_evidence(payload)
        if kind == "failed":
            saw_failed = True
            continue
        if kind == "ran-empty":
            saw_ran = True
            continue
        if kind != "evidence":
            continue
        saw_evidence = True
        text = payload.get("text")
        if q_lower not in text.lower():
            continue
        items.append(
            {
                "item_id": r["item_id"],
                "observation_id": r["observation_id"],
                "run_id": r["run_id"],
                "provider": r["provider"],
                "score": r["score"],
                "text": text[:4000],
                "why": "OCR payload substring; not a person",
            }
        )
        if len(items) >= limit:
            break
    note = "OCR text lookup is observation evidence only; not identity."
    if items:
        return {
            "kind": "text",
            "query": q,
            "count": len(items),
            "items": items,
            "status": "SUCCESS",
            "model_state": "AVAILABLE",
            "provider_state": "READY",
            "reason": "Read text ran.",
            "error_id": None,
            "note": note,
        }
    if saw_evidence or saw_ran:
        return {
            "kind": "text",
            "query": q,
            "count": 0,
            "items": [],
            "status": "NO_RESULT",
            "model_state": "AVAILABLE",
            "provider_state": "READY",
            "reason": "Read text ran and nothing matched.",
            "error_id": None,
            "note": note,
        }
    from semblon.runtime_contract import invoke

    if saw_failed:
        result, _ = invoke("ocr")
        reason = "Read text did not run. Nothing was searched."
        error_id = result.error_id or "ocr.UNAVAILABLE"
        model_state = result.model_state
        provider_state = "FAILED"
        status = "UNAVAILABLE" if result.status != "ERROR" else "ERROR"
    else:
        reason = "Read text has no stored reads in this library. Nothing was searched."
        error_id = "ocr.NO_STORED_READ"
        model_state = "MISSING"
        provider_state = "FAILED"
        status = "UNAVAILABLE"
    return {
        "kind": "text",
        "query": q,
        "count": 0,
        "items": [],
        "status": status,
        "model_state": model_state,
        "provider_state": provider_state,
        "reason": reason,
        "error_id": error_id,
        "note": note,
    }
