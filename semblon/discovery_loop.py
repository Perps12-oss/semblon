"""Semblon-native discovery loop helpers (Memory Canvas path).

Supports: media → region/observation → Similar → result set → continue.
Does not create persons, write face identity, or invent Related when only
Similar exists. Pure helpers — no Tk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SIMILAR_KIND = "similar"
# Related is not fabricated when the backend only supports Similar.
RELATED_KIND = "related"


def image_rect_from_corners(
    ix1: float, iy1: float, ix2: float, iy2: float, *, min_size: int = 2
) -> dict[str, int] | None:
    x1, x2 = sorted((float(ix1), float(ix2)))
    y1, y2 = sorted((float(iy1), float(iy2)))
    w = int(round(x2 - x1))
    h = int(round(y2 - y1))
    if w < min_size or h < min_size:
        return None
    return {"x": int(round(x1)), "y": int(round(y1)), "w": w, "h": h}


def image_rect_from_bbox(bbox: Any) -> dict[str, int] | None:
    if bbox is None:
        return None
    if isinstance(bbox, dict) and {"x", "y", "w", "h"} <= set(bbox):
        w, h = int(bbox["w"]), int(bbox["h"])
        if w < 2 or h < 2:
            return None
        return {
            "x": int(bbox["x"]),
            "y": int(bbox["y"]),
            "w": w,
            "h": h,
        }
    try:
        x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    return image_rect_from_corners(x1, y1, x2, y2)


def image_rect_from_selection(selected_hit: dict | None) -> dict[str, int] | None:
    """Image-space query rect from a Canvas selection (region / face / item / segment)."""
    if not selected_hit:
        return None
    direct = selected_hit.get("rect")
    if isinstance(direct, dict) and {"x", "y", "w", "h"} <= set(direct):
        return image_rect_from_bbox(direct)
    face = selected_hit.get("face") or {}
    if face:
        rect = image_rect_from_bbox(
            [
                face.get("bbox_x1"),
                face.get("bbox_y1"),
                face.get("bbox_x2"),
                face.get("bbox_y2"),
            ]
        )
        if rect:
            return rect
    item = selected_hit.get("item") or {}
    if item:
        rect = image_rect_from_bbox(
            [
                item.get("bbox_x1"),
                item.get("bbox_y1"),
                item.get("bbox_x2"),
                item.get("bbox_y2"),
            ]
        )
        if rect:
            return rect
    seg = selected_hit.get("segment")
    if seg is not None:
        bbox = seg.bbox if hasattr(seg, "bbox") else (seg.get("bbox") if isinstance(seg, dict) else None)
        rect = image_rect_from_bbox(bbox)
        if rect:
            return rect
    return None


def with_discovery_prompt(lines: list[str], *, has_query_rect: bool) -> list[str]:
    out = list(lines or [])
    while out and out[-1] == "":
        out.pop()
    out.append("")
    if has_query_rect:
        out.append("Find Similar looks for visually similar photos.")
        out.append("This is similarity — not identity.")
    else:
        out.append("Select a region or detail, then Find Similar to continue exploring.")
    return out


def result_set_lines(summary: dict | None) -> list[str]:
    summary = summary or {}
    status = str(summary.get("status") or "").upper()
    kind = str(summary.get("kind") or SIMILAR_KIND)
    label = "similar" if kind == SIMILAR_KIND else kind
    if status in {"UNAVAILABLE", "ERROR"}:
        return [
            summary.get("reason") or "Find Similar is not available yet.",
            "",
            "Your library stays open. Try another photo or finish understanding photos first.",
        ]
    items = list(summary.get("items") or [])
    if status == "NO_RESULT" or not items:
        return [
            summary.get("reason") or "No similar images found yet.",
            "",
            "Open another detail in this photo, or pick a different photo and try again.",
        ]
    n = len(items)
    return [
        f"{n} {label} result{'s' if n != 1 else ''}.",
        "",
        "Open a result to keep exploring — select a detail and Find Similar again.",
        "This is visual similarity, not a person identity.",
    ]


@dataclass
class DiscoveryFrame:
    filter_key: str = "all"
    similar_media_ids: list[str] | None = None
    query_media_id: str | None = None
    focus_media_id: str | None = None


@dataclass
class DiscoverySession:
    """Stack of Memory Canvas discovery states for Back / Clear."""

    stack: list[DiscoveryFrame] = field(default_factory=list)
    query_rect: dict[str, int] | None = None
    query_media_id: str | None = None

    def set_query(
        self, media_id: str | None, rect: dict[str, int] | None
    ) -> None:
        self.query_media_id = str(media_id) if media_id else None
        self.query_rect = dict(rect) if rect else None

    def clear_query(self) -> None:
        self.query_rect = None
        self.query_media_id = None

    def push(self, frame: DiscoveryFrame) -> None:
        self.stack.append(frame)

    def pop(self) -> DiscoveryFrame | None:
        if not self.stack:
            return None
        return self.stack.pop()

    def clear(self) -> None:
        self.stack.clear()
        self.clear_query()

    def has_history(self) -> bool:
        return bool(self.stack)
