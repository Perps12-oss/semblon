"""User-selection geometry. The drawn box is authoritative.

Display/widget coordinates are temporary. Canonical storage is image-normalized
x1,y1,x2,y2 in [0,1]. A detector box is a different observation.
"""

from __future__ import annotations


def contain_rect(
    *,
    view_w: int,
    view_h: int,
    image_w: int,
    image_h: int,
) -> dict:
    """Letterboxed image rectangle inside the widget (contain / fit)."""
    if view_w <= 0 or view_h <= 0 or image_w <= 0 or image_h <= 0:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    scale = min(view_w / image_w, view_h / image_h)
    w = image_w * scale
    h = image_h * scale
    x = (view_w - w) / 2.0
    y = (view_h - h) / 2.0
    return {"x": x, "y": y, "w": w, "h": h}


def widget_to_image(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    view_w: int,
    view_h: int,
    image_w: int,
    image_h: int,
    letterbox: bool = True,
) -> dict | None:
    """Map a widget drag to integer image pixels. Zero-area is not a selection."""
    if view_w <= 0 or view_h <= 0 or image_w <= 0 or image_h <= 0:
        return None
    left, right = sorted((float(x0), float(x1)))
    top, bottom = sorted((float(y0), float(y1)))
    if right <= left or bottom <= top:
        return None
    if letterbox:
        box = contain_rect(view_w=view_w, view_h=view_h, image_w=image_w, image_h=image_h)
        if box["w"] <= 0 or box["h"] <= 0:
            return None
        ix = (left - box["x"]) * image_w / box["w"]
        iy = (top - box["y"]) * image_h / box["h"]
        ix2 = (right - box["x"]) * image_w / box["w"]
        iy2 = (bottom - box["y"]) * image_h / box["h"]
    else:
        ix = left * image_w / view_w
        iy = top * image_h / view_h
        ix2 = right * image_w / view_w
        iy2 = bottom * image_h / view_h
    px = int(round(max(0.0, min(float(image_w), ix))))
    py = int(round(max(0.0, min(float(image_h), iy))))
    px2 = int(round(max(0.0, min(float(image_w), ix2))))
    py2 = int(round(max(0.0, min(float(image_h), iy2))))
    if px2 <= px or py2 <= py:
        return None
    return {"x": px, "y": py, "w": px2 - px, "h": py2 - py}


def widget_point_to_image(
    x: float,
    y: float,
    *,
    ox: float,
    oy: float,
    scale: float,
    image_w: int,
    image_h: int,
) -> tuple[int, int] | None:
    """Map one widget/display point to source-image pixels (Canvas open-photo path).

    Uses the same ox/oy/scale convention as CanvasWorkspace (_ox, _oy, _scale).
    Returns None when the point falls outside the image.
    """
    if scale <= 0 or image_w <= 0 or image_h <= 0:
        return None
    ix = (float(x) - float(ox)) / float(scale)
    iy = (float(y) - float(oy)) / float(scale)
    if ix < 0 or iy < 0 or ix >= image_w or iy >= image_h:
        return None
    return int(ix), int(iy)


def normalize_pixels(x: int, y: int, w: int, h: int, image_w: int, image_h: int) -> dict:
    if image_w <= 0 or image_h <= 0 or w <= 0 or h <= 0:
        raise ValueError("region has no area")
    x1 = max(0.0, min(1.0, float(x) / float(image_w)))
    y1 = max(0.0, min(1.0, float(y) / float(image_h)))
    x2 = max(0.0, min(1.0, float(x + w) / float(image_w)))
    y2 = max(0.0, min(1.0, float(y + h) / float(image_h)))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("region has no area")
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def pixels_from_norm(norm: dict, image_w: int, image_h: int) -> dict:
    x = int(round(float(norm["x1"]) * image_w))
    y = int(round(float(norm["y1"]) * image_h))
    x2 = int(round(float(norm["x2"]) * image_w))
    y2 = int(round(float(norm["y2"]) * image_h))
    return {"x": x, "y": y, "w": max(0, x2 - x), "h": max(0, y2 - y)}


def same_norm(a: dict, b: dict, *, tol: float = 1e-6) -> bool:
    return all(abs(float(a[k]) - float(b[k])) <= tol for k in ("x1", "y1", "x2", "y2"))
