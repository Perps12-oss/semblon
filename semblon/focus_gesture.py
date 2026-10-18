"""Focus photo zoom and selection-edge math. Normalized search rects stay in image space."""

from __future__ import annotations

_LEFT = frozenset({"l", "tl", "bl"})
_RIGHT = frozenset({"r", "tr", "br"})
_TOP = frozenset({"t", "tl", "tr"})
_BOTTOM = frozenset({"b", "bl", "br"})


def clamp_view(
    x: float,
    y: float,
    scale: float,
    width: float,
    height: float,
    *,
    zoom_min: float = 1.0,
    zoom_max: float = 8.0,
) -> tuple[float, float, float]:
    """Keep a centre-scaled view covering its viewport. Scale 1 has no pan."""
    if width <= 0 or height <= 0:
        return (0.0, 0.0, 1.0)
    scale = max(zoom_min, min(zoom_max, float(scale)))
    if scale <= zoom_min + 1e-6:
        return (0.0, 0.0, zoom_min)
    max_x = width * (scale - 1.0) / 2.0
    max_y = height * (scale - 1.0) / 2.0
    return (
        max(-max_x, min(max_x, float(x))),
        max(-max_y, min(max_y, float(y))),
        scale,
    )


def zoom_about(
    x: float,
    y: float,
    scale: float,
    view_x: float,
    view_y: float,
    factor: float,
    width: float,
    height: float,
    *,
    zoom_min: float = 1.0,
    zoom_max: float = 8.0,
) -> tuple[float, float, float]:
    """Scale around the viewport point. Returns the view item's x, y, and scale."""
    scale = float(scale) if scale > 0 else zoom_min
    if factor <= 0 or width <= 0 or height <= 0:
        return clamp_view(x, y, scale, width, height, zoom_min=zoom_min, zoom_max=zoom_max)
    next_scale = max(zoom_min, min(zoom_max, scale * float(factor)))
    if abs(next_scale - scale) < 1e-6:
        return clamp_view(x, y, scale, width, height, zoom_min=zoom_min, zoom_max=zoom_max)
    center_x = float(x) + width / 2.0
    center_y = float(y) + height / 2.0
    local_x = width / 2.0 + (float(view_x) - center_x) / scale
    local_y = height / 2.0 + (float(view_y) - center_y) / scale
    new_center_x = float(view_x) - (local_x - width / 2.0) * next_scale
    new_center_y = float(view_y) - (local_y - height / 2.0) * next_scale
    return clamp_view(
        new_center_x - width / 2.0,
        new_center_y - height / 2.0,
        next_scale,
        width,
        height,
        zoom_min=zoom_min,
        zoom_max=zoom_max,
    )


def adjust_box(
    x: float,
    y: float,
    w: float,
    h: float,
    edge: str,
    dx: float,
    dy: float,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    min_size: float = 8.0,
) -> tuple[float, float, float, float]:
    """Move one edge or one corner of a rectangle. The opposite side stays put."""
    kind = str(edge)
    pull_l = kind in _LEFT
    pull_r = kind in _RIGHT
    pull_t = kind in _TOP
    pull_b = kind in _BOTTOM
    x1 = float(x) + float(dx) if pull_l else float(x)
    y1 = float(y) + float(dy) if pull_t else float(y)
    x2 = float(x) + float(w) + float(dx) if pull_r else float(x) + float(w)
    y2 = float(y) + float(h) + float(dy) if pull_b else float(y) + float(h)
    x1, x2 = _span(x1, x2, pull_l, pull_r, float(min_x), float(max_x), min_size)
    y1, y2 = _span(y1, y2, pull_t, pull_b, float(min_y), float(max_y), min_size)
    return (x1, y1, x2 - x1, y2 - y1)


def _span(
    start: float,
    end: float,
    pull_start: bool,
    pull_end: bool,
    lo: float,
    hi: float,
    min_size: float,
) -> tuple[float, float]:
    if end - start < min_size:
        if pull_start and not pull_end:
            start = end - min_size
        else:
            end = start + min_size
    if start < lo:
        start = lo
    if end > hi:
        end = hi
    if end - start < min_size:
        if pull_start and not pull_end:
            start = max(lo, end - min_size)
        else:
            end = min(hi, start + min_size)
        if end - start < min_size:
            start = lo
            end = min(hi, lo + min_size)
    if end < start:
        start, end = lo, min(hi, lo + min_size)
    return start, end
