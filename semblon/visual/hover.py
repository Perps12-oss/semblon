"""Pointer path. Lookup only."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from semblon.geometry import contain_rect
from semblon.visual.model import VisualRegion


@dataclass
class PointerHit:
    region_id: int
    region: VisualRegion | None
    changed: bool
    label: str | None


class HoverIndex:
    """Resident map + table. Construct after analysis. Never discovers."""

    def __init__(self, owner: np.ndarray, regions: list[VisualRegion]):
        self.owner = owner
        self.regions = {r.region_id: r for r in regions}
        self.previous: int | None = None
        self.lookups = 0
        self.transitions = 0
        self.suppressed = 0

    def lookup(self, x: int, y: int) -> int:
        self.lookups += 1
        h, w = self.owner.shape
        if x < 0 or y < 0 or x >= w or y >= h:
            return 0
        return int(self.owner[y, x])

    def pointer(self, x: int, y: int) -> PointerHit:
        rid = self.lookup(x, y)
        changed = rid != self.previous
        if changed:
            self.transitions += 1
            self.previous = rid
        else:
            self.suppressed += 1
        region = self.regions.get(rid)
        return PointerHit(
            region_id=rid,
            region=region,
            changed=changed,
            label=None if region is None else region.label,
        )


def widget_point_to_native(
    wx: float,
    wy: float,
    *,
    view_w: int,
    view_h: int,
    image_w: int,
    image_h: int,
    zoom: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    dpi_scale: float = 1.0,
) -> tuple[int, int] | None:
    """Screen/widget point → native pixel. Letterbox miss is None.

    dpi_scale converts device pixels to logical widget pixels.
    Zoom is about the contain-rect centre. Pan is logical widget pixels.
    EXIF orientation must already match the buffer this indexes.
    """
    if dpi_scale <= 0 or zoom <= 0:
        return None
    lx = wx / dpi_scale
    ly = wy / dpi_scale
    box = contain_rect(view_w=view_w, view_h=view_h, image_w=image_w, image_h=image_h)
    if box["w"] <= 0 or box["h"] <= 0:
        return None
    cx = box["x"] + box["w"] / 2.0
    cy = box["y"] + box["h"] / 2.0
    dw, dh = box["w"] * zoom, box["h"] * zoom
    dx = cx - dw / 2.0 + pan_x
    dy = cy - dh / 2.0 + pan_y
    if lx < dx or ly < dy or lx >= dx + dw or ly >= dy + dh:
        return None
    ix = int((lx - dx) * image_w / dw)
    iy = int((ly - dy) * image_h / dh)
    if ix < 0 or iy < 0 or ix >= image_w or iy >= image_h:
        return None
    return ix, iy


def display_to_image(x: float, y: float, *, ox: float, oy: float, scale: float) -> tuple[float, float]:
    """Canvas point → image pixel, using the same origin the photograph was drawn at."""
    if scale == 0:
        return 0.0, 0.0
    return (x - ox) / scale, (y - oy) / scale


def buffer_pixel(x: int, y: int, width: int, height: int, orientation: int) -> tuple[int, int]:
    """Displayed pixel → unrotated decoder buffer.

    Production Home shows the OpenCV buffer and builds the hover map on that
    same buffer, so orientation 1 is the live path. Orientations 2–8 exist so
    a later decode that applies EXIF cannot drift from the map.
    """
    if orientation == 2:
        return width - 1 - x, y
    if orientation == 3:
        return width - 1 - x, height - 1 - y
    if orientation == 4:
        return x, height - 1 - y
    if orientation == 5:
        return y, x
    if orientation == 6:
        return y, height - 1 - x
    if orientation == 7:
        return width - 1 - y, height - 1 - x
    if orientation == 8:
        return width - 1 - y, x
    return x, y
