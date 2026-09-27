"""Slow path: discover → lattice → name → slice → primary-owner map.

Nothing in this module runs from a pointer event. Callers pass an image.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from semblon.visual.discovery import ClassicalColorDiscovery, Sam2AmgDiscovery, sam2_capability
from semblon.visual.masks import (
    MaskCand,
    area_of,
    bbox_of,
    box_iou,
    connected_labels,
    containment,
    containment_keep,
    iou,
    rows_from_mask,
)
from semblon.visual.model import PAINT_ORDER, VisualConfig, VisualRegion
from semblon.visual.naming import bind_label, split_proposals


def capabilities() -> dict:
    sam2 = sam2_capability()
    return {
        "visual.discovery": {"state": "PARTIAL", "note": "classical colour regions run locally"},
        "visual.discovery.sam2": sam2,
        "visual.naming": {"state": "PARTIAL", "note": "bind/abstain ready; no embedder loaded"},
        "visual.naming.siglip": {"state": "UNAVAILABLE", "note": "no local SigLIP weights"},
        "visual.naming.vlm": {"state": "UNAVAILABLE", "note": "no local VLM"},
        "visual.ocr": {"state": "UNAVAILABLE", "note": "use the existing text observer when present"},
        "visual.stuff": {"state": "PARTIAL", "note": "large residual areas stay unnamed unless a verifier binds them"},
        "visual.hover": {"state": "READY", "note": "lookup only"},
        "visual.user_region": {"state": "READY", "note": "user masks enter the same pipeline"},
    }


@dataclass
class Analysis:
    revision: str
    width: int
    height: int
    regions: list[VisualRegion]
    owner: np.ndarray
    rows: dict[int, dict]
    edges: list[tuple[int, int, str, float]]
    diagnostics: dict
    level: int
    config: VisualConfig = field(default_factory=VisualConfig)

    def region(self, region_id: int) -> VisualRegion | None:
        for region in self.regions:
            if region.region_id == region_id:
                return region
        return None


def analyse(
    rgb: np.ndarray,
    *,
    config: VisualConfig | None = None,
    nouns: list[str] | None = None,
    score_fn=None,
    view_w: int | None = None,
    view_h: int | None = None,
    user_masks: list[np.ndarray] | None = None,
    user_regions: list[dict] | None = None,
    face_boxes: list[tuple[int, int, int, int]] | None = None,
    revision: str = "visual-1",
    cancel=None,
) -> Analysis:
    """Full slow path. `cancel()` true aborts between stages. Never a pointer hook."""
    cfg = config or VisualConfig()
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError("rgb must be HxWx3")
    rgb = np.ascontiguousarray(rgb[:, :, :3])
    h, w = int(rgb.shape[0]), int(rgb.shape[1])
    view_w = view_w or w
    view_h = view_h or h
    diag: dict = {"stages": {}, "removed": [], "timings_ms": {}}
    t0 = time.perf_counter()

    def _stop() -> bool:
        return bool(cancel and cancel())

    def _mark(stage: str, started: float) -> None:
        diag["timings_ms"][stage] = round((time.perf_counter() - started) * 1000.0, 3)

    if _stop():
        return _empty(w, h, revision, cfg, diag, "cancelled")

    started = time.perf_counter()
    raw = ClassicalColorDiscovery().discover(rgb, cfg)
    diag["stages"]["classical"] = len(raw)
    sam2_cap = sam2_capability()
    diag["sam2"] = {"state": sam2_cap["state"], "proposed": None, "note": sam2_cap["note"], "error": None}
    if sam2_cap["state"] == "READY":
        sam2_masks, err = Sam2AmgDiscovery().discover(rgb, cfg)
        diag["sam2"]["proposed"] = len(sam2_masks)
        diag["sam2"]["error"] = err
        if err:
            diag["sam2"]["state"] = "FAILED"
        raw.extend(sam2_masks)
    _mark("discovery", started)
    diag["stages"]["raw"] = len(raw)
    if _stop():
        return _empty(w, h, revision, cfg, diag, "cancelled")

    for spec in user_regions or []:
        mask = np.asarray(spec.get("mask"), dtype=bool)
        if mask.shape == (h, w) and mask.any():
            cand = MaskCand(mask, "user", "user", 1.0, 1.0, "raw")
            cand.user_label = spec.get("label")
            raw.append(cand)
    for mask in user_masks or []:
        m = np.asarray(mask, dtype=bool)
        if m.shape == (h, w) and m.any():
            raw.append(MaskCand(m, "user", "user", 1.0, 1.0, "raw"))
    for box in face_boxes or []:
        m = _box_mask(h, w, box)
        if m.any():
            raw.append(MaskCand(m, "face", "face_projection", 1.0, 1.0, "raw"))

    started = time.perf_counter()
    quality: list[MaskCand] = []
    min_area = max(1, int(cfg.min_area_frac * h * w))
    for cand in raw:
        area = area_of(cand.mask)
        if area < min_area or cand.stability < 0:
            cand.fate = "quality_removed"
            diag["removed"].append({"stage": "quality", "area": area, "method": cand.method})
            continue
        quality.append(cand)
    diag["stages"]["quality"] = len(quality)
    _mark("quality", started)
    if _stop():
        return _empty(w, h, revision, cfg, diag, "cancelled")

    started = time.perf_counter()
    kept, notes = _dedupe(quality, cfg)
    survivors = []
    for i, cand in enumerate(quality):
        cand.fate = notes[i]
        if i in kept:
            survivors.append(cand)
        else:
            diag["removed"].append({"stage": "dedupe", "fate": notes[i], "method": cand.method})
    diag["stages"]["deduped"] = len(survivors)
    diag["dedupe"] = cfg.dedupe
    _mark("dedupe", started)

    started = time.perf_counter()
    regions, masks, edges = _lattice(survivors, cfg, revision, h, w)
    diag["stages"]["lattice"] = len(regions)
    diag["edges"] = len(edges)
    _mark("lattice", started)
    if _stop():
        return _empty(w, h, revision, cfg, diag, "cancelled")

    started = time.perf_counter()
    if nouns and score_fn is not None:
        by_id = {region.region_id: region for region in regions}
        for region in _parents_first(regions, by_id):
            parent = by_id.get(region.parent_id) if region.parent_id else None
            bind_label(region, nouns, score_fn, parent=parent, config=cfg)
    else:
        for region in regions:
            region.label = None
            if region.fate not in {"user_named", "user_proper_held"}:
                region.fate = "unnamed"
    _apply_user_labels(regions)
    _attach_context(regions, edges)
    diag["stages"]["named"] = sum(1 for region in regions if region.label)
    diag["stages"]["abstained"] = sum(1 for region in regions if region.label is None)
    _mark("naming", started)

    started = time.perf_counter()
    sliced = _slice(regions, cfg, image_w=w, image_h=h, view_w=view_w, view_h=view_h)
    sliced_ids = {region.region_id for region in sliced}
    for region in regions:
        if region.region_id not in sliced_ids and region.fate not in {"quality_removed", "dedupe_removed"}:
            region.fate = "slice_removed"
            diag["removed"].append(
                {
                    "stage": "slice",
                    "region_id": region.region_id,
                    "kind": region.kind,
                    "label": region.label,
                }
            )
    diag["stages"]["sliced"] = len(sliced)
    _mark("slice", started)

    started = time.perf_counter()
    owner = _paint(h, w, sliced, {region.region_id: masks[region.region_id] for region in sliced})
    rows = {region.region_id: rows_from_mask(masks[region.region_id]) for region in sliced}
    _mark("paint", started)
    for region in sliced:
        if region.fate in {"user_named", "user_proper_held"}:
            continue
        region.fate = "hover_named" if region.label else "hover_unnamed"
        region.level = 3 if region.label else 2
    level = _level(sliced, edges)
    diag["level"] = level
    diag["owner_bytes"] = int(owner.nbytes)
    diag["timings_ms"]["total"] = round((time.perf_counter() - t0) * 1000.0, 3)
    diag["capabilities"] = capabilities()
    slice_ids = {region.region_id for region in sliced}
    return Analysis(
        revision=revision,
        width=w,
        height=h,
        regions=sliced,
        owner=owner,
        rows=rows,
        edges=[edge for edge in edges if edge[0] in slice_ids and edge[1] in slice_ids],
        diagnostics=diag,
        level=level,
        config=cfg,
    )


def _parents_first(regions: list[VisualRegion], by_id: dict[int, VisualRegion]) -> list[VisualRegion]:
    def depth(region: VisualRegion, seen: set[int] | None = None) -> int:
        seen = set() if seen is None else seen
        if region.parent_id is None or region.region_id in seen:
            return 0
        parent = by_id.get(region.parent_id)
        if parent is None:
            return 0
        seen.add(region.region_id)
        return 1 + depth(parent, seen)

    return sorted(regions, key=depth)


def _level(regions: list[VisualRegion], edges: list) -> int:
    if not regions:
        return 1
    named = any(region.label for region in regions)
    if edges and named:
        return 4
    if named:
        return 3
    if edges:
        return 2
    return 2


def _empty(w, h, revision, cfg, diag, why) -> Analysis:
    diag["cancelled"] = why
    diag["level"] = 0
    return Analysis(revision, w, h, [], np.zeros((h, w), dtype=np.uint16), {}, [], diag, 0, cfg)


def _box_mask(h: int, w: int, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, bw, bh = box
    mask = np.zeros((h, w), dtype=bool)
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(w, int(x) + int(bw)), min(h, int(y) + int(bh))
    if x1 > x0 and y1 > y0:
        mask[y0:y1, x0:x1] = True
    return mask


def _apply_user_labels(regions: list[VisualRegion]) -> None:
    """A human label is not a model guess. A proper name still is not a person."""
    for region in regions:
        if region.method != "user" or not region.user_label:
            continue
        concepts, proper = split_proposals([region.user_label])
        region.proper_name_proposals = list(dict.fromkeys([*region.proper_name_proposals, *proper]))
        if concepts:
            region.label = concepts[0]
            region.confidence = 1.0
            region.fate = "user_named"
            region.level = max(region.level, 3)
        elif proper:
            region.label = None
            region.fate = "user_proper_held"


def _attach_context(regions: list[VisualRegion], edges: list[tuple[int, int, str, float]]) -> None:
    by_id = {region.region_id: region for region in regions}
    related: dict[int, list[str]] = {region.region_id: [] for region in regions}
    for src, dst, kind, _weight in edges:
        if kind not in {"contains", "overlaps"}:
            continue
        for left, right in ((src, dst), (dst, src)):
            other = by_id.get(right)
            if other is None or not other.label or other.label in related[left]:
                continue
            related[left].append(other.label)
    for region in regions:
        parent = by_id.get(region.parent_id) if region.parent_id else None
        region.parent_label = parent.label if parent is not None else None
        region.related_labels = related[region.region_id][:4]


def _dedupe(cands: list[MaskCand], cfg: VisualConfig) -> tuple[set[int], list[str]]:
    masks = [cand.mask for cand in cands]
    scores = [
        cand.stability * 0.5 + cand.pred_iou * 0.5 + (0.05 if cand.method == "user" else 0.0)
        for cand in cands
    ]
    if cfg.dedupe == "nms":
        boxes = [bbox_of(mask) for mask in masks]
        notes = ["nms_removed"] * len(cands)
        order = sorted(range(len(cands)), key=lambda i: scores[i], reverse=True)
        keep: list[int] = []
        for i in order:
            if any(box_iou(boxes[i], boxes[j]) >= cfg.nms_iou for j in keep):
                continue
            keep.append(i)
            notes[i] = "nms_kept"
        return set(keep), notes
    keep, notes = containment_keep(
        masks,
        scores,
        contain_ratio=cfg.contain_ratio,
        overlap_iou=max(cfg.overlap_iou, 0.55),
    )
    return set(keep), notes


def _lattice(cands: list[MaskCand], cfg: VisualConfig, revision: str, h: int, w: int):
    regions: list[VisualRegion] = []
    masks: dict[int, np.ndarray] = {}
    for i, cand in enumerate(cands, start=1):
        box = bbox_of(cand.mask)
        area = area_of(cand.mask)
        regions.append(
            VisualRegion(
                region_id=i,
                bbox=box,
                area=area,
                kind=_kind_guess(cand, area, box),
                provider=cand.provider,
                method=cand.method,
                stability=cand.stability,
                pred_iou=cand.pred_iou,
                fate=cand.fate,
                analysis_revision=revision,
                level=2,
                user_label=cand.user_label,
            )
        )
        masks[i] = cand.mask
    edges: list[tuple[int, int, str, float]] = []
    for region in regions:
        best_parent = None
        best_frac = 0.0
        best_area = 10**18
        for other in regions:
            if region.region_id == other.region_id or other.area <= region.area:
                continue
            frac = containment(masks[other.region_id], masks[region.region_id])
            if frac >= cfg.contain_ratio and other.area < best_area:
                best_parent = other.region_id
                best_frac = frac
                best_area = other.area
        if best_parent is not None:
            region.parent_id = best_parent
            if region.kind in {"thing", "unknown"} and region.method != "face_projection":
                region.kind = "part"
            edges.append((best_parent, region.region_id, "contains", best_frac))
            region.level = 4
    for i, region in enumerate(regions):
        for other in regions[i + 1 :]:
            if region.parent_id == other.region_id or other.parent_id == region.region_id:
                continue
            overlap = iou(masks[region.region_id], masks[other.region_id])
            if overlap >= cfg.overlap_iou:
                edges.append((region.region_id, other.region_id, "overlaps", overlap))
    _reclass_stuff(regions, h, w, cfg)
    _residual_stuff(regions, masks, h, w, cfg, revision)
    return regions, masks, edges


def _kind_guess(cand: MaskCand, area: int, box: tuple[int, int, int, int]) -> str:
    if cand.method == "face_projection":
        return "face"
    if cand.method == "user":
        return "thing"
    return "thing"


def _reclass_stuff(regions: list[VisualRegion], h: int, w: int, cfg: VisualConfig) -> None:
    """Large uncontained colour fields are stuff. The colour is not a name."""
    image_area = max(1, h * w)
    for region in regions:
        if region.method != "color" or region.parent_id is not None:
            continue
        if region.area >= cfg.stuff_area_frac * image_area:
            region.kind = "stuff"


def _residual_stuff(regions, masks, h: int, w: int, cfg: VisualConfig, revision: str) -> None:
    """Pixels nobody claimed, if they form a coherent area. Unnamed."""
    if not regions:
        return
    covered = np.zeros((h, w), dtype=bool)
    for region in regions:
        covered |= masks[region.region_id]
    if int((~covered).sum()) < max(1, int(cfg.min_area_frac * h * w)):
        return
    scale = 96 / max(h, w)
    if scale < 1:
        sh, sw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
        ys = np.linspace(0, h - 1, sh).astype(np.int32)
        xs = np.linspace(0, w - 1, sw).astype(np.int32)
        small = ~covered[ys][:, xs]
    else:
        small = ~covered
        sh, sw = h, w
    comp = connected_labels(small)
    y_map = np.linspace(0, sh - 1, h).astype(np.int32)
    x_map = np.linspace(0, sw - 1, w).astype(np.int32)
    next_id = max(region.region_id for region in regions) + 1
    min_area = max(1, int(cfg.stuff_area_frac * h * w))
    for lid in np.unique(comp):
        if lid == 0:
            continue
        piece = comp == lid
        if int(piece.sum()) < 8:
            continue
        full = piece[y_map][:, x_map] & ~covered
        area = area_of(full)
        if area < min_area:
            continue
        regions.append(
            VisualRegion(
                region_id=next_id,
                bbox=bbox_of(full),
                area=area,
                kind="stuff",
                provider="classical",
                method="residual",
                fate="residual",
                analysis_revision=revision,
                level=2,
            )
        )
        masks[next_id] = full
        next_id += 1


def _slice(regions, cfg: VisualConfig, *, image_w, image_h, view_w, view_h) -> list[VisualRegion]:
    sx = view_w / max(1, image_w)
    sy = view_h / max(1, image_h)
    by_id = {region.region_id: region for region in regions}
    kept: list[VisualRegion] = []
    for region in regions:
        if region.fate == "abstained_material":
            continue
        display_area = region.area * sx * sy
        if display_area < cfg.display_min_px:
            continue
        parent = by_id.get(region.parent_id) if region.parent_id else None
        if parent is not None and parent.area > 0:
            ratio = region.area / parent.area
            distinctive = bool(region.label) and region.label != parent.label and region.label not in {"fabric", "skin"}
            if ratio > cfg.redundant_child_ratio and not distinctive:
                continue
        kept.append(region)
    if len(kept) > cfg.max_hover_regions:
        priority = [
            region
            for region in kept
            if region.kind in {"part", "face", "text", "mark"} or region.method == "user"
        ]
        rest = [region for region in kept if region not in priority]
        rest.sort(key=lambda region: region.area, reverse=True)
        if len(priority) > cfg.max_hover_regions:
            priority.sort(key=lambda region: region.area, reverse=True)
            kept = priority[: cfg.max_hover_regions]
        else:
            room = cfg.max_hover_regions - len(priority)
            kept = priority + rest[:room]
    return kept


def _paint(h: int, w: int, regions: list[VisualRegion], masks: dict[int, np.ndarray]) -> np.ndarray:
    owner = np.zeros((h, w), dtype=np.uint16)
    rank = {kind: index for index, kind in enumerate(PAINT_ORDER)}
    for region in sorted(regions, key=lambda item: rank.get(item.kind, 0)):
        if region.region_id > 65535:
            continue
        owner[masks[region.region_id]] = np.uint16(region.region_id)
    return owner
