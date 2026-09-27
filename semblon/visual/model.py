"""Visual region contract. Not a person, track, or entity."""

from __future__ import annotations

from dataclasses import dataclass, field


KINDS = ("part", "thing", "stuff", "face", "text", "mark", "unknown")
EDGE_TYPES = ("contains", "overlaps")
# Paint order: later kinds overwrite earlier ones. Finest wins.
PAINT_ORDER = ("stuff", "thing", "unknown", "part", "face", "text", "mark")

# Hint list only. Not the universe of names.
HINTS = frozenset(
    {
        "person", "face", "hand", "hood", "jacket", "clothing", "grass", "water",
        "sky", "tree", "boat", "car", "road", "sand", "snow", "sign", "text",
        "animal", "dog", "building", "window",
    }
)
MATERIALS = frozenset({"fabric", "textile", "skin", "metal", "cloth", "material"})


@dataclass
class VisualConfig:
    """Measurable knobs. Not architectural constants."""

    min_area_frac: float = 0.004
    contain_ratio: float = 0.85
    overlap_iou: float = 0.2
    nms_iou: float = 0.7
    dedupe: str = "containment"  # containment | nms
    display_min_px: int = 400
    redundant_child_ratio: float = 0.85
    name_abs: float = 0.28
    name_margin: float = 0.06
    max_hover_regions: int = 48
    stuff_area_frac: float = 0.12


@dataclass
class VisualRegion:
    region_id: int
    bbox: tuple[int, int, int, int]  # x, y, w, h
    area: int
    kind: str = "unknown"
    label: str | None = None
    label_candidates: list[tuple[str, float]] = field(default_factory=list)
    confidence: float | None = None
    parent_id: int | None = None
    parent_label: str | None = None
    related_labels: list[str] = field(default_factory=list)
    user_label: str | None = None
    provider: str = "classical"
    method: str = "color"
    stability: float = 1.0
    pred_iou: float = 1.0
    level: int = 2
    fate: str = "raw"
    proper_name_proposals: list[str] = field(default_factory=list)
    analysis_revision: str = ""

    def to_payload(self) -> dict:
        x, y, w, h = self.bbox
        return {
            "class": "visual_region",
            "identity": "not facekit",
            "region_id": self.region_id,
            "analysis_revision": self.analysis_revision,
            "kind": self.kind,
            "selected_label": self.label,
            "label_candidates": [
                {"text": t, "score": s} for t, s in self.label_candidates
            ],
            "confidence": self.confidence,
            "parent_id": self.parent_id,
            "parent_label": self.parent_label,
            "related_labels": list(self.related_labels),
            "user_label": self.user_label,
            "area": self.area,
            "stability": self.stability,
            "pred_iou": self.pred_iou,
            "level": self.level,
            "fate": self.fate,
            "provider": self.provider,
            "method": self.method,
            "proper_name_proposals": list(self.proper_name_proposals),
            "pixels": {"x": x, "y": y, "w": w, "h": h},
            "readiness": f"L{self.level}",
        }
