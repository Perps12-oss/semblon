"""Non-identity visual retrieval layer.

Face identity queries belong to identify.py. This module handles retrieval over
non-face observation spaces only.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import cv2

from semblon.compare import CompareError, compare_space
from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, clip_embed, color_histogram


class RetrievalError(ValueError):
    pass


def _open_ro(store: Path) -> sqlite3.Connection:
    p = Path(store)
    if not p.is_file():
        raise RetrievalError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _load_item_embedding(conn: sqlite3.Connection, item_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT e.item_id, e.embedding, e.embedding_dim, e.pack_id, e.modality, i.kind, i.provider
        FROM embeddings e
        JOIN observation_items i ON i.item_id = e.item_id
        WHERE e.item_id=?
        """,
        (item_id,),
    ).fetchone()
    if row is None:
        raise RetrievalError(f"no non-identity embedding for item {item_id}")
    if row["modality"] == "face":
        raise RetrievalError("face identity must use identify/search --face, not retrieval")
    return row


def _candidate_rows(
    conn: sqlite3.Connection,
    *,
    item_id: str | None = None,
    modality: str | None = None,
    provider: str | None = None,
    pack_id: str | None = None,
) -> list[sqlite3.Row]:
    clauses = ["e.modality != 'face'"]
    args: list = []
    if item_id:
        clauses.append("e.item_id != ?")
        args.append(item_id)
    if modality:
        clauses.append("e.modality = ?")
        args.append(modality)
    if provider:
        clauses.append("i.provider = ?")
        args.append(provider)
    if pack_id:
        clauses.append("e.pack_id = ?")
        args.append(pack_id)
    where = " AND ".join(clauses)
    return conn.execute(
        f"""
        SELECT e.item_id, e.embedding, e.embedding_dim, e.pack_id, e.modality, i.kind, i.provider
        FROM embeddings e
        JOIN observation_items i ON i.item_id = e.item_id
        WHERE {where}
        ORDER BY e.item_id
        """,
        args,
    ).fetchall()


def _score_candidates(
    query: sqlite3.Row | dict,
    rows: list[sqlite3.Row],
) -> list[dict]:
    scored = []
    for o in rows:
        try:
            score = compare_space(
                str(query["modality"]),
                str(query["pack_id"]),
                int(query["embedding_dim"]),
                query["embedding"],
                str(o["modality"]),
                str(o["pack_id"]),
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
                "modality": o["modality"],
                "pack_id": o["pack_id"],
                "score": float(score),
                "why": "same modality+pack space",
            }
        )
    scored.sort(key=lambda x: (-x["score"], x["item_id"]))
    return scored


def similar_from_item(
    store: Path,
    item_id: str,
    *,
    limit: int = 10,
    modality: str | None = None,
    provider: str | None = None,
    pack_id: str | None = None,
) -> dict:
    conn = _open_ro(store)
    try:
        query = _load_item_embedding(conn, item_id)
        rows = _candidate_rows(
            conn,
            item_id=item_id,
            modality=modality,
            provider=provider,
            pack_id=pack_id,
        )
        scored = _score_candidates(query, rows)
        return {
            "kind": "similar",
            "query": item_id,
            "modality": query["modality"],
            "pack_id": query["pack_id"],
            "count": min(limit, len(scored)),
            "items": scored[:limit],
            "note": "non-identity retrieval only",
        }
    finally:
        conn.close()


def _query_spaces_from_image(path: Path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        raise RetrievalError(f"image not found: {p}")
    img = cv2.imread(str(p))
    if img is None:
        raise RetrievalError(f"cannot decode image: {p}")
    out = [
        {
            "source": "appearance",
            "modality": "appearance",
            "pack_id": APPEARANCE_PACK,
            "embedding_dim": APPEARANCE_DIM,
            "embedding": color_histogram(img),
            "why": "global color histogram",
        }
    ]
    clip = clip_embed(img)
    if clip and not clip.get("error") and clip.get("embedding"):
        out.append(
            {
                "source": "clip",
                "modality": "clip",
                "pack_id": clip["pack_id"],
                "embedding_dim": int(clip["dim"]),
                "embedding": clip["embedding"],
                "why": "clip visual embedding",
            }
        )
    return out


def query_by_image(
    store: Path,
    image: Path,
    *,
    limit: int = 20,
    modality: str | None = None,
    provider: str | None = None,
    pack_id: str | None = None,
) -> dict:
    conn = _open_ro(store)
    try:
        spaces = _query_spaces_from_image(image)
        merged: dict[str, dict] = {}
        for q in spaces:
            if modality and q["modality"] != modality:
                continue
            rows = _candidate_rows(
                conn,
                modality=q["modality"],
                provider=provider,
                pack_id=pack_id or q["pack_id"],
            )
            scored = _score_candidates(q, rows)
            for item in scored:
                rec = merged.get(item["item_id"])
                if rec is None:
                    merged[item["item_id"]] = {
                        **item,
                        "sources": [q["source"]],
                        "source_why": [q["why"]],
                    }
                    continue
                if float(item["score"]) > float(rec["score"]):
                    rec["score"] = item["score"]
                    rec["why"] = item["why"]
                if q["source"] not in rec["sources"]:
                    rec["sources"].append(q["source"])
                    rec["source_why"].append(q["why"])
        items = list(merged.values())
        items.sort(key=lambda x: (-x["score"], x["item_id"]))
        return {
            "kind": "query_image",
            "query": str(Path(image)),
            "spaces_used": [q["source"] for q in spaces if not modality or q["modality"] == modality],
            "count": min(int(limit), len(items)),
            "items": items[: int(limit)],
            "filters": {
                "modality": modality,
                "provider": provider,
                "pack_id": pack_id,
            },
            "note": "non-identity retrieval only; face identity stays in identify.py",
        }
    finally:
        conn.close()


def query_text(
    store: Path,
    text: str,
    *,
    limit: int = 20,
) -> dict:
    q = (text or "").strip()
    if not q:
        raise RetrievalError("text query is empty")
    conn = _open_ro(store)
    try:
        rows = conn.execute(
            """
            SELECT item_id, provider, payload_json
            FROM observation_items
            WHERE kind='text' AND (
              json_extract(payload_json, '$.text') LIKE ? ESCAPE '\\'
              OR payload_json LIKE ? ESCAPE '\\'
            )
            ORDER BY item_id
            LIMIT ?
            """,
            (f"%{q.replace('%', '\\%').replace('_', '\\_')}%", f"%{q.replace('%', '\\%').replace('_', '\\_')}%", int(limit)),
        ).fetchall()
    finally:
        conn.close()
    items = []
    for r in rows:
        payload = {}
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        snippet = str(payload.get("text") or "")[:160]
        items.append(
            {
                "item_id": r["item_id"],
                "kind": "text",
                "provider": r["provider"],
                "score": 1.0,
                "snippet": snippet,
                "why": "text payload match",
            }
        )
    return {
        "kind": "query_text",
        "query": q,
        "count": len(items),
        "items": items,
        "note": "OCR/text retrieval over stored non-identity observations",
    }
