"""On-demand fine-detail analysis for the photos a search is looking at.

Background indexing prepares every photo's whole picture first, then adds fine
detail one photo at a time. When someone searches, the promising photos that
still lack fine detail jump the queue and are analysed right away on the
interactive lane. A claim table keeps the search and the background pass from
working on the same photo at the same time. Finished work is stamped in the
same ``work_items`` mask the background pass uses, so it survives a restart and
is never repeated.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from semblon.scan_tiers import TIER_DETAIL, TIER_SEMANTIC
from semblon.store import connect, writer_lock

_LOCK = threading.Lock()
_INFLIGHT: dict[str, float] = {}
_STALE_S = 180.0
_STATS = {"promoted": 0, "duplicates_avoided": 0, "already_done": 0, "failed": 0}


def claim(media_id: str) -> bool:
    """True when the caller now owns the photo. False when someone else is on it.

    A claim older than ``_STALE_S`` is treated as abandoned by a crashed worker.
    """
    now = time.monotonic()
    with _LOCK:
        taken = _INFLIGHT.get(media_id)
        if taken is not None and now - taken < _STALE_S:
            _STATS["duplicates_avoided"] += 1
            return False
        _INFLIGHT[media_id] = now
        return True


def release(media_id: str) -> None:
    with _LOCK:
        _INFLIGHT.pop(media_id, None)


def stats() -> dict:
    with _LOCK:
        return {**_STATS, "in_flight": len(_INFLIGHT)}


def reset_stats() -> None:
    with _LOCK:
        for key in _STATS:
            _STATS[key] = 0


def mask_of(conn, media_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(tier_done_mask), 0) FROM work_items WHERE media_id=?", (media_id,)
    ).fetchone()
    return int(row[0] or 0)


def lacking_detail(store: Path, media_ids: list[str]) -> list[str]:
    """Photos from ``media_ids`` (order kept) whose fine detail is not stored yet."""
    if not media_ids or not Path(store).is_file():
        return []
    conn = connect(Path(store))
    try:
        return [mid for mid in media_ids if not (mask_of(conn, mid) & TIER_DETAIL)]
    finally:
        conn.close()


def _default_decode(path: Path):
    from semblon.ingest import _decode_bgr

    return _decode_bgr(None, path)


def promote(
    store: Path,
    media_ids: list[str],
    *,
    cancelled=None,
    budget_s: float = 12.0,
    max_photos: int = 8,
    decode=None,
    indexer=None,
    on_done=None,
) -> dict:
    """Analyse fine detail for ``media_ids`` now, best candidates first.

    Returns counts. Stops early when cancelled or over budget; whatever was
    finished stays stored. Photos with no whole-picture pass get both passes.
    """
    from semblon.region_encoder import DEPTH_DETAIL, DEPTH_FULL, index_image_regions

    decode = decode or _default_decode
    indexer = indexer or index_image_regions
    out = {
        "requested": len(media_ids),
        "done": 0,
        "busy": 0,
        "already_done": 0,
        "failed": 0,
        "cancelled": False,
        "elapsed_s": 0.0,
        "done_ids": [],
    }
    started = time.perf_counter()
    conn = connect(Path(store))
    try:
        for media_id in media_ids:
            if cancelled is not None and cancelled():
                out["cancelled"] = True
                break
            if out["done"] >= max_photos or time.perf_counter() - started > budget_s:
                break
            if not claim(media_id):
                out["busy"] += 1
                continue
            try:
                mask = mask_of(conn, media_id)
                if mask & TIER_DETAIL:
                    out["already_done"] += 1
                    with _LOCK:
                        _STATS["already_done"] += 1
                    continue
                row = conn.execute(
                    "SELECT path FROM work_items WHERE media_id=? ORDER BY updated_at DESC LIMIT 1",
                    (media_id,),
                ).fetchone()
                obs = conn.execute(
                    """SELECT observation_id, run_id FROM observations
                       WHERE media_id=? AND frame_id IS NULL ORDER BY rowid DESC LIMIT 1""",
                    (media_id,),
                ).fetchone()
                if row is None or obs is None:
                    out["failed"] += 1
                    continue
                img = decode(Path(row[0]))
                if img is None:
                    out["failed"] += 1
                    continue
                depth = DEPTH_DETAIL if mask & TIER_SEMANTIC else DEPTH_FULL
                with writer_lock():
                    try:
                        indexed = indexer(
                            conn,
                            observation_id=str(obs[0]),
                            run_id=str(obs[1]),
                            img=img,
                            depth=depth,
                            interactive=True,
                            cancelled=cancelled,
                        )
                    except Exception:  # noqa: BLE001
                        indexed = None
                    stored = (
                        int((indexed or {}).get("scene") or 0)
                        + int((indexed or {}).get("patch") or 0)
                        + int((indexed or {}).get("region") or 0)
                    )
                    if indexed is None or (indexed.get("note") and stored == 0 and int(indexed.get("jobs") or 0) > 0):
                        conn.rollback()
                        out["failed"] += 1
                        with _LOCK:
                            _STATS["failed"] += 1
                        continue
                    conn.execute(
                        "UPDATE work_items SET tier_done_mask = tier_done_mask | ? WHERE media_id=?",
                        (TIER_SEMANTIC | TIER_DETAIL, media_id),
                    )
                    conn.commit()
                out["done"] += 1
                out["done_ids"].append(media_id)
                with _LOCK:
                    _STATS["promoted"] += 1
                if on_done is not None:
                    on_done(media_id)
            finally:
                release(media_id)
    finally:
        conn.close()
        out["elapsed_s"] = round(time.perf_counter() - started, 3)
    return out
