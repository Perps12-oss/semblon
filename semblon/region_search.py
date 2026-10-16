"""Find similar from a persisted user box using a query-time appearance crop.

This is the region Similar operation. It is not `search.search_similar`
(stored non-face embedding neighbours) and not Lens `query_image` (capability
report). One path: persist the box, then compare the crop in appearance space.

Does not write an embedding row for the box. Does not create a sibling item.
Face identity is forbidden.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from semblon.compare import CompareError, compare_space
from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, color_histogram
from semblon.user_region import RegionError, persist_user_region


def _open_ro(store: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def crop_bgr(image_path: Path, x: int, y: int, w: int, h: int):
    import cv2

    from semblon.temporal import _decode_still

    image = _decode_still(Path(image_path))
    if image is None:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
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


def search_vector(
    store: Path,
    *,
    blob: bytes,
    modality: str,
    pack_id: str,
    dim: int,
    limit: int = 10,
    exclude_item_id: str | None = None,
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
        if exclude_item_id and row["item_id"] == exclude_item_id:
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
                "why": "same modality+pack; query-time crop; not a person",
            }
        )
    scored.sort(key=lambda x: -x["score"])
    items = scored[:limit]
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


def find_similar_region(
    store: Path,
    *,
    image_path: Path,
    x: int,
    y: int,
    w: int,
    h: int,
    limit: int = 10,
) -> dict:
    crop = crop_bgr(Path(image_path), x, y, w, h)
    blob = appearance_vector(crop)
    rec = search_vector(
        store,
        blob=blob,
        modality="appearance",
        pack_id=APPEARANCE_PACK,
        dim=APPEARANCE_DIM,
        limit=limit,
    )
    rec["query_pixels"] = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    rec["wrote_embedding"] = False
    # Product label: this door is colour histogram, never face or semantic search.
    rec["similarity_basis"] = "Selected region (colour histogram)"
    return rec


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
            store, image_path=path, x=x, y=y, w=w, h=h, limit=limit
        )
    return {
        "region": saved,
        "similar": similar,
        "persons": 0,
        "entity": False,
        "wrote_embedding": False,
    }
