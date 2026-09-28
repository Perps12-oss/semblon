"""Open-vocabulary visual analysis pipeline.

arbitrary image → concept discovery → region discovery → reconcile →
VisualSegments → pixel map → cache.

Runs as a JobEngine visual job or synchronously for tests. Never writes
faces.person_id or embeddings.modality='face'. Does not invent DDL —
optional observation_items dual-write uses kind=object + payload_json.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import numpy as np

from semblon.pixel_index import PixelSegmentIndex, build_pixel_index
from semblon.semantic_visual import LocalSemanticVisualProvider, SemanticVisualProvider
from semblon.visual_cache import load_analysis, save_analysis
from semblon.visual_segment import (
    LABEL_TYPE_FACE,
    SaliencePolicy,
    VisualSegment,
    apply_salience,
    new_segment_id,
    reconcile_sources,
)

OnProgress = Callable[[str, dict], None]


def analyze_image(
    image: np.ndarray,
    *,
    media_id: str,
    observation_id: str | None = None,
    frame_id: str | None = None,
    provider: SemanticVisualProvider | None = None,
    policy: SaliencePolicy | None = None,
    existing_faces: list[dict] | None = None,
    on_progress: OnProgress | None = None,
) -> dict:
    """Full vertical slice. Returns segments, index, masks, metrics."""
    t0 = time.perf_counter()
    prov = provider or LocalSemanticVisualProvider()
    pol = policy or SaliencePolicy()
    arr = np.asarray(image)
    if arr.ndim != 3:
        raise ValueError("image must be HxWxC BGR")
    h, w = arr.shape[:2]
    metrics: dict = {
        "provider": prov.info.name,
        "model_id": prov.info.model_id,
        "model_version": prov.info.model_version,
        "image_h": h,
        "image_w": w,
    }

    def _prog(stage: str, **extra):
        if on_progress is not None:
            on_progress(stage, extra)

    # T0 — existing face observations (identity stays on faces table).
    face_segs: list[VisualSegment] = []
    for f in existing_faces or []:
        try:
            bbox = (
                float(f["bbox_x1"]),
                float(f["bbox_y1"]),
                float(f["bbox_x2"]),
                float(f["bbox_y2"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        face_segs.append(
            VisualSegment(
                segment_id=new_segment_id(),
                observation_id=observation_id,
                media_id=media_id,
                frame_id=frame_id,
                label="face",
                label_type=LABEL_TYPE_FACE,
                confidence=0.9,
                bbox=bbox,
                source_provider="facekit",
                model_id="facekit",
                model_version="1",
                payload={"face_id": f.get("face_id"), "observation_only": True},
            )
        )
    _prog("t0_faces", n=len(face_segs))
    t_faces = time.perf_counter()

    # T1 — class-agnostic regions.
    t_reg0 = time.perf_counter()
    regions = list(prov.discover_regions(arr))
    t_regions = time.perf_counter() - t_reg0
    _prog("t1_regions", n=len(regions), seconds=t_regions)
    metrics["region_discovery_s"] = t_regions
    metrics["n_raw_regions"] = len(regions)

    # T2 — semantic inventory (may include CLIP/VLM when available).
    t_con0 = time.perf_counter()
    concepts = list(prov.discover_concepts(arr, regions=regions))
    # Ground ungrounded concepts via segment_concept.
    grounded = []
    for c in concepts:
        if c.get("bbox") is not None:
            grounded.append(c)
            continue
        hits = prov.segment_concept(arr, str(c.get("label") or ""))
        if hits:
            best = max(hits, key=lambda r: float(r.get("confidence") or 0))
            grounded.append({**c, "bbox": best["bbox"], "mask": best.get("mask")})
    t_concepts = time.perf_counter() - t_con0
    _prog("t2_concepts", n=len(grounded), seconds=t_concepts)
    metrics["concept_discovery_s"] = t_concepts
    metrics["n_concepts"] = len(grounded)

    # T3 — reconcile + salience.
    segments = reconcile_sources(
        concepts=grounded,
        regions=regions,
        media_id=media_id,
        observation_id=observation_id,
        frame_id=frame_id,
        provider=prov.info.name,
        model_id=prov.info.model_id,
        model_version=prov.info.model_version,
        image_w=w,
        image_h=h,
        policy=pol,
    )
    # Prefer face segments; avoid swallowing them in salience cap.
    segments = apply_salience(
        face_segs + segments, image_w=w, image_h=h, policy=pol
    )
    _prog("t3_reconcile", n=len(segments))

    # Collect masks (source image coords).
    masks: dict[str, np.ndarray] = {}
    # Re-attach masks from region/concept dicts by bbox match when possible.
    raw_with_masks = [r for r in regions + grounded if r.get("mask") is not None]
    for seg in segments:
        for raw in raw_with_masks:
            rb = raw.get("bbox")
            if rb is None:
                continue
            if (
                abs(float(rb[0]) - seg.bbox[0]) < 1.5
                and abs(float(rb[1]) - seg.bbox[1]) < 1.5
                and abs(float(rb[2]) - seg.bbox[2]) < 1.5
                and abs(float(rb[3]) - seg.bbox[3]) < 1.5
            ):
                m = np.asarray(raw["mask"])
                if m.shape[:2] == (h, w):
                    masks[seg.segment_id] = m
                break
        if seg.segment_id not in masks:
            # Rectangular fallback mask for hover highlight.
            m = np.zeros((h, w), np.uint8)
            x1, y1, x2, y2 = [int(round(v)) for v in seg.bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            m[y1:y2, x1:x2] = 255
            masks[seg.segment_id] = m
        seg.mask_ref = f"cache:{seg.segment_id}"

    index = build_pixel_index(segments, height=h, width=w, masks=masks)
    elapsed = time.perf_counter() - t0
    metrics.update(
        {
            "analysis_s": elapsed,
            "t0_faces_s": t_faces - t0,
            "n_segments": len(segments),
            "coverage_frac": index.coverage_frac(),
            "labelled_frac": index.labelled_frac(),
            "labels": sorted({s.label for s in segments}),
        }
    )
    _prog("done", **metrics)
    return {
        "segments": segments,
        "index": index,
        "masks": masks,
        "metrics": metrics,
        "provider": prov.info.name,
        "model_id": prov.info.model_id,
        "model_version": prov.info.model_version,
    }


def analyze_and_cache(
    store: Path,
    *,
    media_id: str,
    image: np.ndarray,
    observation_id: str | None = None,
    frame_id: str | None = None,
    existing_faces: list[dict] | None = None,
    provider: SemanticVisualProvider | None = None,
    policy: SaliencePolicy | None = None,
    on_progress: OnProgress | None = None,
    force: bool = False,
) -> dict:
    """Load cache if valid; else analyze and persist sidecar."""
    prov = provider or LocalSemanticVisualProvider()
    if not force:
        cached = load_analysis(
            store,
            media_id,
            provider=prov.info.name,
            model_id=prov.info.model_id,
            model_version=prov.info.model_version,
        )
        if cached is not None:
            meta_metrics = (cached.get("meta") or {}).get("metrics") or {}
            cached["metrics"] = {**meta_metrics, "cache_hit": True}
            return cached
    result = analyze_image(
        image,
        media_id=media_id,
        observation_id=observation_id,
        frame_id=frame_id,
        provider=prov,
        policy=policy,
        existing_faces=existing_faces,
        on_progress=on_progress,
    )
    root = save_analysis(
        store,
        media_id=media_id,
        segments=result["segments"],
        index=result["index"],
        masks=result["masks"],
        provider=result["provider"],
        model_id=result["model_id"],
        model_version=result["model_version"],
        metrics=result["metrics"],
    )
    result["cache_root"] = root
    result["metrics"]["cache_hit"] = False
    return result


def hover_lookup(
    index: PixelSegmentIndex,
    *,
    widget_x: float,
    widget_y: float,
    ox: float,
    oy: float,
    scale: float,
) -> VisualSegment | None:
    """Widget → source image → pixel map. Instant; no model calls."""
    if scale <= 0:
        return None
    ix = int((widget_x - ox) / scale)
    iy = int((widget_y - oy) / scale)
    return index.lookup(ix, iy)


def display_mask_overlay(
    mask: np.ndarray,
    *,
    scale: float,
    ox: float,
    oy: float,
    color_bgr: tuple[int, int, int] = (40, 94, 202),
    alpha: float = 0.35,
) -> tuple[np.ndarray, int, int]:
    """Build a translucent RGBA overlay image (display size) from a source mask."""
    import cv2

    h, w = mask.shape[:2]
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = cv2.resize(
        (mask > 0).astype(np.uint8) * 255, (nw, nh), interpolation=cv2.INTER_NEAREST
    )
    rgba = np.zeros((nh, nw, 4), dtype=np.uint8)
    rgba[:, :, 0] = color_bgr[2]
    rgba[:, :, 1] = color_bgr[1]
    rgba[:, :, 2] = color_bgr[0]
    rgba[:, :, 3] = (resized > 0).astype(np.uint8) * int(max(0, min(255, round(alpha * 255))))
    return rgba, int(round(ox)), int(round(oy))
