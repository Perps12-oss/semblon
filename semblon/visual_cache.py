"""Persistent visual-understanding cache (sidecars next to the store).

Tied to media_id + provider + model/version + analysis config.
Does not modify original media files. Does not invent DDL.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from semblon.pixel_index import PixelSegmentIndex, build_pixel_index, decode_map, encode_index
from semblon.visual_segment import VisualSegment

CACHE_VERSION = 1
PROVIDER_DEFAULT = "local_opencv"
MODEL_DEFAULT = "local-opencv"
MODEL_VERSION_DEFAULT = "1"
CONFIG_DEFAULT = "salience-v1"


def cache_key(
    *,
    provider: str = PROVIDER_DEFAULT,
    model_id: str = MODEL_DEFAULT,
    model_version: str = MODEL_VERSION_DEFAULT,
    config: str = CONFIG_DEFAULT,
) -> str:
    raw = f"{CACHE_VERSION}|{provider}|{model_id}|{model_version}|{config}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cache_dir(store: Path) -> Path:
    return Path(store).resolve().parent / "visual_cache"


def media_cache_dir(store: Path, media_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in media_id)[:80]
    return cache_dir(store) / safe


def cache_paths(store: Path, media_id: str, key: str | None = None) -> dict[str, Path]:
    key = key or cache_key()
    root = media_cache_dir(store, media_id) / key
    return {
        "root": root,
        "meta": root / "meta.json",
        "segments": root / "segments.json",
        "index": root / "pixel_map.bin",
        "masks": root / "masks.npz",
    }


def save_analysis(
    store: Path,
    *,
    media_id: str,
    segments: list[VisualSegment],
    index: PixelSegmentIndex,
    masks: dict[str, np.ndarray] | None = None,
    provider: str = PROVIDER_DEFAULT,
    model_id: str = MODEL_DEFAULT,
    model_version: str = MODEL_VERSION_DEFAULT,
    config: str = CONFIG_DEFAULT,
    metrics: dict | None = None,
) -> Path:
    key = cache_key(
        provider=provider,
        model_id=model_id,
        model_version=model_version,
        config=config,
    )
    paths = cache_paths(store, media_id, key)
    paths["root"].mkdir(parents=True, exist_ok=True)
    meta = {
        "cache_version": CACHE_VERSION,
        "media_id": media_id,
        "provider": provider,
        "model_id": model_id,
        "model_version": model_version,
        "config": config,
        "key": key,
        "created_at": time.time(),
        "n_segments": len(segments),
        "coverage_frac": index.coverage_frac(),
        "labelled_frac": index.labelled_frac(),
        "image_h": index.height,
        "image_w": index.width,
        "metrics": metrics or {},
    }
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    paths["segments"].write_text(
        json.dumps([s.as_dict() for s in segments], indent=2),
        encoding="utf-8",
    )
    paths["index"].write_bytes(encode_index(index))
    if masks:
        # Store as compressed uint8 maps keyed by segment_id.
        np.savez_compressed(
            paths["masks"],
            **{sid: (m > 0).astype(np.uint8) for sid, m in masks.items()},
        )
    return paths["root"]


def load_analysis(
    store: Path,
    media_id: str,
    *,
    provider: str = PROVIDER_DEFAULT,
    model_id: str = MODEL_DEFAULT,
    model_version: str = MODEL_VERSION_DEFAULT,
    config: str = CONFIG_DEFAULT,
) -> dict | None:
    key = cache_key(
        provider=provider,
        model_id=model_id,
        model_version=model_version,
        config=config,
    )
    paths = cache_paths(store, media_id, key)
    if not paths["meta"].is_file() or not paths["segments"].is_file():
        return None
    try:
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        raw_segs = json.loads(paths["segments"].read_text(encoding="utf-8"))
        segments = [VisualSegment.from_dict(r) for r in raw_segs]
        by_id = {s.segment_id: s for s in segments}
        order = [s.segment_id for s in segments]
        if paths["index"].is_file():
            blob = paths["index"].read_bytes()
            flat = decode_map(blob, order)
            index = PixelSegmentIndex(
                height=int(flat.shape[0]),
                width=int(flat.shape[1]),
                map=flat,
                order=order,
                by_id=by_id,
            )
        else:
            index = build_pixel_index(
                segments,
                height=int(meta.get("image_h") or 1),
                width=int(meta.get("image_w") or 1),
            )
        masks: dict[str, np.ndarray] = {}
        if paths["masks"].is_file():
            with np.load(paths["masks"]) as z:
                for sid in z.files:
                    masks[sid] = z[sid]
        return {
            "meta": meta,
            "segments": segments,
            "index": index,
            "masks": masks,
            "key": key,
            "paths": paths,
        }
    except (OSError, ValueError, json.JSONDecodeError, KeyError):
        return None
