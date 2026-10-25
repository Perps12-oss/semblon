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
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from semblon.compare import CompareError, compare_space
from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, color_histogram
from semblon.region_encoder import (
    KNOWN_SHA256,
    LABEL_COLOUR,
    LABEL_SIMILAR,
    LABEL_TEXT,
    LABEL_UNKNOWN,
    MODALITY_PATCH,
    MODALITY_REGION,
    PROVIDER,
    WEIGHT_NAME,
    OUTPUT_DIM,
    RegionPackError,
    active_pack,
    content_patch_records,
    embed_bgr,
    pack_id_patches,
    probe_region_pack,
)
from semblon.similarity_profile import SimilarityProfile, resolve_search_quality
from semblon.user_region import RegionError, persist_user_region
from semblon.store import connect_readonly


def _open_ro(store: Path) -> sqlite3.Connection:
    conn = connect_readonly(Path(store).resolve())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


_FRAME_CACHE: OrderedDict[tuple, np.ndarray] = OrderedDict()
_FRAME_LOCK = threading.Lock()
_FRAME_CAP_BYTES = 48 * 1024 * 1024
_GALLERY_LOCK = threading.Lock()
_GALLERY: dict[tuple, tuple[list[dict], bool]] = {}
_GALLERY_LOADS = 0
_GALLERY_CAP_BYTES = 96 * 1024 * 1024
_PATCH_CHUNK = 8192
SHORTLIST_SIZE = 64
DETAIL_PROMOTE_MAX = 8
DETAIL_BUDGET_S = 12.0
_EXIF_ORIENTATION = 0x0112


def clear_frame_cache() -> None:
    with _FRAME_LOCK:
        _FRAME_CACHE.clear()


def clear_patch_gallery_cache() -> None:
    global _GALLERY_LOADS
    with _GALLERY_LOCK:
        _GALLERY.clear()
        _GALLERY_LOADS = 0


def patch_gallery_loads() -> int:
    return _GALLERY_LOADS


def crop_bgr(image_path: Path, x: int, y: int, w: int, h: int):
    image = _oriented_frame(Path(image_path))
    height, width = image.shape[:2]
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(width, int(x + w))
    y2 = min(height, int(y + h))
    if x2 <= x1 or y2 <= y1:
        raise RegionError("region has no pixels")
    return image[y1:y2, x1:x2].copy()


