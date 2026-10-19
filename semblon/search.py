"""Evidence-based retrieval over owned memory. Not a vector database.

Person search is named-entity lookup. Face search is identify vs persons.
Face→similar photos ranks other stills by same-pack face embedding (not a name).
Whole-image / region Similar stay non-identity spaces. OCR text is payload
substring lookup. Search does not write the store.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.compare import CompareError, compare, compare_space
from semblon.identify import IdentifyError, identify_face
from semblon.memory import MemoryError, history
from semblon.similarity_profile import resolve_search_quality


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


_FACE_SIMILAR_BASIS = "Same face"
_FACE_SIMILAR_NOTE = (
    "Face similarity is not a name. Semblon does not auto-assign a person."
)


def search_similar_faces(
    store: Path,
    face_id: str,
    *,
    limit: int = 10,
    threshold: float | None = None,
) -> dict:
    """Rank other photos by same-pack face embedding. Not identify; no writes.

    Uses compare() (pack_id + dim). Cross-pack rows are skipped. Scores below
    the provisional identity_config threshold are excluded (prefer false split).
    Best face score wins per media_id. Seed media is excluded.
    """
    from semblon.identity_config import DEFAULT_THRESHOLD

    fid = (face_id or "").strip()
    thr = DEFAULT_THRESHOLD if threshold is None else float(threshold)
    empty = {
        "kind": "similar_faces",
        "query": face_id,
        "count": 0,
        "items": [],
        "media_ids": [],
        "modality": "face",
        "threshold": thr,
        "similarity_basis": _FACE_SIMILAR_BASIS,
        "note": _FACE_SIMILAR_NOTE,
    }
    if not fid:
        return {
            **empty,
            "status": "UNAVAILABLE",
            "model_state": "MISSING",
            "provider_state": "FAILED",
            "reason": "Select a face on the photo first.",
            "error_id": "similar_faces.NO_FACE",
            "pack_id": None,
        }
    conn = _open_ro(store)
    try:
        seed = conn.execute(
            """SELECT f.face_id, f.embedding, f.embedding_pack, f.embedding_dim,
                      f.status, f.run_id, o.media_id
               FROM faces f
               JOIN observations o ON o.observation_id = f.observation_id
               WHERE f.face_id=?""",
            (fid,),
        ).fetchone()
        if seed is None:
            return {
                **empty,
                "query": fid,
                "status": "UNAVAILABLE",
                "model_state": "MISSING",
                "provider_state": "FAILED",
                "reason": "That face is not in this library.",
                "error_id": "similar_faces.UNKNOWN_FACE",
                "pack_id": None,
            }
        if seed["status"] != "ok" or seed["embedding"] is None:
            return {
                **empty,
                "query": fid,
                "status": "UNAVAILABLE",
                "model_state": "MISSING",
                "provider_state": "FAILED",
                "reason": "This face has no usable embedding yet. Nothing was searched.",
                "error_id": "similar_faces.NO_EMBEDDING",
                "pack_id": seed["embedding_pack"],
                "seed_media_id": seed["media_id"],
            }
        pack_id = str(seed["embedding_pack"] or "")
        dim = int(seed["embedding_dim"])
        seed_media = str(seed["media_id"] or "")
        others = conn.execute(
            """SELECT f.face_id, f.embedding, f.embedding_pack, f.embedding_dim,
                      o.media_id
               FROM faces f
               JOIN observations o ON o.observation_id = f.observation_id
               WHERE f.face_id != ?
                 AND f.status = 'ok'
                 AND f.embedding IS NOT NULL
                 AND f.embedding_pack = ?""",
            (fid, pack_id),
        ).fetchall()
        best_by_media: dict[str, dict] = {}
        for row in others:
            mid = str(row["media_id"] or "")
            if not mid or mid == seed_media:
                continue
            try:
                score = compare(
                    pack_id,
                    dim,
                    seed["embedding"],
                    str(row["embedding_pack"] or ""),
                    int(row["embedding_dim"]),
                    row["embedding"],
                )
            except CompareError:
                continue
            if score < thr:
                continue
            prev = best_by_media.get(mid)
            if prev is None or score > prev["score"]:
                best_by_media[mid] = {
                    "media_id": mid,
                    "face_id": str(row["face_id"]),
                    "score": float(score),
                    "why": "same pack face embedding; not a named person",
                }
    finally:
        conn.close()
    items = sorted(best_by_media.values(), key=lambda x: -x["score"])[: max(0, int(limit))]
    if not items:
        return {
            **empty,
            "query": fid,
            "seed_media_id": seed_media,
            "pack_id": pack_id,
            "status": "NO_RESULT",
            "model_state": "AVAILABLE",
            "provider_state": "READY",
            "reason": "No other photos matched this face at the current threshold.",
            "error_id": None,
        }
    return {
        "kind": "similar_faces",
        "query": fid,
        "seed_media_id": seed_media,
        "pack_id": pack_id,
        "modality": "face",
        "threshold": thr,
        "count": len(items),
        "items": items,
        "media_ids": [it["media_id"] for it in items],
        "status": "SUCCESS",
        "model_state": "AVAILABLE",
        "provider_state": "READY",
        "reason": "Ranked other photos by face embedding (same pack only).",
        "error_id": None,
        "similarity_basis": _FACE_SIMILAR_BASIS,
        "note": _FACE_SIMILAR_NOTE,
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


def _failed_item(conn, item_id: str) -> dict | None:
    """Observation that was stored but never embedded. Not an empty match."""
    row = conn.execute(
        "SELECT kind, payload_json FROM observation_items WHERE item_id=?",
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    status = str(payload.get("contract_status") or "").upper()
    raw = str(payload.get("status") or "").lower()
    failed = status in {"UNAVAILABLE", "ERROR", "TIMEOUT", "CANCELLED"} or raw in {
        "unavailable",
        "error",
    }
    if not failed:
        return {
            "kind": "similar",
            "query": item_id,
            "modality": row["kind"],
            "pack_id": None,
            "count": 0,
            "items": [],
            "status": "UNAVAILABLE",
            "model_state": "MISSING",
            "provider_state": "FAILED",
            "fallback": None,
            "reason": "This item has no embedding yet. Nothing was searched.",
            "error_id": "similar.NO_EMBEDDING",
            "note": "Similar looking is not the same as a named person.",
        }
    out_status = "ERROR" if status == "ERROR" or raw == "error" else "UNAVAILABLE"
    return {
        "kind": "similar",
        "query": item_id,
        "modality": row["kind"],
        "pack_id": None,
        "count": 0,
        "items": [],
        "status": out_status,
        "model_state": "MISSING",
        "provider_state": "FAILED",
        "fallback": None,
        "reason": payload.get("reason")
        or "Similar photos need an optional model. Nothing was searched.",
        "error_id": payload.get("error_id") or f"{row['kind']}.{out_status}",
        "note": "Similar looking is not the same as a named person.",
    }


# Whole-image Similar picks a space on purpose. Region crops are not that space.
_WHOLE_MODALITY_RANK = {"scene": 0, "clip": 1, "appearance": 2}


def non_face_item_for_media(store: Path, media_id: str) -> str | None:
    """Intentional whole-image seed. Scene, then CLIP, then colour. Never lowest UUID."""
    mid = (media_id or "").strip()
    if not mid:
        return None
    conn = _open_ro(store)
    try:
        rows = conn.execute(
            """SELECT e.item_id, e.modality
               FROM embeddings e
               JOIN observation_items i ON i.item_id = e.item_id
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE o.media_id=? AND e.modality NOT IN ('face', 'region')""",
            (mid,),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return None

    def _rank(row) -> tuple[int, str]:
        modality = str(row["modality"] if hasattr(row, "keys") else row[1])
        item_id = str(row["item_id"] if hasattr(row, "keys") else row[0])
        return (_WHOLE_MODALITY_RANK.get(modality, 50), item_id)

    best = sorted(rows, key=_rank)[0]
    return str(best["item_id"] if hasattr(best, "keys") else best[0])


def media_ids_for_items(store: Path, item_ids: list[str]) -> dict[str, str]:
    ids = [str(i) for i in item_ids if i]
    if not ids:
        return {}
    conn = _open_ro(store)
    try:
        qmarks = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"""SELECT i.item_id, o.media_id
                FROM observation_items i
                JOIN observations o ON o.observation_id = i.observation_id
                WHERE i.item_id IN ({qmarks})""",
            ids,
        ).fetchall()
    finally:
        conn.close()
    out: dict[str, str] = {}
    for r in rows:
        iid = str(r["item_id"] if hasattr(r, "keys") else r[0])
        mid = str(r["media_id"] if hasattr(r, "keys") else r[1] or "")
        if iid and mid:
            out[iid] = mid
    return out


def _whole_image_basis_label(modality: str | None, pack_id: str | None) -> str:
    """Product label for whole-image Similar. Colour is named only when it is colour."""
    from semblon.region_encoder import LABEL_COLOUR, LABEL_SIMILAR

    mod = str(modality or "").strip().lower()
    pack = str(pack_id or "").strip().lower()
    if mod in {"scene", "clip"}:
        return LABEL_SIMILAR
    if mod == "appearance" or pack.startswith("appearance/") or "color" in pack or "colour" in pack:
        return LABEL_COLOUR
    if mod:
        return LABEL_SIMILAR
    return LABEL_COLOUR


def search_similar_media(
    store: Path,
    media_id: str,
    *,
    limit: int = 10,
    search_quality: str = "balanced",
) -> dict:
    """Whole-image (B) discovery from a library photo. Honest UNAVAILABLE without embeddings."""
    quality = resolve_search_quality(search_quality)
    target_limit = max(1, min(int(limit or 1), quality.max_results))
    mid = (media_id or "").strip()
    if not mid:
        return {
            "kind": "similar",
            "query": media_id,
            "count": 0,
            "items": [],
            "status": "UNAVAILABLE",
            "model_state": "MISSING",
            "provider_state": "FAILED",
            "reason": "Open a photo, then search Whole image — or type a media id.",
            "error_id": "similar.NO_MEDIA",
            "note": "Whole-image similarity is not identity.",
            "similarity_basis": "Colour only",
            "search_profile": quality.key,
            "search_profile_label": quality.label,
        }
    item = non_face_item_for_media(store, mid)
    if item is None:
        return {
            "kind": "similar",
            "query": mid,
            "count": 0,
            "items": [],
            "status": "UNAVAILABLE",
            "model_state": "MISSING",
            "provider_state": "FAILED",
            "reason": (
                "Whole-image search needs non-identity embeddings for this photo. "
                "Nothing was searched."
            ),
            "error_id": "similar.NO_EMBEDDING",
            "note": "Whole-image similarity is not identity.",
            "similarity_basis": "Colour only",
            "media_ids": [],
            "search_profile": quality.key,
            "search_profile_label": quality.label,
        }
    from semblon.region_encoder import PROVIDER

    modality_row = None
    conn = _open_ro(store)
    try:
        modality_row = conn.execute(
            "SELECT modality FROM embeddings WHERE item_id=?",
            (item,),
        ).fetchone()
    finally:
        conn.close()
    modality_name = str(modality_row["modality"] if modality_row is not None else "")
    floor = quality.whole_colour_floor if modality_name == "appearance" else quality.whole_scene_floor
    probe_limit = max(target_limit * max(1, quality.whole_probe_multiplier), target_limit)
    rec = search_similar(store, item, limit=probe_limit, min_score=floor)
    rec["similarity_basis"] = _whole_image_basis_label(rec.get("modality"), rec.get("pack_id"))
    rec["engine"] = "color-hist" if str(rec.get("modality") or "") == "appearance" else PROVIDER
    rec["seed_media_id"] = mid
    rec["search_profile"] = quality.key
    rec["search_profile_label"] = quality.label
    item_ids = [str(it.get("item_id")) for it in (rec.get("items") or []) if it.get("item_id")]
    mid_map = media_ids_for_items(store, item_ids)
    kept: list[dict] = []
    seen: set[str] = set()
    for it in rec.get("items") or []:
        if not isinstance(it, dict) or it.get("item_id") not in mid_map:
            continue
        media_id = mid_map[it["item_id"]]
        if media_id == mid or media_id in seen:
            continue
        seen.add(media_id)
        it["media_id"] = media_id
        kept.append(it)
        if len(kept) >= target_limit:
            break
    rec["items"] = kept
    rec["count"] = len(kept)
    rec["media_ids"] = [it["media_id"] for it in kept]
    if rec.get("status") == "SUCCESS" and not kept:
        rec["status"] = "NO_RESULT"
        rec["reason"] = "Searched your library and nothing else was close enough."
    return rec


def search_similar(
    store: Path,
    item_id: str,
    *,
    limit: int = 10,
    require_index: bool = False,
    min_score: float | None = None,
) -> dict:
    """Modality-scoped nearest items. Face identity is forbidden here.

    A derived matrix index, when present, is an exact dot-product scan — not an
    approximate nearest-neighbour index. Otherwise the library is scanned and
    the result says so. Demanding a missing index is not an empty match.
    """
    from semblon.index_provider import active_vector_index

    index = active_vector_index()
    if require_index and not index.ready(store):
        return {
            "kind": "similar",
            "query": item_id,
            "modality": None,
            "pack_id": None,
            "count": 0,
            "items": [],
            "status": "UNAVAILABLE",
            "model_state": "MISSING",
            "provider_state": "FAILED",
            "fallback": None,
            "reason": (
                "The fast visual index is not built. Semblon did not fall back "
                "to a library scan because this request required the index."
            ),
            "error_id": "ann_index.INDEX_REQUIRED",
            "note": "Similar looking is not the same as a named person.",
        }
    conn = _open_ro(store)
    try:
        row = conn.execute(
            """SELECT e.embedding, e.embedding_dim, e.pack_id, e.modality, i.kind, i.provider
               FROM embeddings e JOIN observation_items i ON i.item_id=e.item_id
               WHERE e.item_id=?""",
            (item_id,),
        ).fetchone()
        if row is None:
            failed = _failed_item(conn, item_id)
            if failed is not None:
                return failed
            raise SearchError(f"no non-identity embedding for item {item_id}")
        if row["modality"] == "face":
            raise SearchError("face identity must use search --face / identify, not --similar")
        indexed = index.search(
            store,
            item_id=item_id,
            modality=row["modality"],
            pack_id=row["pack_id"],
            vector=row["embedding"],
            dim=int(row["embedding_dim"]),
            limit=limit,
        )
        if indexed is not None:
            scored = indexed
            used_index = True
        else:
            used_index = False
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
                if min_score is not None and float(s) < float(min_score):
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
    if min_score is not None:
        scored = [row for row in scored if float(row.get("score") or 0.0) >= float(min_score)]
    scored.sort(key=lambda x: -x["score"])
    items = scored[:limit]
    note = "Similar looking is not the same as a named person."
    if used_index:
        reason_hit = "Matches from a speed index. Your library stays the source of truth."
        reason_miss = "Nothing matched in the speed index."
        provider = "READY"
        model = "AVAILABLE"
        fallback = None
    else:
        reason_hit = "Searched your library directly (no separate index required)."
        reason_miss = "Searched your library directly and nothing matched."
        provider = "DEGRADED"
        model = "MISSING"
        fallback = "LIBRARY_SCAN"
    if not items:
        return {
            "kind": "similar",
            "query": item_id,
            "modality": row["modality"],
            "pack_id": row["pack_id"],
            "count": 0,
            "items": [],
            "status": "NO_RESULT",
            "model_state": model,
            "provider_state": provider,
            "fallback": fallback,
            "reason": reason_miss,
            "error_id": None,
            "note": note,
        }
    return {
        "kind": "similar",
        "query": item_id,
        "modality": row["modality"],
        "pack_id": row["pack_id"],
        "count": len(items),
        "items": items,
        "status": "SUCCESS",
        "model_state": model,
        "provider_state": provider,
        "fallback": fallback,
        "reason": reason_hit,
        "error_id": None,
        "note": note,
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


def search_text(
    store: Path,
    query: str,
    *,
    limit: int = 50,
    within_media_ids: list[str] | set[str] | None = None,
) -> dict:
    """Substring lookup over OCR observation_items payloads. Not identity.

    No new columns. Reads ``kind='text'`` payload_json only. Does not write
    the store and never touches faces.person_id or face embeddings.

    When ``within_media_ids`` is set (active Field / day / person scope), only
    those media rows can match. A library with no completed read is UNAVAILABLE,
    not an empty match. A completed read with no hit is NO_RESULT.
    """
    q = (query or "").strip()
    if not q:
        raise SearchError("text query is empty")
    q_lower = q.lower()
    scope = {str(m).strip() for m in (within_media_ids or []) if str(m).strip()} or None
    conn = _open_ro(store)
    try:
        rows = conn.execute(
            """SELECT i.item_id, i.observation_id, i.run_id, i.provider, i.score,
                      i.payload_json, o.media_id
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE i.kind='text'
               ORDER BY i.item_id"""
        ).fetchall()
    finally:
        conn.close()
    items = []
    media_ids: list[str] = []
    seen_media: set[str] = set()
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
        mid = str(r["media_id"] or "").strip()
        if scope is not None and mid not in scope:
            continue
        text = payload.get("text")
        if not isinstance(text, str) or q_lower not in text.lower():
            continue
        items.append(
            {
                "item_id": r["item_id"],
                "observation_id": r["observation_id"],
                "media_id": mid,
                "run_id": r["run_id"],
                "provider": r["provider"],
                "score": r["score"],
                "text": text[:4000],
                "why": "OCR payload substring; not a person",
            }
        )
        if mid and mid not in seen_media:
            seen_media.add(mid)
            media_ids.append(mid)
        if len(items) >= limit:
            break
    note = "Text in photos — not a person."
    basis = "Text in photos (OCR substring)"
    if scope is not None:
        basis = f"{basis} · current Field"
    if items:
        return {
            "kind": "text",
            "query": q,
            "count": len(items),
            "items": items,
            "media_ids": media_ids,
            "status": "SUCCESS",
            "model_state": "AVAILABLE",
            "provider_state": "READY",
            "reason": "Found matching text in your photos.",
            "error_id": None,
            "similarity_basis": basis,
            "note": note,
        }
    if saw_evidence or saw_ran:
        reason = (
            "No text matched in the current Field."
            if scope is not None
            else "No text matched in your photos."
        )
        return {
            "kind": "text",
            "query": q,
            "count": 0,
            "items": [],
            "media_ids": [],
            "status": "NO_RESULT",
            "model_state": "AVAILABLE",
            "provider_state": "READY",
            "reason": reason,
            "error_id": None,
            "similarity_basis": basis,
            "note": note,
        }
    from semblon.runtime_contract import invoke

    if saw_failed:
        result, _ = invoke("ocr")
        reason = (
            "Text reading did not finish for these photos. "
            "People search still works for names you have given."
        )
        error_id = result.error_id or "ocr.UNAVAILABLE"
        model_state = result.model_state
        provider_state = "FAILED"
        status = "UNAVAILABLE" if result.status != "ERROR" else "ERROR"
    else:
        reason = (
            "No readable text is stored in this library yet. "
            "Optional text reading may need a component, or photos without text."
        )
        error_id = "ocr.NO_STORED_READ"
        model_state = "MISSING"
        provider_state = "FAILED"
        status = "UNAVAILABLE"
    return {
        "kind": "text",
        "query": q,
        "count": 0,
        "items": [],
        "media_ids": [],
        "status": status,
        "model_state": model_state,
        "provider_state": provider_state,
        "reason": reason,
        "error_id": error_id,
        "similarity_basis": basis,
        "note": note,
    }


_OBJECT_SEARCH_BASIS = "COCO object detection (NanoDet)"
_OBJECT_SEARCH_NOTE = "Object labels are not identity. Contour regions are not detector matches."
_NANODET_PROVIDER = "opencv-zoo-nanodet"


def search_object(
    store: Path,
    query: str,
    *,
    limit: int = 50,
    within_media_ids: list[str] | set[str] | None = None,
) -> dict:
    """Substring / class match over NanoDet object observations. Not identity.

    Contour ``class=region`` rows are ignored. Missing detector pack → UNAVAILABLE.
    Does not write the store or touch faces.person_id.
    """
    from semblon.object_pack import probe_nanodet_status

    q = (query or "").strip()
    basis = _OBJECT_SEARCH_BASIS
    scope = {str(m).strip() for m in (within_media_ids or []) if str(m).strip()} or None
    if scope is not None:
        basis = f"{basis} · current Field"
    empty = {
        "kind": "object",
        "query": query,
        "count": 0,
        "items": [],
        "media_ids": [],
        "similarity_basis": basis,
        "note": _OBJECT_SEARCH_NOTE,
    }
    if not q:
        raise SearchError("object query is empty")
    ready, pack_note = probe_nanodet_status()
    if not ready:
        return {
            **empty,
            "query": q,
            "status": "UNAVAILABLE",
            "model_state": "MISSING",
            "provider_state": "FAILED",
            "reason": pack_note
            or "Object detection needs a NanoDet pack. Contours are not object search.",
            "error_id": "object.PACK_MISSING",
        }
    q_lower = q.lower()
    conn = _open_ro(store)
    try:
        rows = conn.execute(
            """SELECT i.item_id, i.observation_id, i.run_id, i.provider, i.score,
                      i.payload_json, o.media_id
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE i.kind='object' AND i.provider=?
               ORDER BY i.item_id""",
            (_NANODET_PROVIDER,),
        ).fetchall()
    finally:
        conn.close()
    items = []
    media_ids: list[str] = []
    seen_media: set[str] = set()
    saw_label = False
    for r in rows:
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            continue
        if str(payload.get("contract_status") or "").upper() == "UNAVAILABLE":
            continue
        mid = str(r["media_id"] or "").strip()
        if scope is not None and mid not in scope:
            continue
        label = str(payload.get("label") or payload.get("class") or "").strip()
        if not label or label.lower() == "region":
            continue
        saw_label = True
        if q_lower not in label.lower() and q_lower != str(payload.get("class_id") or ""):
            continue
        items.append(
            {
                "item_id": r["item_id"],
                "observation_id": r["observation_id"],
                "media_id": mid,
                "run_id": r["run_id"],
                "provider": r["provider"],
                "score": r["score"],
                "label": label,
                "why": "NanoDet COCO label; not a person",
            }
        )
        if mid and mid not in seen_media:
            seen_media.add(mid)
            media_ids.append(mid)
        if len(items) >= limit:
            break
    if items:
        return {
            "kind": "object",
            "query": q,
            "count": len(items),
            "items": items,
            "media_ids": media_ids,
            "status": "SUCCESS",
            "model_state": "AVAILABLE",
            "provider_state": "READY",
            "reason": f"Found {len(items)} photos with matching object labels.",
            "error_id": None,
            "similarity_basis": basis,
            "note": _OBJECT_SEARCH_NOTE,
        }
    if saw_label:
        return {
            **empty,
            "query": q,
            "status": "NO_RESULT",
            "model_state": "AVAILABLE",
            "provider_state": "READY",
            "reason": "No stored object labels matched.",
            "error_id": None,
        }
    return {
        **empty,
        "query": q,
        "status": "UNAVAILABLE",
        "model_state": "MISSING",
        "provider_state": "FAILED",
        "reason": (
            "No NanoDet object labels are stored yet. "
            "Add the pack and re-scan photos, or search by appearance."
        ),
        "error_id": "object.NO_STORED_LABELS",
    }
