"""Find similar from a persisted user box.

Primary space: indexed region embeddings from the installed local encoder
(same pack and preprocess as the query crop). Colour histograms are the
labelled fallback when that encoder or its index is absent.

Does not write an embedding row for the query. Does not create a sibling item.
Face identity is forbidden. A region query never scans whole-frame vectors.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from semblon.compare import CompareError, compare_space
from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, color_histogram
from semblon.region_encoder import (
    COLOUR_SCORE_FLOOR,
    LABEL_COLOUR,
    LABEL_SIMILAR,
    LABEL_TEXT,
    LABEL_UNKNOWN,
    MODALITY_REGION,
    PROVIDER,
    REGION_SCORE_FLOOR,
    RegionPackError,
    active_pack,
    embed_bgr,
    probe_region_pack,
)
from semblon.user_region import RegionError, persist_user_region


def _open_ro(store: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def crop_bgr(image_path: Path, x: int, y: int, w: int, h: int):
    import cv2

    from semblon.temporal import VIDEO_EXT, _decode_still, read_bgr

    path = Path(image_path)
    if path.suffix.lower() in VIDEO_EXT:
        image = read_bgr(path, frame_id=0)
    else:
        image = _decode_still(path)
        if image is None:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RegionError(f"could not read {image_path}")
    image = _apply_display_orientation(image_path, image)
    height, width = image.shape[:2]
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(width, int(x + w))
    y2 = min(height, int(y + h))
    if x2 <= x1 or y2 <= y1:
        raise RegionError("region has no pixels")
    return image[y1:y2, x1:x2].copy()


def _apply_display_orientation(image_path: Path, image):
    """Match QImageReader auto-transform so a drawn box is the pixels the user saw."""
    try:
        from PIL import Image, ImageOps
        import numpy as np
    except Exception:
        return image
    try:
        with Image.open(image_path) as raw:
            oriented = ImageOps.exif_transpose(raw)
            if oriented.size == raw.size and oriented.tobytes() == raw.tobytes():
                return image
            rgb = np.asarray(oriented.convert("RGB"))
    except Exception:
        return image
    return rgb[:, :, ::-1].copy()


def appearance_vector(crop) -> bytes:
    return color_histogram(crop)


def _dedupe_scored(scored: list[dict], *, limit: int, min_score: float | None) -> list[dict]:
    """Best score per media. Drop weak neighbours. Fewer honest hits beat a full strip."""
    best: dict[str, dict] = {}
    order: list[str] = []
    for row in sorted(scored, key=lambda item: -float(item["score"])):
        if min_score is not None and float(row["score"]) < float(min_score):
            continue
        media_id = str(row.get("media_id") or row.get("item_id") or "")
        if not media_id or media_id in best:
            continue
        best[media_id] = row
        order.append(media_id)
        if len(order) >= limit:
            break
    return [best[key] for key in order]


def search_vector(
    store: Path,
    *,
    blob: bytes,
    modality: str,
    pack_id: str,
    dim: int,
    limit: int = 10,
    exclude_item_id: str | None = None,
    exclude_media_id: str | None = None,
    min_score: float | None = None,
    cancelled=None,
) -> dict:
    """Nearest existing embeddings in one space. Library scan; .npz not required."""
    if modality == "face":
        raise RegionError("face identity must use identify, not region search")
    path = Path(store)
    if not path.is_file():
        return {
            "kind": "region_similar",
            "status": "UNAVAILABLE",
            "reason": "Store not found. Nothing was searched.",
            "error_id": "region.NO_STORE",
            "count": 0,
            "items": [],
            "modality": modality,
            "pack_id": pack_id,
            "indexed": False,
            "note": "Similar looking is not the same as a named person.",
        }
    conn = _open_ro(path)
    try:
        rows = conn.execute(
            """SELECT e.item_id, e.embedding, e.embedding_dim, e.pack_id, e.modality,
                      i.kind, i.provider, o.media_id
               FROM embeddings e
               JOIN observation_items i ON i.item_id = e.item_id
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE e.modality = ? AND e.pack_id = ?""",
            (modality, pack_id),
        ).fetchall()
    finally:
        conn.close()
    scored = []
    for row in rows:
        if cancelled is not None and cancelled():
            break
        if exclude_item_id and row["item_id"] == exclude_item_id:
            continue
        if exclude_media_id and str(row["media_id"] or "") == str(exclude_media_id):
            continue
        try:
            score = compare_space(
                modality,
                pack_id,
                dim,
                blob,
                row["modality"],
                row["pack_id"],
                int(row["embedding_dim"]),
                row["embedding"],
            )
        except CompareError:
            continue
        scored.append(
            {
                "item_id": row["item_id"],
                "media_id": row["media_id"],
                "kind": row["kind"],
                "provider": row["provider"],
                "score": score,
                "why": "same modality+pack; query crop; source excluded; not a person",
            }
        )
    items = _dedupe_scored(scored, limit=limit, min_score=min_score)
    if not rows:
        return {
            "kind": "region_similar",
            "status": "UNAVAILABLE",
            "reason": "No embeddings in this space yet. Ingest with color first.",
            "error_id": "region.NO_LIBRARY_SPACE",
            "count": 0,
            "items": [],
            "modality": modality,
            "pack_id": pack_id,
            "indexed": False,
            "note": "Similar looking is not the same as a named person.",
        }
    if not items:
        return {
            "kind": "region_similar",
            "status": "NO_RESULT",
            "reason": "Searched your library and nothing matched in this space.",
            "error_id": None,
            "count": 0,
            "items": [],
            "modality": modality,
            "pack_id": pack_id,
            "indexed": False,
            "note": "Similar looking is not the same as a named person.",
        }
    return {
        "kind": "region_similar",
        "status": "SUCCESS",
        "reason": "Searched your library directly (query-time crop; no new index row).",
        "error_id": None,
        "count": len(items),
        "items": items,
        "modality": modality,
        "pack_id": pack_id,
        "indexed": False,
        "note": "Similar looking is not the same as a named person.",
    }


def _selection_box(x: int, y: int, w: int, h: int) -> tuple[float, float, float, float]:
    return (float(x), float(y), float(x + w), float(y + h))


def _boxes_overlap(sel: tuple[float, float, float, float], box: tuple[float, float, float, float]) -> bool:
    x1 = max(sel[0], box[0])
    y1 = max(sel[1], box[1])
    x2 = min(sel[2], box[2])
    y2 = min(sel[3], box[3])
    if x2 <= x1 or y2 <= y1:
        return False
    sel_cx = (sel[0] + sel[2]) / 2
    sel_cy = (sel[1] + sel[3]) / 2
    box_cx = (box[0] + box[2]) / 2
    box_cy = (box[1] + box[3]) / 2
    center_in_sel = sel[0] <= box_cx <= sel[2] and sel[1] <= box_cy <= sel[3]
    center_in_box = box[0] <= sel_cx <= box[2] and box[1] <= sel_cy <= box[3]
    return center_in_sel or center_in_box


def overlapping_text(store: Path, media_id: str, x: int, y: int, w: int, h: int) -> str:
    """OCR text whose stored box overlaps the selection. Empty when none do."""
    path = Path(store)
    if not path.is_file() or not media_id:
        return ""
    conn = _open_ro(path)
    try:
        rows = conn.execute(
            """SELECT i.payload_json, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE o.media_id=? AND i.kind='text'""",
            (media_id,),
        ).fetchall()
    finally:
        conn.close()
    sel = _selection_box(x, y, w, h)
    chunks: list[str] = []
    for row in rows:
        if row["bbox_x1"] is None:
            continue
        box = (
            float(row["bbox_x1"]),
            float(row["bbox_y1"]),
            float(row["bbox_x2"]),
            float(row["bbox_y2"]),
        )
        if not _boxes_overlap(sel, box):
            continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            continue
        text = str((payload or {}).get("text") or "").strip()
        if text:
            chunks.append(text)
    return " ".join(chunks).strip()


def _ocr_crop_text(crop) -> str:
    """Confident words in the crop. Low-confidence noise does not steal the visual search."""
    try:
        import cv2
        import pytesseract
        from pytesseract import Output
    except Exception:
        return ""
    if shutil_which_tesseract() is None:
        return ""
    arr = np.asarray(crop)
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY) if arr.ndim == 3 else arr
    try:
        data = pytesseract.image_to_data(gray, output_type=Output.DICT)
    except Exception:
        return ""
    words: list[str] = []
    texts = data.get("text") or []
    confs = data.get("conf") or []
    for raw, conf in zip(texts, confs):
        token = str(raw or "").strip()
        try:
            score = float(conf)
        except (TypeError, ValueError):
            continue
        if score < 70 or len(token) < 4:
            continue
        if not any(ch.isalnum() for ch in token):
            continue
        words.append(token)
    return " ".join(words).strip()


def shutil_which_tesseract() -> str | None:
    import shutil

    return shutil.which("tesseract")


def _text_query_token(text: str) -> str:
    tokens = [part for part in text.replace("\n", " ").split() if any(ch.isalnum() for ch in part)]
    tokens.sort(key=len, reverse=True)
    for token in tokens:
        cleaned = "".join(ch for ch in token if ch.isalnum())
        if len(cleaned) >= 4:
            return cleaned
    return ""


def _as_text_result(rec: dict, *, token: str) -> dict:
    items = []
    for item in rec.get("items") or []:
        media_id = str(item.get("media_id") or "")
        if not media_id:
            continue
        items.append(
            {
                "item_id": item.get("item_id"),
                "media_id": media_id,
                "kind": "text",
                "provider": item.get("provider") or "tesseract",
                "score": float(item.get("score") or 1.0),
                "why": "OCR text overlapped the selection; not a person",
            }
        )
    out = {
        "kind": "region_similar",
        "status": rec.get("status") or "NO_RESULT",
        "reason": f"Text in the selection: {token}.",
        "error_id": rec.get("error_id"),
        "count": len(items),
        "items": items,
        "modality": "text",
        "pack_id": None,
        "indexed": False,
        "wrote_embedding": False,
        "similarity_basis": LABEL_TEXT,
        "engine": "ocr",
        "note": "Text in the selection is not a person and not a colour match.",
    }
    if out["status"] == "SUCCESS" and not items:
        out["status"] = "NO_RESULT"
    return out


def _colour_result(store: Path, crop, *, limit: int, exclude_media_id: str | None, cancelled, reason: str) -> dict:
    blob = appearance_vector(crop)
    rec = search_vector(
        store,
        blob=blob,
        modality="appearance",
        pack_id=APPEARANCE_PACK,
        dim=APPEARANCE_DIM,
        limit=limit,
        exclude_media_id=exclude_media_id,
        min_score=COLOUR_SCORE_FLOOR,
        cancelled=cancelled,
    )
    rec["wrote_embedding"] = False
    rec["similarity_basis"] = LABEL_COLOUR
    rec["engine"] = "color-hist"
    rec["fallback"] = "colour"
    rec["reason"] = reason
    rec["note"] = "Colour only. This is not a region embedding and not a named person."
    return rec


def find_similar_region(
    store: Path,
    *,
    image_path: Path,
    x: int,
    y: int,
    w: int,
    h: int,
    limit: int = 10,
    media_id: str | None = None,
    selection_kind: str | None = None,
    cancelled=None,
) -> dict:
    crop = crop_bgr(Path(image_path), x, y, w, h)
    pixels = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    stored_text = overlapping_text(store, media_id or "", x, y, w, h) if media_id else ""
    text = stored_text
    if not text and selection_kind == "text":
        # Pointing at text with no stored box still reads the crop. Other selections stay visual.
        text = _ocr_crop_text(crop)
    token = _text_query_token(text)
    if token and selection_kind != "face":
        from semblon.search import search_text

        text_rec = search_text(store, token, limit=limit)
        items = [
            item
            for item in (text_rec.get("items") or [])
            if str(item.get("media_id") or "") != str(media_id or "")
        ]
        text_rec = {**text_rec, "items": items, "count": len(items)}
        if items:
            rec = _as_text_result(text_rec, token=token)
            rec["query_pixels"] = pixels
            return rec
        # A stored text box with no other hit stays a text result. A crop-only
        # guess with no hit falls through to the visual index.
        if stored_text and text_rec.get("status") in {"NO_RESULT", "SUCCESS", "UNAVAILABLE"}:
            rec = _as_text_result(text_rec, token=token)
            rec["status"] = "NO_RESULT"
            rec["query_pixels"] = pixels
            return rec

    ready, missing = probe_region_pack()
    pack = active_pack() if ready else None
    if pack is not None:
        pack_id, dim = pack
        encode_error = ""
        try:
            blob = embed_bgr(crop)
        except RegionPackError as exc:
            blob = None
            encode_error = str(exc)
        if blob is None:
            colour = _colour_result(
                store,
                crop,
                limit=limit,
                exclude_media_id=media_id,
                cancelled=cancelled,
                reason=(
                    encode_error
                    or "The region encoder did not finish. Showing colour only."
                ),
            )
            colour["query_pixels"] = pixels
            return colour
        if blob is not None:
            rec = search_vector(
                store,
                blob=blob,
                modality=MODALITY_REGION,
                pack_id=pack_id,
                dim=dim,
                limit=limit,
                exclude_media_id=media_id,
                min_score=REGION_SCORE_FLOOR,
                cancelled=cancelled,
            )
            if rec.get("status") != "UNAVAILABLE":
                rec["query_pixels"] = pixels
                rec["wrote_embedding"] = False
                rec["similarity_basis"] = (
                    LABEL_UNKNOWN if selection_kind == "unknown" else LABEL_SIMILAR
                )
                rec["engine"] = PROVIDER
                rec["fallback"] = None
                rec["reason"] = (
                    "Visually similar region. Not a claim that it is the same physical object."
                )
                rec["note"] = "Region embedding match. Not a name and not colour."
                return rec
            colour = _colour_result(
                store,
                crop,
                limit=limit,
                exclude_media_id=media_id,
                cancelled=cancelled,
                reason=(
                    "The region encoder is installed, but these photos have no matching "
                    "region index yet. Showing colour only. Add the folder again to index regions."
                ),
            )
            colour["query_pixels"] = pixels
            return colour
    colour = _colour_result(
        store,
        crop,
        limit=limit,
        exclude_media_id=media_id,
        cancelled=cancelled,
        reason=missing
        or "Region encoder is not installed. Showing colour only.",
    )
    colour["query_pixels"] = pixels
    return colour


def remember_and_find(
    store: Path,
    *,
    media_id: str,
    image_path: Path | None,
    x: int,
    y: int,
    w: int,
    h: int,
    run_id: str | None = None,
    limit: int = 10,
    selection_kind: str | None = None,
    cancelled=None,
) -> dict:
    """Persist the box, then search. Does not persist a vector or a sibling item."""
    saved = persist_user_region(
        store,
        media_id=media_id,
        x=x,
        y=y,
        w=w,
        h=h,
        run_id=run_id,
        report=None,
    )
    path = Path(image_path) if image_path is not None else None
    if path is None or not path.is_file():
        conn = sqlite3.connect(str(store))
        row = conn.execute("SELECT path FROM media WHERE media_id=?", (media_id,)).fetchone()
        conn.close()
        path = Path(row[0]) if row and row[0] else None
    similar = {
        "kind": "region_similar",
        "status": "UNAVAILABLE",
        "reason": "Could not read the photo to search from the box.",
        "error_id": "region.NO_IMAGE",
        "count": 0,
        "items": [],
        "wrote_embedding": False,
    }
    if path is not None and path.is_file():
        similar = find_similar_region(
            store,
            image_path=path,
            x=x,
            y=y,
            w=w,
            h=h,
            limit=limit,
            media_id=media_id,
            selection_kind=selection_kind,
            cancelled=cancelled,
        )
    return {
        "region": saved,
        "similar": similar,
        "persons": 0,
        "entity": False,
        "wrote_embedding": False,
    }
