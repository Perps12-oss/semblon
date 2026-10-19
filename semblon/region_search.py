"""Find similar from a persisted user box.

Primary space: dense DINOv2 content patches of each indexed frame, scored
against the query crop by late interaction. A pointed region can match a
place that was never one of the proposal boxes. Proposal CLS crops remain
the fallback when that patch map is absent. Colour histograms are the
labelled fallback when the encoder itself is absent.

Does not write an embedding row for the query. Does not create a sibling item.
Face identity is forbidden. A region query never scans whole-frame scene vectors
and never writes faces.person_id.
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
    KNOWN_SHA256,
    LABEL_COLOUR,
    LABEL_SIMILAR,
    LABEL_TEXT,
    LABEL_UNKNOWN,
    MODALITY_PATCH,
    MODALITY_REGION,
    PATCH_COVERAGE_FLOOR,
    PATCH_SCORE_FLOOR,
    PATCH_TOKEN_FLOOR,
    PROVIDER,
    REGION_SCORE_FLOOR,
    WEIGHT_NAME,
    RegionPackError,
    active_pack,
    content_patch_records,
    embed_bgr,
    pack_id_patches,
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


def describe_selection(
    store: Path,
    media_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    crop: np.ndarray | None = None,
) -> str:
    """What this selection is, in plain language. Never a person name.

    Order: a face box that contains the centre, then a detector class
    (contour boxes are geometry, not a class), then overlapping OCR text,
    then one local noun that beats "no specific name". Otherwise unlabelled.
    The noun does not choose which archive photos match.
    """
    path = Path(store)
    if not path.is_file() or not media_id:
        return "Unlabelled region."
    cx = float(x) + float(w) / 2.0
    cy = float(y) + float(h) / 2.0
    conn = _open_ro(path)
    try:
        faces = conn.execute(
            """SELECT f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2
               FROM faces f
               JOIN observations o ON o.observation_id = f.observation_id
               WHERE o.media_id=?""",
            (media_id,),
        ).fetchall()
        objects = conn.execute(
            """SELECT i.payload_json, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2, i.provider
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE o.media_id=? AND i.kind='object'""",
            (media_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in faces:
        if _point_in_box(cx, cy, row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]):
            return "Face in the selection. Not a named person."
    for row in objects:
        if row["bbox_x1"] is None:
            continue
        if not _point_in_box(cx, cy, row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]):
            continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("source") or "") == "contour":
            continue
        label = str(payload.get("label") or payload.get("class") or "").strip()
        if not label or label.lower() in {"region", "user_region"}:
            continue
        return f"Object: {label}."
    text = overlapping_text(store, media_id, x, y, w, h)
    token = _text_query_token(text)
    if token:
        return f"Text: {token}."
    if crop is not None:
        from semblon.visual.naming_local import name_crop_bgr

        try:
            named = name_crop_bgr(crop)
        except Exception:  # noqa: BLE001 — naming must not replace a visual search
            named = None
        if named:
            return named
    return "Unlabelled region."


def _point_in_box(px: float, py: float, x1, y1, x2, y2) -> bool:
    if x1 is None or y1 is None or x2 is None or y2 is None:
        return False
    return float(x1) <= px <= float(x2) and float(y1) <= py <= float(y2)


def _union_box(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _norm_box(box: tuple[float, float, float, float], width: int, height: int) -> list[float]:
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    x1, y1, x2, y2 = box
    nx = max(0.0, min(1.0, x1 / float(width)))
    ny = max(0.0, min(1.0, y1 / float(height)))
    nw = max(0.0, min(1.0 - nx, (x2 - x1) / float(width)))
    nh = max(0.0, min(1.0 - ny, (y2 - y1) / float(height)))
    return [nx, ny, nw, nh]


def search_patches(
    store: Path,
    crop,
    *,
    limit: int = 10,
    exclude_media_id: str | None = None,
    cancelled=None,
    keep_weak: bool = False,
) -> dict:
    """Late interaction of the query crop against stored content patches.

    Score is the mean, over query patches, of the best cosine in the other
    photo. The match box is the union of those winning patches. Proposal
    rows are not read.
    """
    ready, missing = probe_region_pack()
    empty = {
        "kind": "region_similar",
        "status": "UNAVAILABLE",
        "reason": missing or "Region encoder is not installed.",
        "error_id": "region.NO_PACK",
        "count": 0,
        "items": [],
        "modality": MODALITY_PATCH,
        "pack_id": None,
        "indexed": False,
        "wrote_embedding": False,
        "engine": "dinov2-patch",
        "note": "A patch match is not a named person.",
    }
    if not ready:
        return empty
    pack = pack_id_patches(KNOWN_SHA256[WEIGHT_NAME])
    try:
        _cls, records = content_patch_records(crop)
    except RegionPackError as exc:
        empty["reason"] = str(exc)
        empty["error_id"] = "region.ENCODE"
        return empty
    query = np.stack([np.frombuffer(record["blob"], dtype=np.float32).copy() for record in records])
    if query.size == 0:
        empty["reason"] = "The selection produced no patches."
        return empty
    path = Path(store)
    if not path.is_file():
        empty["reason"] = "Store not found. Nothing was searched."
        empty["error_id"] = "region.NO_STORE"
        return empty
    conn = _open_ro(path)
    try:
        rows = conn.execute(
            """SELECT e.embedding, e.embedding_dim, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2,
                      o.media_id, m.width, m.height
               FROM embeddings e
               JOIN observation_items i ON i.item_id = e.item_id
               JOIN observations o ON o.observation_id = i.observation_id
               JOIN media m ON m.media_id = o.media_id
               WHERE e.modality = ? AND e.pack_id = ?""",
            (MODALITY_PATCH, pack),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        empty["reason"] = (
            "These photos have no patch map yet. Add the folder again to index regions."
        )
        empty["error_id"] = "region.NO_PATCH_INDEX"
        return empty
    grouped: dict[str, dict] = {}
    for row in rows:
        media_id = str(row["media_id"] or "")
        if not media_id or media_id == str(exclude_media_id or ""):
            continue
        if row["bbox_x1"] is None or int(row["embedding_dim"] or 0) != query.shape[1]:
            continue
        bucket = grouped.setdefault(
            media_id,
            {"width": int(row["width"] or 0), "height": int(row["height"] or 0), "vecs": [], "boxes": []},
        )
        bucket["vecs"].append(np.frombuffer(row["embedding"], dtype=np.float32).copy())
        bucket["boxes"].append(
            (float(row["bbox_x1"]), float(row["bbox_y1"]), float(row["bbox_x2"]), float(row["bbox_y2"]))
        )
    items: list[dict] = []
    for media_id, bucket in grouped.items():
        if cancelled is not None and cancelled():
            break
        matrix = np.stack(bucket["vecs"])
        sims = query @ matrix.T
        maxes = sims.max(axis=1)
        score = float(maxes.mean())
        coverage = float((maxes >= PATCH_TOKEN_FLOOR).mean())
        above = score >= PATCH_SCORE_FLOOR and coverage >= PATCH_COVERAGE_FLOOR
        if not above and not keep_weak:
            continue
        winners: list[tuple[float, tuple[float, float, float, float]]] = []
        chosen = sims.argmax(axis=1)
        for index, column in enumerate(chosen):
            weight = float(sims[index, column])
            if weight >= PATCH_TOKEN_FLOOR:
                winners.append((weight, bucket["boxes"][int(column)]))
        if not winners:
            if not keep_weak:
                continue
            items.append(
                {
                    "item_id": None,
                    "media_id": media_id,
                    "kind": "clip",
                    "provider": PROVIDER,
                    "score": score,
                    "match_box": [0.0, 0.0, 0.0, 0.0],
                    "match_norm": [0.0, 0.0, 0.0, 0.0],
                    "coverage": coverage,
                    "above_floor": False,
                    "why": "patch max-sim below the token line; not a person",
                }
            )
            continue
        winners.sort(key=lambda item: -item[0])
        # A tight box. If the winners cover most of the photo, keep the strongest quarter.
        span = _union_box([box for _weight, box in winners])
        area = max(0.0, span[2] - span[0]) * max(0.0, span[3] - span[1])
        frame = float(bucket["width"] * bucket["height"] or 1)
        if area > 0.55 * frame and len(winners) > 4:
            keep = max(4, len(winners) // 4)
            span = _union_box([box for _weight, box in winners[:keep]])
        x1, y1, x2, y2 = span
        items.append(
            {
                "item_id": None,
                "media_id": media_id,
                "kind": "clip",
                "provider": PROVIDER,
                "score": score,
                "match_box": [x1, y1, max(1.0, x2 - x1), max(1.0, y2 - y1)],
                "match_norm": _norm_box(span, bucket["width"], bucket["height"]),
                "coverage": coverage,
                "above_floor": above,
                "why": "patch max-sim; source excluded; not a person",
            }
        )
    items.sort(key=lambda item: -float(item["score"]))
    items = items[:limit]
    if not items:
        return {
            "kind": "region_similar",
            "status": "NO_RESULT",
            "reason": "Searched the patch maps and nothing matched this selection.",
            "error_id": None,
            "count": 0,
            "items": [],
            "modality": MODALITY_PATCH,
            "pack_id": pack,
            "indexed": True,
            "wrote_embedding": False,
            "similarity_basis": LABEL_SIMILAR,
            "engine": "dinov2-patch",
            "fallback": None,
            "note": "A patch match is not a named person.",
        }
    return {
        "kind": "region_similar",
        "status": "SUCCESS",
        "reason": "Matching region in your archive. The box marks where it sits.",
        "error_id": None,
        "count": len(items),
        "items": items,
        "modality": MODALITY_PATCH,
        "pack_id": pack,
        "indexed": True,
        "wrote_embedding": False,
        "similarity_basis": LABEL_SIMILAR,
        "engine": "dinov2-patch",
        "fallback": None,
        "note": "Patch-map match. Not a name and not colour.",
    }


def _attach_understanding(rec: dict, understanding: str, *, selection_kind: str | None) -> dict:
    rec["understanding"] = understanding
    if selection_kind == "unknown" and rec.get("engine") == "dinov2-patch":
        rec["similarity_basis"] = LABEL_UNKNOWN
    return rec


def _find_similar_from_crop(
    store: Path,
    *,
    crop,
    limit: int,
    media_id: str | None,
    selection_kind: str | None,
    cancelled,
    understanding: str,
    stored_text: str,
    query_pixels: dict[str, int] | None,
) -> dict:
    text_only = selection_kind == "text"
    text_priority = selection_kind in {"text", "text_priority"}
    token = _text_query_token(stored_text)
    # A text observation is its own door. Any other selection keeps the visual search
    # and only reports the text as understanding.
    if token and text_priority:
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
            if query_pixels is not None:
                rec["query_pixels"] = query_pixels
            return _attach_understanding(rec, f"Text: {token}.", selection_kind=selection_kind)
        if stored_text and text_rec.get("status") in {"NO_RESULT", "SUCCESS", "UNAVAILABLE"}:
            if not text_only:
                understanding = f"Text: {token}. No text match; showing visual similarity."
            else:
                rec = _as_text_result(text_rec, token=token)
                rec["status"] = "NO_RESULT"
                if query_pixels is not None:
                    rec["query_pixels"] = query_pixels
                return _attach_understanding(rec, f"Text: {token}.", selection_kind=selection_kind)
        if stored_text and text_rec.get("status") == "ERROR" and not text_only:
            understanding = f"Text: {token}. Text lookup failed; showing visual similarity."
        elif stored_text and text_rec.get("status") == "ERROR":
            rec = _as_text_result(text_rec, token=token)
            rec["status"] = "ERROR"
            if query_pixels is not None:
                rec["query_pixels"] = query_pixels
            return _attach_understanding(rec, f"Text: {token}.", selection_kind=selection_kind)

    ready, missing = probe_region_pack()
    if ready:
        dense = search_patches(
            store,
            crop,
            limit=limit,
            exclude_media_id=media_id,
            cancelled=cancelled,
        )
        if query_pixels is not None:
            dense["query_pixels"] = query_pixels
        if dense.get("status") in {"SUCCESS", "NO_RESULT"}:
            return _attach_understanding(dense, understanding, selection_kind=selection_kind)
        if dense.get("error_id") == "region.ENCODE":
            colour = _colour_result(
                store,
                crop,
                limit=limit,
                exclude_media_id=media_id,
                cancelled=cancelled,
                reason=str(dense.get("reason") or "The region encoder did not finish. Showing colour only."),
            )
            if query_pixels is not None:
                colour["query_pixels"] = query_pixels
            return _attach_understanding(colour, understanding, selection_kind=selection_kind)
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
            if query_pixels is not None:
                colour["query_pixels"] = query_pixels
            return _attach_understanding(colour, understanding, selection_kind=selection_kind)
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
                if query_pixels is not None:
                    rec["query_pixels"] = query_pixels
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
                return _attach_understanding(rec, understanding, selection_kind=selection_kind)
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
            if query_pixels is not None:
                colour["query_pixels"] = query_pixels
            return _attach_understanding(colour, understanding, selection_kind=selection_kind)
    colour = _colour_result(
        store,
        crop,
        limit=limit,
        exclude_media_id=media_id,
        cancelled=cancelled,
        reason=missing
        or "Region encoder is not installed. Showing colour only.",
    )
    if query_pixels is not None:
        colour["query_pixels"] = query_pixels
    return _attach_understanding(colour, understanding, selection_kind=selection_kind)


def _describe_crop(crop) -> str:
    from semblon.visual.naming_local import name_crop_bgr

    try:
        named = name_crop_bgr(crop)
    except Exception:  # noqa: BLE001 — naming must not replace a visual search
        named = None
    return str(named or "Unlabelled region.")


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
    understanding = describe_selection(store, media_id or "", x, y, w, h, crop=crop)
    stored_text = overlapping_text(store, media_id or "", x, y, w, h) if media_id else ""
    if not stored_text and selection_kind in {"text", "text_priority"}:
        # Pointing at text with no stored box still reads the crop. Other selections stay visual.
        stored_text = _ocr_crop_text(crop)
    return _find_similar_from_crop(
        store,
        crop=crop,
        limit=limit,
        media_id=media_id,
        selection_kind=selection_kind,
        cancelled=cancelled,
        understanding=understanding,
        stored_text=stored_text,
        query_pixels=pixels,
    )


def find_similar_crop(
    store: Path,
    *,
    crop,
    limit: int = 10,
    selection_kind: str | None = None,
    cancelled=None,
) -> dict:
    """Search the local archive from an arbitrary query crop (for example screen selection)."""
    text = _ocr_crop_text(crop) if selection_kind in {"text", "text_priority"} else ""
    understanding = _describe_crop(crop)
    return _find_similar_from_crop(
        store,
        crop=crop,
        limit=limit,
        media_id=None,
        selection_kind=selection_kind,
        cancelled=cancelled,
        understanding=understanding,
        stored_text=text,
        query_pixels=None,
    )


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
