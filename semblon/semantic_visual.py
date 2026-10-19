"""SemanticVisualProvider — open-vocabulary visual understanding boundary.

Not an identity provider. FaceKit remains the only identity engine.
SAM2/SAM3/CLIP/VLM are optional backends behind this Protocol; the default
LocalSemanticVisualProvider works with OpenCV only and degrades gracefully.

Capabilities:
  discover_concepts(image)  — image-specific semantic inventory
  discover_regions(image)   — class-agnostic candidate regions
  segment_concept(...)      — ground one concept to a precise region
  refine_from_point(...)    — interactive unknown-region prompt
  refine_from_box(...)      — box-prompted refinement
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from semblon.visual_segment import (
    LABEL_TYPE_CONCEPT,
    LABEL_TYPE_REGION,
    LABEL_TYPE_UNKNOWN,
)


@dataclass(frozen=True)
class SemanticVisualInfo:
    name: str
    modality: str = "visual"
    device: str = "cpu"
    model_id: str = "local-opencv"
    model_version: str = "1"
    open_vocabulary: bool = True


@runtime_checkable
class SemanticVisualProvider(Protocol):
    """Non-identity visual understanding provider."""

    info: SemanticVisualInfo

    def discover_concepts(self, image: np.ndarray) -> list[dict]:
        """Image-specific candidate concepts (labels may include bbox when grounded)."""
        ...

    def discover_regions(self, image: np.ndarray) -> list[dict]:
        """Class-agnostic visual regions (bbox required; label optional/descriptive)."""
        ...

    def segment_concept(self, image: np.ndarray, concept: str) -> list[dict]:
        """Ground a named concept to one or more regions."""
        ...

    def refine_from_point(self, image: np.ndarray, x: int, y: int) -> dict | None:
        """Interactive segmentation from a click. None = unavailable."""
        ...

    def refine_from_box(
        self, image: np.ndarray, bbox: tuple[float, float, float, float]
    ) -> dict | None:
        """Interactive segmentation from a box. None = unavailable."""
        ...


# ---------------------------------------------------------------------------
# Appearance → natural-language naming (image-dependent, not a fixed detector)
# ---------------------------------------------------------------------------

_SKY_LIKE = ("sky", "bright open area")
_WATER_LIKE = ("water", "reflective surface", "pond")
_VEG_LIKE = ("vegetation", "grass", "foliage", "tree canopy")
_EARTH_LIKE = ("earth", "muddy bank", "ground", "path")
_SKIN_LIKE = ("skin tone", "face area")
_FABRIC_LIKE = ("fabric", "clothing", "robe")
_HARD_LIKE = ("hard surface", "structure", "object")
_DARK_LIKE = ("shadow", "dark region")


def _hsv_means(bgr: np.ndarray) -> tuple[float, float, float]:
    import cv2

    if bgr.size == 0:
        return 0.0, 0.0, 0.0
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    return float(h.mean()), float(s.mean()), float(v.mean())


def describe_region_appearance(
    crop: np.ndarray,
    *,
    cy_frac: float,
    area_frac: float,
    aspect: float,
) -> tuple[str, float]:
    """Map measured appearance to an image-specific label. Not a COCO class list."""
    h_m, s_m, v_m = _hsv_means(crop)
    # Hue bands roughly: 0–15 red/brown, 15–35 yellow/earth, 35–85 green,
    # 85–130 cyan/water, 130–170 blue/sky/water, rest magenta/red.
    candidates: list[tuple[str, float]] = []

    if v_m < 45 and s_m < 60:
        candidates.append((_DARK_LIKE[0], 0.55))
    if v_m > 190 and s_m < 50 and cy_frac < 0.45:
        candidates.append((_SKY_LIKE[0], 0.7))
    if 85 <= h_m <= 140 and s_m > 40 and v_m > 40:
        # Blue/cyan — water if lower half / mid, sky if upper.
        if cy_frac > 0.45:
            candidates.append((_WATER_LIKE[0], 0.65))
            if area_frac > 0.05:
                candidates.append((_WATER_LIKE[2], 0.55))
        else:
            candidates.append((_SKY_LIKE[0], 0.6))
    if 35 <= h_m <= 85 and s_m > 35:
        if area_frac > 0.12 and cy_frac < 0.55:
            candidates.append((_VEG_LIKE[3], 0.62))
        elif cy_frac > 0.55:
            candidates.append((_VEG_LIKE[1], 0.65))
        else:
            candidates.append((_VEG_LIKE[0], 0.55))
    # High green channel without strong HSV saturation still reads as foliage in BGR photos.
    mean_bgr = np.asarray(crop, dtype=np.float32).mean(axis=(0, 1)) if crop.size else np.zeros(3)
    if mean_bgr.size >= 3:
        bb, gg, rr = float(mean_bgr[0]), float(mean_bgr[1]), float(mean_bgr[2])
        if gg > rr + 25 and gg > bb + 15 and gg > 60:
            candidates.append((_VEG_LIKE[0], 0.58))
            if cy_frac > 0.55:
                candidates.append((_VEG_LIKE[1], 0.6))
        if bb > gg + 20 and bb > rr + 20 and cy_frac > 0.45:
            candidates.append((_WATER_LIKE[0], 0.5))
        if rr > gg + 30 and rr > bb + 20 and 40 < v_m < 200:
            if cy_frac < 0.55 and 0.6 < aspect < 1.7 and area_frac < 0.2:
                candidates.append((_SKIN_LIKE[0], 0.52))
            elif cy_frac > 0.45:
                candidates.append((_EARTH_LIKE[0], 0.5))
                candidates.append((_FABRIC_LIKE[1], 0.45))
    if (h_m < 25 or h_m > 160) and 40 < s_m < 160 and 40 < v_m < 180:
        # Warm browns / reds — earth, fabric, skin.
        if 0.55 < aspect < 1.8 and 0.01 < area_frac < 0.15 and cy_frac < 0.55:
            candidates.append((_SKIN_LIKE[0], 0.5))
        if cy_frac > 0.5 and area_frac > 0.04:
            candidates.append((_EARTH_LIKE[1] if v_m < 110 else _EARTH_LIKE[0], 0.58))
        if 0.4 < aspect < 2.5 and area_frac > 0.03:
            candidates.append((_FABRIC_LIKE[1], 0.45))
            if area_frac > 0.08 and v_m < 120:
                candidates.append((_FABRIC_LIKE[2], 0.42))
    if s_m < 35 and 60 < v_m < 180:
        candidates.append((_HARD_LIKE[0], 0.4))
    if aspect > 2.8 and area_frac < 0.08:
        candidates.append(("elongated object", 0.4))
    if aspect < 0.45 and area_frac < 0.1:
        candidates.append(("tall object", 0.4))

    if not candidates:
        # Fall back to tone words so every image still gets distinct inventory.
        tone = "bright" if v_m > 170 else ("dark" if v_m < 50 else "mid-tone")
        if s_m > 70:
            hue_name = (
                "warm"
                if h_m < 40 or h_m > 150
                else ("green" if h_m < 90 else ("cool" if h_m < 140 else "magenta"))
            )
            label = f"{tone} {hue_name} region"
        else:
            label = f"{tone} grey region"
        return label, 0.35

    candidates.sort(key=lambda t: -t[1])
    return candidates[0][0], float(candidates[0][1])


def _connected_regions(
    mask: np.ndarray, *, min_area: int, max_regions: int
) -> list[tuple[int, int, int, int, np.ndarray]]:
    import cv2

    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    scored = []
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        scored.append((area, x, y, w, h, (labels == i)))
    scored.sort(reverse=True)
    out = []
    for area, x, y, w, h, m in scored[:max_regions]:
        out.append((x, y, x + w, y + h, m))
    return out


class LocalSemanticVisualProvider:
    """Always-available OpenCV provider. Open-vocabulary via appearance grounding.

    Does not require SAM2/SAM3/CLIP/VLM. Optional backends can wrap or replace it.
    """

    info = SemanticVisualInfo(
        name="local_opencv",
        model_id="local-opencv",
        model_version="1",
    )

    def __init__(
        self,
        *,
        min_area_frac: float = 0.004,
        max_regions: int = 32,
        levels: int = 3,
    ):
        self.min_area_frac = min_area_frac
        self.max_regions = max_regions
        self.levels = levels
        self.last_optional_errors: list[str] = []

    def discover_regions(self, image: np.ndarray) -> list[dict]:
        import cv2

        arr = np.asarray(image)
        if arr.ndim != 3:
            return []
        h, w = arr.shape[:2]
        min_area = max(64, int(self.min_area_frac * w * h))
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        regions: list[dict] = []
        seen_boxes: list[tuple[float, float, float, float]] = []

        # Multi-threshold class-agnostic discovery (no class list required).
        for k in range(self.levels):
            blur = cv2.GaussianBlur(gray, (5 + 2 * k, 5 + 2 * k), 0)
            if k == 0:
                thr_img = cv2.threshold(
                    blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )[1]
            else:
                thr_img = cv2.adaptiveThreshold(
                    blur,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    11 + 10 * k,
                    2,
                )
            for inv in (thr_img, 255 - thr_img):
                for x1, y1, x2, y2, m in _connected_regions(
                    inv, min_area=min_area, max_regions=self.max_regions
                ):
                    if (x2 - x1) >= w * 0.98 and (y2 - y1) >= h * 0.98:
                        continue
                    box = (float(x1), float(y1), float(x2), float(y2))
                    if any(_iou(box, b) > 0.85 for b in seen_boxes):
                        continue
                    seen_boxes.append(box)
                    crop = arr[y1:y2, x1:x2]
                    bw, bh = max(1, x2 - x1), max(1, y2 - y1)
                    area_frac = (bw * bh) / float(w * h)
                    label, conf = describe_region_appearance(
                        crop,
                        cy_frac=((y1 + y2) / 2) / float(h),
                        area_frac=area_frac,
                        aspect=bw / float(bh),
                    )
                    mask_u8 = (m.astype(np.uint8) * 255) if m is not None else None
                    regions.append(
                        {
                            "bbox": box,
                            "label": label,
                            "label_type": LABEL_TYPE_REGION,
                            "confidence": conf,
                            "area_frac": area_frac,
                            "mask": mask_u8,
                            "source_provider": self.info.name,
                            "payload": {"discovery": "multithreshold"},
                        }
                    )
                    if len(regions) >= self.max_regions:
                        return regions
        return regions

    def discover_concepts(self, image: np.ndarray, *, regions: list[dict] | None = None) -> list[dict]:
        """Build an image-specific inventory from discovered regions + optional VLM/CLIP."""
        regions = list(regions) if regions is not None else self.discover_regions(image)
        # Collapse by label: inventory of unique concepts present in THIS image.
        by_label: dict[str, dict] = {}
        for reg in regions:
            key = str(reg["label"]).strip().lower()
            prev = by_label.get(key)
            if prev is None or float(reg["confidence"]) > float(prev["confidence"]):
                by_label[key] = {
                    "label": reg["label"],
                    "confidence": reg["confidence"],
                    "bbox": reg["bbox"],
                    "mask": reg.get("mask"),
                    "source_provider": self.info.name,
                    "label_type": LABEL_TYPE_CONCEPT,
                    "payload": {"inventory": "appearance"},
                }
        concepts = list(by_label.values())
        self.last_optional_errors = []

        # Optional CLIP open-vocab ranking (when installed + weights present).
        concepts.extend(_clip_image_concepts(image, existing={c["label"].lower() for c in concepts}))
        clip_error = clip_last_error()
        if clip_error:
            self.last_optional_errors.append(clip_error)

        # Optional VLM concepts (SEMBLON_VLM_MODEL); may lack bboxes.
        concepts.extend(_vlm_image_concepts(image, existing={c["label"].lower() for c in concepts}))
        return concepts

    def segment_concept(self, image: np.ndarray, concept: str) -> list[dict]:
        needle = concept.strip().lower()
        if not needle:
            return []
        hits = []
        for reg in self.discover_regions(image):
            if needle in str(reg["label"]).lower() or str(reg["label"]).lower() in needle:
                hits.append(reg)
        return hits

    def refine_from_point(self, image: np.ndarray, x: int, y: int) -> dict | None:
        import cv2

        arr = np.asarray(image)
        h, w = arr.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return None
        # Prefer SAM2 when configured; else flood-fill from the point.
        sam = _try_sam_point(arr, x, y)
        if sam is not None:
            return sam
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        seed_mask = np.zeros((h + 2, w + 2), np.uint8)
        fill = gray.copy()
        cv2.floodFill(
            fill,
            seed_mask,
            (int(x), int(y)),
            255,
            loDiff=12,
            upDiff=12,
            flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY,
        )
        region = seed_mask[1:-1, 1:-1]
        if int(region.sum()) < 64:
            return {
                "bbox": (float(max(0, x - 16)), float(max(0, y - 16)), float(min(w, x + 16)), float(min(h, y + 16))),
                "label": "unknown region",
                "label_type": LABEL_TYPE_UNKNOWN,
                "confidence": 0.3,
                "mask": None,
                "source_provider": self.info.name,
            }
        ys, xs = np.where(region > 0)
        x1, x2 = int(xs.min()), int(xs.max()) + 1
        y1, y2 = int(ys.min()), int(ys.max()) + 1
        crop = arr[y1:y2, x1:x2]
        label, conf = describe_region_appearance(
            crop,
            cy_frac=((y1 + y2) / 2) / float(h),
            area_frac=((x2 - x1) * (y2 - y1)) / float(w * h),
            aspect=(x2 - x1) / float(max(1, y2 - y1)),
        )
        return {
            "bbox": (float(x1), float(y1), float(x2), float(y2)),
            "label": label,
            "label_type": LABEL_TYPE_REGION,
            "confidence": conf,
            "mask": (region > 0).astype(np.uint8) * 255,
            "source_provider": self.info.name,
            "payload": {"refine": "floodfill"},
        }

    def refine_from_box(
        self, image: np.ndarray, bbox: tuple[float, float, float, float]
    ) -> dict | None:
        arr = np.asarray(image)
        h, w = arr.shape[:2]
        x1 = int(max(0, min(w - 1, bbox[0])))
        y1 = int(max(0, min(h - 1, bbox[1])))
        x2 = int(max(0, min(w, bbox[2])))
        y2 = int(max(0, min(h, bbox[3])))
        if x2 <= x1 or y2 <= y1:
            return None
        sam = _try_sam_box(arr, (x1, y1, x2, y2))
        if sam is not None:
            return sam
        crop = arr[y1:y2, x1:x2]
        label, conf = describe_region_appearance(
            crop,
            cy_frac=((y1 + y2) / 2) / float(h),
            area_frac=((x2 - x1) * (y2 - y1)) / float(w * h),
            aspect=(x2 - x1) / float(max(1, y2 - y1)),
        )
        mask = np.zeros((h, w), np.uint8)
        mask[y1:y2, x1:x2] = 255
        return {
            "bbox": (float(x1), float(y1), float(x2), float(y2)),
            "label": label,
            "label_type": LABEL_TYPE_REGION,
            "confidence": conf,
            "mask": mask,
            "source_provider": self.info.name,
            "payload": {"refine": "box"},
        }


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


# Broad open candidate bank for optional CLIP ranking. Per-image filtering makes
# the vocabulary image-dependent; it is NOT returned wholesale as detections.
_OPEN_CANDIDATE_BANK = (
    "person",
    "face",
    "hands",
    "hood",
    "robe",
    "clothing",
    "dog",
    "cat",
    "bird",
    "car",
    "bicycle",
    "road",
    "building",
    "tree",
    "grass",
    "flower",
    "pond",
    "water",
    "water reflection",
    "muddy bank",
    "sky",
    "cloud",
    "mountain",
    "forest",
    "desk",
    "laptop",
    "keyboard",
    "coffee cup",
    "notebook",
    "glasses",
    "plate",
    "food",
    "kitchen",
    "chair",
    "table",
    "window",
    "door",
    "sign",
    "screen",
    "text",
    "fence",
    "path",
    "bench",
    "ball",
    "collar",
    "reflection",
    "shadow",
    "product",
    "box",
    "bottle",
)


_CLIP_BUNDLE = None
_CLIP_LAST_ERROR: str | None = None


def clip_last_error() -> str | None:
    """Runtime failure from the last CLIP attempt. Import misses stay empty."""
    return _CLIP_LAST_ERROR


def _load_clip_bundle():
    """Process-local CLIP weights. Failures are not cached."""
    global _CLIP_BUNDLE
    if _CLIP_BUNDLE is not None:
        return _CLIP_BUNDLE
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    _CLIP_BUNDLE = (model, preprocess, tokenizer)
    return _CLIP_BUNDLE


def _clip_image_concepts(image: np.ndarray, *, existing: set[str]) -> list[dict]:
    """Optional CLIP zero-shot inventory. Missing CLIP → empty (not a crash)."""
    global _CLIP_LAST_ERROR
    _CLIP_LAST_ERROR = None
    try:
        import open_clip  # noqa: F401
        import torch
        from PIL import Image
    except Exception:
        return []
    try:
        from semblon.observers import probe_clip_status

        ready, _ = probe_clip_status()
        if not ready:
            return []
    except Exception:
        return []
    try:
        model, preprocess, tokenizer = _load_clip_bundle()
        arr = np.asarray(image)
        rgb = arr[:, :, ::-1].copy()
        with torch.no_grad():
            image_feat = model.encode_image(preprocess(Image.fromarray(rgb)).unsqueeze(0))
            image_feat = image_feat / image_feat.norm(dim=-1, keepdim=True)
            text = tokenizer(list(_OPEN_CANDIDATE_BANK))
            text_feat = model.encode_text(text)
            text_feat = text_feat / text_feat.norm(dim=-1, keepdim=True)
            sims = (image_feat @ text_feat.T).squeeze(0).cpu().numpy()
        out = []
        order = np.argsort(-sims)
        for idx in order[:12]:
            score = float(sims[idx])
            if score < 0.22:
                break
            label = _OPEN_CANDIDATE_BANK[int(idx)]
            if label.lower() in existing:
                continue
            out.append(
                {
                    "label": label,
                    "confidence": min(1.0, max(0.0, (score - 0.15) / 0.35)),
                    "bbox": None,  # needs grounding pass
                    "source_provider": "clip_openvocab",
                    "label_type": LABEL_TYPE_CONCEPT,
                    "payload": {"clip_score": score},
                }
            )
            existing.add(label.lower())
        return out
    except Exception as exc:
        # Not a concept label. Callers copy this into metrics, not the gallery.
        _CLIP_LAST_ERROR = f"clip: {type(exc).__name__}: {exc}"
        return []


def _vlm_image_concepts(image: np.ndarray, *, existing: set[str]) -> list[dict]:
    try:
        from semblon.lens import describe_vlm
    except Exception:
        return []
    try:
        result = describe_vlm(image)
    except Exception:
        return []
    if getattr(result, "status", None) != "SUCCESS":
        return []
    # describe_vlm returns summary as label; concepts live in generate payload only
    # for pixel-describer. Re-run describe_pixels path when available.
    try:
        from semblon.lens import describe_pixels, probe_vlm, _is_pixel_model
        from semblon.vlm_model import vlm_model_path
        from pathlib import Path

        if probe_vlm() != "AVAILABLE":
            return []
        located = vlm_model_path()
        if not located:
            return []
        path = Path(located)
        payload = describe_pixels(image) if _is_pixel_model(path) else None
        if not isinstance(payload, dict):
            return []
        out = []
        for concept in payload.get("concepts") or []:
            if not isinstance(concept, str) or not concept.strip():
                continue
            key = concept.strip().lower()
            if key in existing:
                continue
            out.append(
                {
                    "label": concept.strip(),
                    "confidence": 0.45,
                    "bbox": None,
                    "source_provider": "vlm",
                    "label_type": LABEL_TYPE_CONCEPT,
                    "payload": {"vlm": True},
                }
            )
            existing.add(key)
        return out
    except Exception:
        return []


def _try_sam_point(image: np.ndarray, x: int, y: int) -> dict | None:
    """SAM 2 point prompt when the shared runtime is READY. Else None."""
    from semblon.sam2_runtime import predict_point

    return predict_point(image, x, y)


def _try_sam_box(image: np.ndarray, bbox: tuple[int, int, int, int]) -> dict | None:
    from semblon.sam2_runtime import predict_box

    return predict_box(image, bbox)


def default_provider() -> LocalSemanticVisualProvider:
    return LocalSemanticVisualProvider()
