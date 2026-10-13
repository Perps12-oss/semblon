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
from semblon.semantic_visual import SemanticVisualProvider, describe_region_appearance
from semblon.visual_cache import load_analysis, save_analysis
from semblon.visual_segment import (
    LABEL_TYPE_FACE,
    LABEL_TYPE_UNKNOWN,
    SaliencePolicy,
    VisualSegment,
    apply_salience,
    link_segment_lattice,
    new_segment_id,
    reconcile_sources,
)

# Appearance proposals below this confidence stay unnamed. SAM 2 does not name.
_NAME_BIND_MIN = 0.55
_UNNAMED_LABELS = {"", "region", "unknown", "unknown region"}

OnProgress = Callable[[str, dict], None]

READINESS_L0 = "L0"
READINESS_L1 = "L1"
READINESS_L2 = "L2"
READINESS_L3 = "L3"
READINESS_L4 = "L4"


def attach_region_names(
    image: np.ndarray,
    regions: list[dict],
    *,
    only_unlabeled: bool = True,
) -> tuple[list[dict], dict]:
    """Propose a local appearance name, bind it, or abstain.

    This is not SAM 2. A bound label is an appearance proposal. Unknown stays
    valid when the proposal is weak or generic.
    """
    t0 = time.perf_counter()
    arr = np.asarray(image)
    h, w = arr.shape[:2]
    proposed = bound = abstained = 0
    named: list[dict] = []
    for reg in regions:
        payload = dict(reg.get("payload") or {})
        label = str(reg.get("label") or "").strip()
        if only_unlabeled and label.lower() not in _UNNAMED_LABELS:
            payload.setdefault("naming", "provider")
            named.append({**reg, "payload": payload})
            continue
        x1, y1, x2, y2 = [int(round(float(v))) for v in reg["bbox"]]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = arr[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else arr[:0, :0]
        if crop.size == 0:
            payload["naming"] = "abstain"
            abstained += 1
            named.append(
                {
                    **reg,
                    "label": "region",
                    "label_type": LABEL_TYPE_UNKNOWN,
                    "payload": payload,
                }
            )
            continue
        bw, bh = max(1, x2 - x1), max(1, y2 - y1)
        proposal, conf = describe_region_appearance(
            crop,
            cy_frac=((y1 + y2) / 2) / float(max(h, 1)),
            area_frac=(bw * bh) / float(max(w * h, 1)),
            aspect=bw / float(bh),
        )
        proposed += 1
        payload["namer"] = "appearance"
        payload["proposed_label"] = proposal
        payload["proposal_confidence"] = float(conf)
        generic = (not proposal) or ("region" in proposal.lower())
        if float(conf) >= _NAME_BIND_MIN and not generic:
            payload["naming"] = "bind"
            bound += 1
            named.append(
                {
                    **reg,
                    "label": proposal,
                    "label_type": "region",
                    "payload": payload,
                }
            )
        else:
            payload["naming"] = "abstain"
            abstained += 1
            named.append(
                {
                    **reg,
                    "label": "region",
                    "label_type": LABEL_TYPE_UNKNOWN,
                    "payload": payload,
                }
            )
    return named, {
        "proposed": proposed,
        "bound": bound,
        "abstained": abstained,
        "naming_s": time.perf_counter() - t0,
    }


def _bind_names_on_segments(image: np.ndarray, segments: list[VisualSegment]) -> dict:
    """Name surviving segments in place. Does not add or drop regions."""
    regions = [
        {
            "bbox": seg.bbox,
            "label": seg.label,
            "label_type": seg.label_type,
            "confidence": seg.confidence,
            "payload": dict(seg.payload),
            "source_provider": seg.source_provider,
        }
        for seg in segments
    ]
    named, stats = attach_region_names(image, regions, only_unlabeled=True)
    for seg, reg in zip(segments, named):
        seg.label = str(reg["label"])
        seg.label_type = str(reg["label_type"])
        seg.payload = dict(reg.get("payload") or {})
    return stats


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
    sam2_status = None
    if provider is None:
        from semblon.sam2_runtime import provider_for_discovery

        provider, sam2_status = provider_for_discovery()
    prov = provider
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
        "readiness": READINESS_L1,
        "sam2_state": getattr(sam2_status, "state", "") if sam2_status else "",
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
    _prog("L1", readiness=READINESS_L1, n=len(face_segs))
    _prog("t0_faces", n=len(face_segs))
    t_faces = time.perf_counter()

    # T1 — class-agnostic regions. SAM 2 when the runtime is READY.
    t_reg0 = time.perf_counter()
    regions = list(prov.discover_regions(arr))
    t_regions = time.perf_counter() - t_reg0
    _prog("t1_regions", n=len(regions), seconds=t_regions, readiness=READINESS_L1)
    discovery_stats = dict(getattr(prov, "last_stats", {}) or {})
    metrics["region_discovery_s"] = t_regions
    metrics["discovery_s"] = float(discovery_stats.get("discovery_s", t_regions))
    metrics["normalize_s"] = float(discovery_stats.get("normalize_s", 0.0))
    metrics["n_raw_masks"] = int(discovery_stats.get("n_raw", len(regions)))
    metrics["n_raw_regions"] = metrics["n_raw_masks"]
    metrics["n_quality_kept"] = int(discovery_stats.get("n_quality_kept", len(regions)))
    metrics["n_removed_quality"] = int(discovery_stats.get("n_removed_quality", 0))
    metrics["n_removed_dedupe"] = int(discovery_stats.get("n_removed_dedupe", 0))
    metrics["n_nested_retained"] = int(discovery_stats.get("n_nested_retained", 0))
    if discovery_stats.get("sam2_state"):
        metrics["sam2_state"] = discovery_stats["sam2_state"]
    metrics["decode_s"] = 0.0

    # Concepts stay on the OpenCV path. SAM 2's provider returns none on purpose.
    t_con0 = time.perf_counter()
    concepts = list(prov.discover_concepts(arr, regions=regions))
    optional_errors = list(getattr(prov, "last_optional_errors", []) or [])
    if optional_errors:
        metrics["optional_errors"] = optional_errors
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
    t_lat0 = time.perf_counter()
    lattice = link_segment_lattice(segments)
    metrics["lattice_s"] = time.perf_counter() - t_lat0
    metrics["n_contains"] = len(lattice["contains"])
    metrics["n_overlaps"] = len(lattice["overlaps"])
    metrics["n_nested_retained"] = max(
        int(metrics.get("n_nested_retained") or 0),
        sum(1 for seg in segments if seg.parent_segment_id),
    )
    _prog("t3_reconcile", n=len(segments), readiness=READINESS_L2)

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

    t_map0 = time.perf_counter()
    index = build_pixel_index(segments, height=h, width=w, masks=masks)
    metrics["owner_map_s"] = time.perf_counter() - t_map0
    metrics["readiness"] = READINESS_L2
    spatial = {
        "segments": segments,
        "index": index,
        "masks": masks,
        "metrics": dict(metrics),
        "provider": prov.info.name,
        "model_id": prov.info.model_id,
        "model_version": prov.info.model_version,
    }
    _prog("L2", readiness=READINESS_L2, partial=spatial)

    t_name0 = time.perf_counter()
    name_stats = _bind_names_on_segments(arr, segments)
    metrics["naming_s"] = float(name_stats.get("naming_s") or (time.perf_counter() - t_name0))
    metrics["names_proposed"] = int(name_stats.get("proposed") or 0)
    metrics["names_bound"] = int(name_stats.get("bound") or 0)
    metrics["names_abstained"] = int(name_stats.get("abstained") or 0)
    metrics["readiness"] = READINESS_L3
    _prog("L3", readiness=READINESS_L3, partial=spatial)

    t_hover0 = time.perf_counter()
    _ = index.lookup(w // 2, h // 2)
    metrics["hover_lookup_s"] = time.perf_counter() - t_hover0
    elapsed = time.perf_counter() - t0
    metrics["readiness"] = READINESS_L4
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
    _prog("L4", readiness=READINESS_L4, partial=spatial)
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
    if provider is None:
        from semblon.sam2_runtime import provider_for_discovery

        provider, _status = provider_for_discovery()
    prov = provider
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