def _oriented_frame(image_path: Path):
    """Full display-oriented frame. Repeated searches of one photo reuse it."""
    import cv2

    from semblon.temporal import VIDEO_EXT, _decode_still, read_bgr

    path = Path(image_path)
    try:
        stat = path.stat()
        key = (str(path.resolve()), int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        key = None
    if key is not None:
        with _FRAME_LOCK:
            hit = _FRAME_CACHE.get(key)
            if hit is not None:
                _FRAME_CACHE.move_to_end(key)
                return hit
    if path.suffix.lower() in VIDEO_EXT:
        image = read_bgr(path, frame_id=0)
    else:
        image = _decode_still(path)
        if image is None:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RegionError(f"could not read {image_path}")
    image = _apply_display_orientation(path, image)
    if key is not None and int(image.nbytes) <= _FRAME_CAP_BYTES:
        with _FRAME_LOCK:
            _FRAME_CACHE[key] = image
            _FRAME_CACHE.move_to_end(key)
            while _FRAME_CACHE and sum(int(frame.nbytes) for frame in _FRAME_CACHE.values()) > _FRAME_CAP_BYTES:
                _FRAME_CACHE.popitem(last=False)
    return image


def _apply_display_orientation(image_path: Path, image):
    """Match QImageReader auto-transform so a drawn box is the pixels the user saw.

    A file with no orientation tag is already the display image. Comparing
    every pixel here decoded the photograph a second time on each search.
    """
    suffix = Path(image_path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        return image
    try:
        from PIL import Image, ImageOps
    except Exception:
        return image
    try:
        with Image.open(image_path) as raw:
            exif = raw.getexif()
            orientation = exif.get(_EXIF_ORIENTATION) if exif is not None else None
            if orientation in (None, 1):
                return image
            oriented = ImageOps.exif_transpose(raw)
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


def _as_text_result(rec: dict, *, token: str, quality: SimilarityProfile) -> dict:
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
                "score": 1.0 if item.get("score") is None else float(item.get("score")),
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
        "search_profile": quality.key,
        "search_profile_label": quality.label,
    }
    if out["status"] == "SUCCESS" and not items:
        out["status"] = "NO_RESULT"
    return out


def _colour_result(
    store: Path,
    crop,
    *,
    limit: int,
    exclude_media_id: str | None,
    cancelled,
    reason: str,
    min_score: float,
    quality: SimilarityProfile,
) -> dict:
    blob = appearance_vector(crop)
    rec = search_vector(
        store,
        blob=blob,
        modality="appearance",
        pack_id=APPEARANCE_PACK,
        dim=APPEARANCE_DIM,
        limit=limit,
        exclude_media_id=exclude_media_id,
        min_score=min_score,
        cancelled=cancelled,
    )
    rec["wrote_embedding"] = False
    rec["similarity_basis"] = LABEL_COLOUR
    rec["engine"] = "color-hist"
    rec["fallback"] = "colour"
    rec["reason"] = reason
    rec["note"] = "Colour only. This is not a region embedding and not a named person."
    rec["search_profile"] = quality.key
    rec["search_profile_label"] = quality.label
    return rec


def _unit_confidence(value) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0:
        return None
    if score > 1:
        return 1.0
    return score


def describe_selection(
    store: Path,
    media_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    crop: np.ndarray | None = None,
) -> str:
    """What this selection is, in plain language. Never a person name."""
    return str(describe_selection_detail(store, media_id, x, y, w, h, crop=crop)["understanding"])


def describe_selection_detail(
    store: Path,
    media_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    crop: np.ndarray | None = None,
) -> dict:
    """Selection label plus the model's own score, when it has one.

    Order: a face box that contains the centre, then a detector class
    (contour boxes are geometry, not a class), then overlapping OCR text,
    then one local noun that beats "no specific name". Otherwise unlabelled.
    The noun does not choose which archive photos match.
    """

    def pack(text: str, confidence=None) -> dict:
        return {"understanding": text, "confidence": _unit_confidence(confidence)}

    path = Path(store)
    if not path.is_file() or not media_id:
        return pack("Unlabelled region.")
    cx = float(x) + float(w) / 2.0
    cy = float(y) + float(h) / 2.0
    conn = _open_ro(path)
    try:
        faces = conn.execute(
            """SELECT f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2, f.det_score
               FROM faces f
               JOIN observations o ON o.observation_id = f.observation_id
               WHERE o.media_id=?""",
            (media_id,),
        ).fetchall()
        objects = conn.execute(
            """SELECT i.payload_json, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2, i.provider, i.score
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE o.media_id=? AND i.kind='object'""",
            (media_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in faces:
        if _point_in_box(cx, cy, row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]):
            return pack("Face in the selection. Not a named person.", row["det_score"])
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
        return pack(f"Object: {label}.", row["score"])
    text = overlapping_text(store, media_id, x, y, w, h)
    token = _text_query_token(text)
    if token:
        return pack(f"Text: {token}.")
    if crop is not None:
        from semblon.visual.naming_local import name_crop_detail

        try:
            named, score = name_crop_detail(crop)
        except Exception:  # noqa: BLE001 — naming must not replace a visual search
            named, score = None, None
        if named:
            return pack(named, score)
    return pack("Unlabelled region.")


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


def load_patch_groups(store: Path, conn, pack: str, dim: int) -> tuple[list[dict], bool]:
    """Patch matrices for one pack. A second search reuses them until the index changes."""
    global _GALLERY_LOADS
    stamp = conn.execute(
        "SELECT COUNT(*), COALESCE(MAX(rowid), 0) FROM embeddings WHERE modality=? AND pack_id=?",
        (MODALITY_PATCH, pack),
    ).fetchone()
    count = int(stamp[0] or 0)
    max_row = int(stamp[1] or 0)
    key = (str(Path(store).resolve()), str(pack), int(dim), count, max_row)
    with _GALLERY_LOCK:
        hit = _GALLERY.get(key)
        if hit is not None:
            return hit
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
    grouped: dict[str, dict] = {}
    order: list[str] = []
    saw_rows = bool(rows)
    for row in rows:
        media_id = str(row["media_id"] or "")
        if not media_id:
            continue
        if row["bbox_x1"] is None or int(row["embedding_dim"] or 0) != int(dim):
            continue
        bucket = grouped.get(media_id)
        if bucket is None:
            bucket = {
                "media_id": media_id,
                "width": int(row["width"] or 0),
                "height": int(row["height"] or 0),
                "vecs": [],
                "boxes": [],
            }
            grouped[media_id] = bucket
            order.append(media_id)
        bucket["vecs"].append(np.frombuffer(row["embedding"], dtype=np.float32).copy())
        bucket["boxes"].append(
            (float(row["bbox_x1"]), float(row["bbox_y1"]), float(row["bbox_x2"]), float(row["bbox_y2"]))
        )
    groups = []
    for media_id in order:
        bucket = grouped[media_id]
        groups.append(
            {
                "media_id": media_id,
                "width": bucket["width"],
                "height": bucket["height"],
                "matrix": np.ascontiguousarray(np.stack(bucket["vecs"]), dtype=np.float32),
                "boxes": bucket["boxes"],
            }
        )
    payload = (groups, saw_rows)
    nbytes = sum(int(group["matrix"].nbytes) for group in groups)
    with _GALLERY_LOCK:
        _GALLERY_LOADS += 1
        if nbytes <= _GALLERY_CAP_BYTES:
            _GALLERY.clear()
            _GALLERY[key] = payload
    return payload


def _score_one_block(
    block: np.ndarray,
    group: dict,
    *,
    token_floor: float,
    score_floor: float,
    coverage_floor: float,
    keep_weak: bool,
) -> dict | None:
    maxes = block.max(axis=1)
    score = float(maxes.mean())
    coverage = float((maxes >= float(token_floor)).mean())
    above = score >= float(score_floor) and coverage >= float(coverage_floor)
    if not above and not keep_weak:
        return None
    winners: list[tuple[float, tuple[float, float, float, float]]] = []
    chosen = block.argmax(axis=1)
    boxes = group["boxes"]
    for index, column in enumerate(chosen):
        weight = float(block[index, column])
        if weight >= float(token_floor):
            winners.append((weight, boxes[int(column)]))
    media_id = group["media_id"]
    if not winners:
        if not keep_weak:
            return None
        return {
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
    winners.sort(key=lambda item: -item[0])
    span = _union_box([box for _weight, box in winners])
    area = max(0.0, span[2] - span[0]) * max(0.0, span[3] - span[1])
    frame = float(int(group["width"]) * int(group["height"]) or 1)
    if area > 0.55 * frame and len(winners) > 4:
        keep = max(4, len(winners) // 4)
        span = _union_box([box for _weight, box in winners[:keep]])
    x1, y1, x2, y2 = span
    return {
        "item_id": None,
        "media_id": media_id,
        "kind": "clip",
        "provider": PROVIDER,
        "score": score,
        "match_box": [x1, y1, max(1.0, x2 - x1), max(1.0, y2 - y1)],
        "match_norm": _norm_box(span, int(group["width"]), int(group["height"])),
        "coverage": coverage,
        "above_floor": above,
        "why": "patch max-sim; source excluded; not a person",
    }


def score_patch_groups(
    query: np.ndarray,
    groups: list[dict],
    *,
    exclude_media_id: str | None = None,
    cancelled=None,
    keep_weak: bool = False,
    token_floor: float = 0.35,
    score_floor: float = 0.28,
    coverage_floor: float = 0.28,
    limit: int = 10,
) -> list[dict]:
    """Late interaction. One multiply covers many photos; the score is still max-sim."""
    skipped = str(exclude_media_id or "")
    items: list[dict] = []
    pending: list[dict] = []
    pending_patches = 0

    def flush() -> None:
        nonlocal pending, pending_patches
        if not pending:
            return
        stacked = np.concatenate([group["matrix"] for group in pending], axis=0)
        sims = query @ stacked.T
        start = 0
        for group in pending:
            count = int(group["matrix"].shape[0])
            item = _score_one_block(
                sims[:, start : start + count],
                group,
                token_floor=token_floor,
                score_floor=score_floor,
                coverage_floor=coverage_floor,
                keep_weak=keep_weak,
            )
            start += count
            if item is not None:
                items.append(item)
        pending = []
        pending_patches = 0

    for group in groups:
        if cancelled is not None and cancelled():
            break
        if str(group["media_id"]) == skipped:
            continue
        pending.append(group)
        pending_patches += int(group["matrix"].shape[0])
        if pending_patches >= _PATCH_CHUNK:
            flush()
    flush()
    items.sort(key=lambda item: -float(item["score"]))
    return items[: int(limit)]


def roi_query_tokens(groups: list[dict], media_id: str, box: tuple[int, int, int, int]) -> np.ndarray | None:
    """Tokens already stored for this photo whose centres sit in the box.

    The finest stored scale that covers the box is the query. A photo that was
    indexed does not need another encoder pass.
    """
    x, y, w, h = (int(box[0]), int(box[1]), int(box[2]), int(box[3]))
    if w <= 0 or h <= 0:
        return None
    x2 = x + w
    y2 = y + h
    group = None
    for item in groups:
        if str(item.get("media_id") or "") == str(media_id):
            group = item
            break
    if group is None:
        return None
    matrix = group["matrix"]
    hits: list[tuple[float, int]] = []
    for index, bbox in enumerate(group["boxes"]):
        cx = (float(bbox[0]) + float(bbox[2])) * 0.5
        cy = (float(bbox[1]) + float(bbox[3])) * 0.5
        if cx < x or cy < y or cx >= x2 or cy >= y2:
            continue
        area = max(1.0, (float(bbox[2]) - float(bbox[0])) * (float(bbox[3]) - float(bbox[1])))
        hits.append((area, index))
    if not hits:
        return None
    hits.sort(key=lambda item: item[0])
    smallest = hits[0][0]
    selected = [index for area, index in hits if area <= smallest * 1.5]
    if len(selected) < 4:
        selected = [index for _area, index in hits]
    rows = np.asarray(selected, dtype=np.int64)
    return np.ascontiguousarray(matrix[rows], dtype=np.float32)


def search_patches(
    store: Path,
    crop,
    *,
    limit: int = 10,
    exclude_media_id: str | None = None,
    cancelled=None,
    keep_weak: bool = False,
    token_stride: int = 1,
    token_floor: float = 0.35,
    score_floor: float = 0.28,
    coverage_floor: float = 0.28,
    query_box: tuple[int, int, int, int] | None = None,
    shortlist_out: list | None = None,
) -> dict:
    """Late interaction of the query crop against stored content patches.

    Score is the mean, over query patches, of the best cosine in the other
    photo. The match box is the union of those winning patches. Proposal
    rows are not read.
    """
    pack = pack_id_patches(KNOWN_SHA256[WEIGHT_NAME])
    empty = {
        "kind": "region_similar",
        "status": "UNAVAILABLE",
        "reason": "Region encoder is not installed.",
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
    path = Path(store)
    groups = None
    saw_rows = False
    query = None
    query_source = "crop-forward"
    if query_box is not None and exclude_media_id and path.is_file():
        conn = _open_ro(path)
        try:
            groups, saw_rows = load_patch_groups(path, conn, pack, OUTPUT_DIM)
        finally:
            conn.close()
        if saw_rows:
            stored = roi_query_tokens(groups, str(exclude_media_id), query_box)
            if stored is not None:
                query = stored
                query_source = "index"
            else:
                indexed = any(str(item.get("media_id") or "") == str(exclude_media_id) for item in groups)
                if indexed:
                    empty["reason"] = "The selection produced no patches."
                    empty["error_id"] = None
                    empty["status"] = "NO_RESULT"
                    empty["indexed"] = True
                    empty["pack_id"] = pack
                    empty["query_source"] = "index"
                    return empty
    if query is None:
        ready, missing = probe_region_pack()
        if not ready:
            empty["reason"] = missing or empty["reason"]
            return empty
        try:
            _cls, records = content_patch_records(crop, interactive=True, cancelled=cancelled)
        except RegionPackError as exc:
            if cancelled is not None and cancelled():
                empty["status"] = "CANCELLED"
                empty["reason"] = "Search cancelled."
                empty["error_id"] = "region.CANCELLED"
                return empty
            empty["reason"] = str(exc)
            empty["error_id"] = "region.ENCODE"
            return empty
        query = np.stack([np.frombuffer(record["blob"], dtype=np.float32).copy() for record in records])
    stride = max(1, int(token_stride))
    if stride > 1 and query.shape[0] > stride:
        query = query[::stride]
    if query.size == 0:
        empty["reason"] = "The selection produced no patches."
        empty["query_source"] = query_source
        return empty
    if groups is None:
        if not path.is_file():
            empty["reason"] = "Store not found. Nothing was searched."
            empty["error_id"] = "region.NO_STORE"
            return empty
        conn = _open_ro(path)
        try:
            groups, saw_rows = load_patch_groups(path, conn, pack, int(query.shape[1]))
        finally:
            conn.close()
    if not saw_rows:
        empty["reason"] = (
            "These photos have no patch map yet. Add the folder again to index regions."
        )
        empty["error_id"] = "region.NO_PATCH_INDEX"
        return empty
    if shortlist_out is not None:
        # A wider, unfiltered ranking decides which photos deserve fine detail first.
        wide = score_patch_groups(
            query,
            groups,
            exclude_media_id=exclude_media_id,
            cancelled=cancelled,
            keep_weak=True,
            token_floor=token_floor,
            score_floor=score_floor,
            coverage_floor=coverage_floor,
            limit=SHORTLIST_SIZE,
        )
        shortlist_out.extend(str(item["media_id"]) for item in wide if item.get("media_id"))
    items = score_patch_groups(
        query,
        groups,
        exclude_media_id=exclude_media_id,
        cancelled=cancelled,
        keep_weak=keep_weak,
        token_floor=token_floor,
        score_floor=score_floor,
        coverage_floor=coverage_floor,
        limit=limit,
    )
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
            "query_source": query_source,
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
        "query_source": query_source,
        "note": "Patch-map match. Not a name and not colour.",
    }


def _attach_understanding(rec: dict, understanding: str, *, selection_kind: str | None) -> dict:
    rec["understanding"] = understanding
    if selection_kind == "unknown" and rec.get("engine") == "dinov2-patch":
        rec["similarity_basis"] = LABEL_UNKNOWN
    return rec


def _attach_coverage(rec: dict, store: Path) -> None:
    """Say so when part of the library has not been prepared for search yet."""
    from semblon.scan_tiers import coverage_note, semantic_coverage

    try:
        conn = _open_ro(Path(store))
    except Exception:  # noqa: BLE001 — coverage is advice, never a reason to fail a search
        return
    try:
        coverage = semantic_coverage(conn)
    finally:
        conn.close()
    if coverage is None:
        return
    rec["coverage"] = coverage
    note = coverage_note(coverage)
    if note:
        rec["reason"] = f"{rec.get('reason') or ''} {note}".strip()


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
    search_quality: str = "balanced",
    shortlist_out: list | None = None,
) -> dict:
    quality = resolve_search_quality(search_quality)
    capped_limit = max(1, min(int(limit or 1), quality.max_results))
    text_only = selection_kind == "text"
    text_priority = selection_kind in {"text", "text_priority"}
    token = _text_query_token(stored_text)
    # A text observation is its own door. Any other selection keeps the visual search
    # and only reports the text as understanding.
    if token and text_priority:
        from semblon.search import search_text

        text_rec = search_text(store, token, limit=capped_limit)
        items = [
            item
            for item in (text_rec.get("items") or [])
            if str(item.get("media_id") or "") != str(media_id or "")
        ]
        text_rec = {**text_rec, "items": items, "count": len(items)}
        if items:
            rec = _as_text_result(text_rec, token=token, quality=quality)
            if query_pixels is not None:
                rec["query_pixels"] = query_pixels
            return _attach_understanding(rec, f"Text: {token}.", selection_kind=selection_kind)
        if stored_text and text_rec.get("status") in {"NO_RESULT", "SUCCESS", "UNAVAILABLE"}:
            if not text_only:
                understanding = f"Text: {token}. No text match; showing visual similarity."
            else:
                rec = _as_text_result(text_rec, token=token, quality=quality)
                rec["status"] = "NO_RESULT"
                if query_pixels is not None:
                    rec["query_pixels"] = query_pixels
                return _attach_understanding(rec, f"Text: {token}.", selection_kind=selection_kind)
        if stored_text and text_rec.get("status") == "ERROR" and not text_only:
            understanding = f"Text: {token}. Text lookup failed; showing visual similarity."
        elif stored_text and text_rec.get("status") == "ERROR":
            rec = _as_text_result(text_rec, token=token, quality=quality)
            rec["status"] = "ERROR"
            if query_pixels is not None:
                rec["query_pixels"] = query_pixels
            return _attach_understanding(rec, f"Text: {token}.", selection_kind=selection_kind)

    ready, missing = probe_region_pack()
    box = None
    if query_pixels is not None:
        box = (
            int(query_pixels["x"]),
            int(query_pixels["y"]),
            int(query_pixels["w"]),
            int(query_pixels["h"]),
        )
    dense = search_patches(
        store,
        crop,
        limit=capped_limit,
        exclude_media_id=media_id,
        cancelled=cancelled,
        token_stride=quality.patch_token_stride,
        token_floor=quality.patch_token_floor,
        score_floor=quality.patch_score_floor,
        coverage_floor=quality.patch_coverage_floor,
        query_box=box,
        shortlist_out=shortlist_out,
    )
    dense["search_profile"] = quality.key
    dense["search_profile_label"] = quality.label
    if query_pixels is not None:
        dense["query_pixels"] = query_pixels
    if dense.get("status") in {"SUCCESS", "NO_RESULT"}:
        _attach_coverage(dense, store)
        return _attach_understanding(dense, understanding, selection_kind=selection_kind)
    if dense.get("error_id") == "region.ENCODE":
        colour = _colour_result(
            store,
            crop,
            limit=capped_limit,
            exclude_media_id=media_id,
            cancelled=cancelled,
            reason=str(dense.get("reason") or "The region encoder did not finish. Showing colour only."),
            min_score=quality.whole_colour_floor,
            quality=quality,
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
                limit=capped_limit,
                exclude_media_id=media_id,
                cancelled=cancelled,
                reason=(
                    encode_error
                    or "The region encoder did not finish. Showing colour only."
                ),
                min_score=quality.whole_colour_floor,
                quality=quality,
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
                limit=capped_limit,
                exclude_media_id=media_id,
                min_score=quality.region_score_floor,
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
                rec["search_profile"] = quality.key
                rec["search_profile_label"] = quality.label
                return _attach_understanding(rec, understanding, selection_kind=selection_kind)
            colour = _colour_result(
                store,
                crop,
                limit=capped_limit,
                exclude_media_id=media_id,
                cancelled=cancelled,
                reason=(
                    "The region encoder is installed, but these photos have no matching "
                    "region index yet. Showing colour only. Add the folder again to index regions."
                ),
                min_score=quality.whole_colour_floor,
                quality=quality,
            )
            if query_pixels is not None:
                colour["query_pixels"] = query_pixels
            return _attach_understanding(colour, understanding, selection_kind=selection_kind)
    colour = _colour_result(
        store,
        crop,
        limit=capped_limit,
        exclude_media_id=media_id,
        cancelled=cancelled,
        reason=missing
        or "Region encoder is not installed. Showing colour only.",
        min_score=quality.whole_colour_floor,
        quality=quality,
    )
    if query_pixels is not None:
        colour["query_pixels"] = query_pixels
    return _attach_understanding(colour, understanding, selection_kind=selection_kind)


def name_selection(
    store: Path,
    *,
    media_id: str,
    image_path: Path | None,
    x: int,
    y: int,
    w: int,
    h: int,
) -> dict:
    """Name the highlighted crop. Does not search, persist, or write a person."""
    path = Path(image_path) if image_path is not None else None
    if path is None or not path.is_file():
        conn = sqlite3.connect(str(store))
        row = conn.execute("SELECT path FROM media WHERE media_id=?", (media_id,)).fetchone()
        conn.close()
        path = Path(row[0]) if row and row[0] else None
    blank = {
        "kind": "region_name",
        "persons": 0,
        "entity": False,
        "wrote_embedding": False,
    }
    if path is None or not path.is_file():
        return {
            **blank,
            "status": "UNAVAILABLE",
            "understanding": "This area could not be named.",
        }
    try:
        crop = crop_bgr(path, x, y, w, h)
    except RegionError:
        return {
            **blank,
            "status": "UNAVAILABLE",
            "understanding": "This area could not be named.",
        }
    detail = describe_selection_detail(store, media_id or "", x, y, w, h, crop=crop)
    return {
        **blank,
        "status": "SUCCESS",
        "understanding": str(detail.get("understanding") or "Unlabelled region."),
        "confidence": detail.get("confidence"),
    }


def _with_phase(similar: dict, phase: str) -> dict:
    stamped = dict(similar)
    stamped["search_phase"] = phase
    return stamped


def _bundle(saved: dict, similar: dict) -> dict:
    return {
        "region": saved,
        "similar": similar,
        "persons": 0,
        "entity": False,
        "wrote_embedding": False,
    }


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
    search_quality: str = "balanced",
    cancelled=None,
    shortlist_out: list | None = None,
) -> dict:
    crop = crop_bgr(Path(image_path), x, y, w, h)
    pixels = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    # Stored face, object, and text can label the box. The local noun stays on
    # Name this area so this search is not waiting on that model.
    understanding = describe_selection(store, media_id or "", x, y, w, h)
    stored_text = overlapping_text(store, media_id or "", x, y, w, h) if media_id else ""
    if not stored_text and selection_kind in {"text", "text_priority"}:
        stored_text = _ocr_crop_text(crop)
    started = time.perf_counter()
    result = _find_similar_from_crop(
        store,
        crop=crop,
        limit=limit,
        media_id=media_id,
        selection_kind=selection_kind,
        cancelled=cancelled,
        understanding=understanding,
        stored_text=stored_text,
        query_pixels=pixels,
        search_quality=search_quality,
        shortlist_out=shortlist_out,
    )
    from semblon import perf_evidence

    coverage = result.get("coverage") or {}
    perf_evidence.record(
        store,
        "search",
        latency_ms=(time.perf_counter() - started) * 1000.0,
        status=result.get("status"),
        results=result.get("count"),
        cancelled=bool(cancelled is not None and cancelled()),
        searchable=coverage.get("searchable"),
        detailed=coverage.get("detailed"),
        total=coverage.get("total"),
    )
    return result


def find_similar_crop(
    store: Path,
    *,
    crop,
    limit: int = 10,
    selection_kind: str | None = None,
    observed_text: str | None = None,
    search_quality: str = "balanced",
    cancelled=None,
) -> dict:
    """Search the local archive from an arbitrary query crop (for example screen selection)."""
    text = ""
    if selection_kind in {"text", "text_priority"}:
        text = str(observed_text or "").strip() or _ocr_crop_text(crop)
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
        search_quality=search_quality,
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
    search_quality: str = "balanced",
    cancelled=None,
    on_first=None,
    query_spec=None,
) -> dict:
    """Persist the box once, then search. A fuller quality can preview Fast first.

    Balanced and Max fuse the other local doors after the first look.
    Does not persist a vector or a second user box. Does not write identity.
    """
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
    if path is None or not path.is_file():
        return _bundle(saved, similar)

    quality = resolve_search_quality(search_quality)
    find_kwargs = {
        "image_path": path,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "limit": limit,
        "media_id": media_id,
        "selection_kind": selection_kind,
        "cancelled": cancelled,
    }
    from semblon.query_spec import parse_query_spec
    from semblon.region_parts import propose_parts, select_part

    spec = parse_query_spec(query_spec)
    crop = None
    try:
        crop = crop_bgr(path, x, y, w, h)
    except Exception:
        crop = None
    parts = propose_parts(store, media_id=media_id, x=x, y=y, w=w, h=h, crop=crop)
    chosen = select_part(parts, spec.part_index)
    box = chosen.get("box") if isinstance(chosen, dict) else None
    if spec.part_index >= 0 and isinstance(box, (list, tuple)) and len(box) == 4:
        find_kwargs["x"], find_kwargs["y"], find_kwargs["w"], find_kwargs["h"] = (
            int(box[0]),
            int(box[1]),
            int(box[2]),
            int(box[3]),
        )
        try:
            crop = crop_bgr(path, int(box[0]), int(box[1]), int(box[2]), int(box[3]))
        except Exception:
            pass

    shortlist: list[str] = []
    if quality.key == "fast" or on_first is None:
        similar = find_similar_region(
            store,
            search_quality=quality.key,
            shortlist_out=None if quality.key == "fast" else shortlist,
            **find_kwargs,
        )
        if quality.key != "fast":
            sharper = _refine_with_detail(
                store,
                shortlist,
                crop=crop,
                media_id=media_id,
                quality=quality,
                cancelled=cancelled,
                rerun=lambda: find_similar_region(store, search_quality=quality.key, **find_kwargs),
            )
            if sharper is not None:
                similar = sharper
        if quality.key != "fast" and crop is not None:
            similar = _fuse_region(
                store,
                similar,
                crop=crop,
                media_id=media_id,
                selection_kind=selection_kind,
                limit=limit,
                cancelled=cancelled,
                spec=spec,
                parts=parts,
            )
        if quality.key == "fast":
            similar = _with_phase(similar, "fast")
        elif crop is not None:
            similar = _check_matches(store, similar, crop=crop, cancelled=cancelled)
        similar.setdefault("parts", parts)
        similar.setdefault("query_spec", spec.as_public())
        similar.setdefault("strip_label", similar.get("similarity_basis"))
        return _bundle(saved, similar)

    fast = _with_phase(
        find_similar_region(store, search_quality="fast", **find_kwargs),
        "first",
    )
    if on_first is not None and not (cancelled is not None and cancelled()):
        on_first(_bundle(saved, fast))
    if cancelled is not None and cancelled():
        return _bundle(saved, _with_phase(fast, "kept"))

    full = find_similar_region(store, search_quality=quality.key, shortlist_out=shortlist, **find_kwargs)
    if crop is not None:
        full = _fuse_region(
            store,
            full,
            crop=crop,
            media_id=media_id,
            selection_kind=selection_kind,
            limit=limit,
            cancelled=cancelled,
            spec=spec,
            parts=parts,
        )
    fast_items = list(fast.get("items") or [])
    full_items = list(full.get("items") or [])
    if fast_items and not full_items:
        return _bundle(saved, _with_phase(fast, "kept"))
    if on_first is not None and full_items and not (cancelled is not None and cancelled()):
        on_first(_bundle(saved, _with_phase(full, "refined")))
    if cancelled is not None and cancelled():
        return _bundle(saved, _with_phase(full, "refined"))
    sharper = _refine_with_detail(
        store,
        shortlist,
        crop=crop,
        media_id=media_id,
        quality=quality,
        cancelled=cancelled,
        rerun=lambda: _fuse_region(
            store,
            find_similar_region(store, search_quality=quality.key, **find_kwargs),
            crop=crop,
            media_id=media_id,
            selection_kind=selection_kind,
            limit=limit,
            cancelled=cancelled,
            spec=spec,
            parts=parts,
        ),
        on_update=(
            None
            if on_first is None
            else lambda refreshed: on_first(_bundle(saved, _with_phase(refreshed, "detailed")))
            if refreshed.get("items") and not (cancelled is not None and cancelled())
            else None
        ),
    )
    if sharper is not None:
        full = sharper
        if (
            on_first is not None
            and not sharper.get("progress_published")
            and full.get("items")
            and not (cancelled is not None and cancelled())
        ):
            on_first(_bundle(saved, _with_phase(full, "detailed")))
        if cancelled is not None and cancelled():
            return _bundle(saved, _with_phase(full, "detailed"))
    checked = _check_matches(store, full, crop=crop, cancelled=cancelled)
    return _bundle(saved, checked)


def promote_for_search(
    store: Path,
    shortlist: list[str],
    *,
    crop,
    media_id: str | None,
    quality,
    cancelled=None,
    promote=None,
    on_done=None,
) -> dict:
    """Give fine detail to the photos this search most needs, then report what ran.

    Candidates come from two doors so an unprepared photo is never invisible:
    the best whole-picture matches that lack fine detail, and the best colour
    matches among photos not prepared at all.
    """
    from semblon import detail_priority

    ranked = detail_priority.lacking_detail(store, list(shortlist))
    chosen = ranked[: DETAIL_PROMOTE_MAX - 2]
    try:
        colour = _colour_result(
            store,
            crop,
            limit=DETAIL_PROMOTE_MAX,
            exclude_media_id=media_id,
            cancelled=cancelled,
            reason="",
            min_score=quality.whole_colour_floor,
            quality=quality,
        )
        ids = [str(i["media_id"]) for i in (colour.get("items") or []) if i.get("media_id")]
        for mid in detail_priority.lacking_detail(store, ids):
            if mid not in chosen and len(chosen) < DETAIL_PROMOTE_MAX:
                chosen.append(mid)
    except Exception:  # noqa: BLE001 — the colour door only adds candidates
        pass
    for mid in ranked[DETAIL_PROMOTE_MAX - 2 :]:
        if len(chosen) >= DETAIL_PROMOTE_MAX:
            break
        if mid not in chosen:
            chosen.append(mid)
    if not chosen:
        return {"requested": 0, "done": 0, "done_ids": []}
    run = promote or detail_priority.promote
    return run(
        store,
        chosen,
        cancelled=cancelled,
        budget_s=DETAIL_BUDGET_S,
        max_photos=DETAIL_PROMOTE_MAX,
        on_done=on_done,
    )


def _refine_with_detail(
    store: Path,
    shortlist: list[str],
    *,
    crop,
    media_id: str,
    quality,
    cancelled,
    rerun,
    on_update=None,
) -> dict | None:
    """Promote detail for the shortlist; rescore only when something finished.

    ``on_update`` receives a rescored result after each photo, so the shell can
    show new matches before the batch ends. The returned value is that last
    rescore. Without ``on_update`` there is one rescore at the end, which is
    what the benchmark measures.
    """
    if crop is None or not shortlist or (cancelled is not None and cancelled()):
        return None
    published: dict = {}

    def _after(_media_id: str) -> None:
        if on_update is None or (cancelled is not None and cancelled()):
            return
        refreshed = rerun()
        if not isinstance(refreshed, dict):
            return
        published["value"] = refreshed
        on_update(refreshed)

    summary = promote_for_search(
        store,
        shortlist,
        crop=crop,
        media_id=media_id,
        quality=quality,
        cancelled=cancelled,
        on_done=_after if on_update is not None else None,
    )
    if not summary.get("done") or (cancelled is not None and cancelled()):
        return None
    if published.get("value") is not None:
        refreshed = published["value"]
    else:
        refreshed = rerun()
    refreshed["detail_promoted"] = int(summary["done"])
    refreshed["detail_phases_ms"] = dict(summary.get("phases_ms") or {})
    refreshed["progress_published"] = on_update is not None
    return refreshed


def _check_matches(store: Path, similar: dict, *, crop, cancelled) -> dict:
    """Reorder the fused list after the first grid. Never blocks Fast."""
    from semblon.match_judge import judge_matches

    items = list(similar.get("items") or [])
    if crop is None or not items:
        return _with_phase(similar, similar.get("search_phase") or "refined")
    judged = judge_matches(
        store,
        crop=crop,
        items=items,
        cancelled=cancelled,
    )
    out = dict(similar)
    if judged.get("items"):
        out["items"] = judged["items"]
        out["count"] = len(judged["items"])
    out["judge"] = judged.get("judge") or "skipped"
    if judged.get("status") == "CANCELLED":
        return _with_phase(out, out.get("search_phase") or "refined")
    if judged.get("judge") == "ready":
        return _with_phase(out, "checked")
    if out.get("search_phase"):
        return out
    return out


def _fuse_region(
    store: Path,
    visual: dict,
    *,
    crop,
    media_id: str,
    selection_kind: str | None,
    limit: int,
    cancelled,
    spec,
    parts,
) -> dict:
    """Attach text / object / language doors without replacing a good first look."""
    from semblon.selection_retrieval import retrieve_selection

    fused = retrieve_selection(
        store,
        crop=crop,
        observations=_stored_observations(store, media_id),
        limit=limit,
        selection_kind=selection_kind,
        cancelled=cancelled,
        query_spec=spec,
        region_rec=visual,
        media_id=media_id,
        parts=parts,
    )
    if fused.get("status") == "SUCCESS" and fused.get("items"):
        out = dict(visual)
        out.update(
            {
                "status": "SUCCESS",
                "items": fused.get("items") or [],
                "count": fused.get("count") or 0,
                "channels": fused.get("channels") or [],
                "similarity_basis": visual.get("similarity_basis") or fused.get("strip_label"),
                "strip_label": fused.get("strip_label") or visual.get("similarity_basis"),
                "query_spec": fused.get("query_spec"),
                "parts": fused.get("parts") or parts,
                "engine": visual.get("engine") or fused.get("engine"),
                "reason": fused.get("reason") or visual.get("reason"),
            }
        )
        return out
    visual = dict(visual)
    visual["query_spec"] = spec.as_public() if hasattr(spec, "as_public") else spec
    visual["parts"] = parts
    visual["strip_label"] = visual.get("similarity_basis")
    visual["channels"] = fused.get("channels") or []
    return visual


def _stored_observations(store: Path, media_id: str) -> list[dict]:
    if not media_id or not Path(store).is_file():
        return []
    conn = connect_readonly(Path(store).resolve())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT i.kind, i.provider, i.payload_json
               FROM observation_items i
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE o.media_id=? AND i.kind IN ('object', 'text')""",
            (media_id,),
        ).fetchall()
    finally:
        conn.close()
    found = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        found.append({"kind": row["kind"], "provider": row["provider"], "payload": payload})
    return found
