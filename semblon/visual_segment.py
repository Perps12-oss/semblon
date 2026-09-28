"""VisualSegment — observation-level grounded region (not identity).

A VisualSegment is not a person, Entity, Track, cluster, or face identity.
It is a labelled visual region on one media/frame. Persistence reuses
observation_items (kind=object) + payload_json; masks live in visual_cache
sidecars. Never writes faces.person_id or embeddings.modality='face'.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


LABEL_TYPE_CONCEPT = "concept"
LABEL_TYPE_REGION = "region"
LABEL_TYPE_FACE = "face"
LABEL_TYPE_UNKNOWN = "unknown"


@dataclass
class VisualSegment:
    """Model-independent observation-level visual region."""

    segment_id: str
    observation_id: str | None
    media_id: str
    frame_id: str | None
    label: str
    label_type: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1,y1,x2,y2 image pixels
    mask_ref: str | None = None
    parent_segment_id: str | None = None
    source_provider: str = "semantic_visual"
    model_id: str = "local"
    model_version: str = "1"
    embedding_ref: str | None = None
    created_at: float = field(default_factory=lambda: time.time())
    area_frac: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["bbox"] = list(self.bbox)
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> "VisualSegment":
        bbox = raw.get("bbox") or (0, 0, 0, 0)
        if isinstance(bbox, dict):
            bbox = (
                float(bbox["x1"]),
                float(bbox["y1"]),
                float(bbox["x2"]),
                float(bbox["y2"]),
            )
        else:
            bbox = tuple(float(x) for x in bbox)
        return cls(
            segment_id=str(raw["segment_id"]),
            observation_id=raw.get("observation_id"),
            media_id=str(raw["media_id"]),
            frame_id=raw.get("frame_id"),
            label=str(raw.get("label") or "region"),
            label_type=str(raw.get("label_type") or LABEL_TYPE_REGION),
            confidence=float(raw.get("confidence") or 0.0),
            bbox=bbox,  # type: ignore[arg-type]
            mask_ref=raw.get("mask_ref"),
            parent_segment_id=raw.get("parent_segment_id"),
            source_provider=str(raw.get("source_provider") or "semantic_visual"),
            model_id=str(raw.get("model_id") or "local"),
            model_version=str(raw.get("model_version") or "1"),
            embedding_ref=raw.get("embedding_ref"),
            created_at=float(raw.get("created_at") or time.time()),
            area_frac=float(raw.get("area_frac") or 0.0),
            payload=dict(raw.get("payload") or {}),
        )


def new_segment_id() -> str:
    return f"vs-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class SaliencePolicy:
    """Configurable rules that reject garbage micro-fragments."""

    min_area_frac: float = 0.004
    max_area_frac: float = 0.92
    min_confidence: float = 0.15
    max_segments: int = 48
    min_side_px: int = 8
    iou_merge: float = 0.82
    duplicate_label_iou: float = 0.55
    prefer_children_when_parent_frac: float = 0.55


DEFAULT_SALIENCE = SaliencePolicy()


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_iou(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def apply_salience(
    segments: list[VisualSegment],
    *,
    image_w: int,
    image_h: int,
    policy: SaliencePolicy = DEFAULT_SALIENCE,
) -> list[VisualSegment]:
    """Filter tiny / whole-image / low-confidence noise. Preserve nested structure."""
    total = float(max(image_w * image_h, 1))
    kept: list[VisualSegment] = []
    for seg in segments:
        x1, y1, x2, y2 = seg.bbox
        w, h = x2 - x1, y2 - y1
        if w < policy.min_side_px or h < policy.min_side_px:
            continue
        area = bbox_area(seg.bbox)
        frac = area / total
        seg.area_frac = frac
        if frac < policy.min_area_frac or frac > policy.max_area_frac:
            continue
        if seg.confidence < policy.min_confidence:
            continue
        kept.append(seg)

    # Merge near-duplicate boxes with identical/similar labels.
    kept.sort(key=lambda s: (-s.confidence, -s.area_frac))
    merged: list[VisualSegment] = []
    for seg in kept:
        dup = False
        for other in merged:
            iou = bbox_iou(seg.bbox, other.bbox)
            same_label = seg.label.strip().lower() == other.label.strip().lower()
            if iou >= policy.iou_merge or (
                same_label and iou >= policy.duplicate_label_iou
            ):
                # Keep the higher-confidence / larger useful child preference.
                if seg.confidence > other.confidence and seg.area_frac < other.area_frac:
                    # Prefer more specific (smaller) high-confidence child: attach.
                    seg.parent_segment_id = other.segment_id
                    merged.append(seg)
                dup = True
                break
        if not dup:
            merged.append(seg)

    # Cap count: keep highest confidence, but always keep labelled faces.
    faces = [s for s in merged if s.label_type == LABEL_TYPE_FACE]
    rest = [s for s in merged if s.label_type != LABEL_TYPE_FACE]
    rest.sort(key=lambda s: (-s.confidence, -s.area_frac))
    budget = max(0, policy.max_segments - len(faces))
    out = faces + rest[:budget]
    return out


def reconcile_sources(
    *,
    concepts: list[dict],
    regions: list[dict],
    media_id: str,
    observation_id: str | None = None,
    frame_id: str | None = None,
    provider: str = "semantic_visual",
    model_id: str = "local",
    model_version: str = "1",
    image_w: int,
    image_h: int,
    policy: SaliencePolicy = DEFAULT_SALIENCE,
) -> list[VisualSegment]:
    """Merge semantic concepts + class-agnostic regions into VisualSegments."""
    segments: list[VisualSegment] = []

    # Index regions by rough centre for concept grounding.
    for reg in regions:
        bbox = tuple(float(x) for x in reg["bbox"])
        label = str(reg.get("label") or "region")
        segments.append(
            VisualSegment(
                segment_id=new_segment_id(),
                observation_id=observation_id,
                media_id=media_id,
                frame_id=frame_id,
                label=label,
                label_type=str(reg.get("label_type") or LABEL_TYPE_REGION),
                confidence=float(reg.get("confidence") or 0.4),
                bbox=bbox,  # type: ignore[arg-type]
                mask_ref=reg.get("mask_ref"),
                parent_segment_id=reg.get("parent_segment_id"),
                source_provider=str(reg.get("source_provider") or provider),
                model_id=model_id,
                model_version=model_version,
                area_frac=float(reg.get("area_frac") or 0.0),
                payload=dict(reg.get("payload") or {}),
            )
        )

    for concept in concepts:
        bbox = concept.get("bbox")
        if bbox is None:
            # Concept without grounding: skip region creation; inventory only.
            continue
        bbox_t = tuple(float(x) for x in bbox)
        segments.append(
            VisualSegment(
                segment_id=new_segment_id(),
                observation_id=observation_id,
                media_id=media_id,
                frame_id=frame_id,
                label=str(concept.get("label") or "concept"),
                label_type=LABEL_TYPE_CONCEPT,
                confidence=float(concept.get("confidence") or 0.5),
                bbox=bbox_t,  # type: ignore[arg-type]
                mask_ref=concept.get("mask_ref"),
                parent_segment_id=concept.get("parent_segment_id"),
                source_provider=str(concept.get("source_provider") or provider),
                model_id=model_id,
                model_version=model_version,
                payload=dict(concept.get("payload") or {}),
            )
        )

    return apply_salience(segments, image_w=image_w, image_h=image_h, policy=policy)
