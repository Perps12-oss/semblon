"""Highlight geometry for the production canvas. No discovery. No second GUI."""

from __future__ import annotations


def display_runs(
    rows: dict,
    *,
    scale: float,
    ox: float,
    oy: float,
    max_runs: int = 600,
) -> list[tuple[float, float, float, float]]:
    """Image row-runs → display rectangles. Cached by the caller per region id."""
    if not rows or scale <= 0:
        return []
    ordered: list[tuple[int, list]] = []
    for key, spans in rows.items():
        try:
            y = int(key)
        except (TypeError, ValueError):
            continue
        ordered.append((y, spans or []))
    ordered.sort()
    rects: list[tuple[float, float, float, float]] = []
    for y, spans in ordered:
        y1 = oy + y * scale
        y2 = y1 + max(scale, 1.0)
        for span in spans:
            if not span or len(span) < 2:
                continue
            x0, x1 = float(span[0]), float(span[1])
            rects.append((ox + x0 * scale, y1, ox + x1 * scale, y2))
            if len(rects) >= max_runs:
                return rects
    return rects


def mask_png(
    rows: dict,
    *,
    width: int,
    height: int,
    scale: float,
    color: tuple[int, int, int] = (40, 94, 202),
    alpha: int = 110,
) -> bytes:
    """One cached overlay for a region. Empty where the mask is not."""
    import io

    import numpy as np
    from PIL import Image

    if scale <= 0 or width <= 0 or height <= 0:
        scale = 1.0
    dw = max(1, int(round(width * scale)))
    dh = max(1, int(round(height * scale)))
    img = np.zeros((dh, dw, 4), dtype=np.uint8)
    for key, spans in (rows or {}).items():
        try:
            y = int(key)
        except (TypeError, ValueError):
            continue
        y1 = int(y * scale)
        y2 = min(dh, max(y1 + 1, int(round((y + 1) * scale))))
        if y1 >= dh or y2 <= y1:
            continue
        for span in spans or []:
            if not span or len(span) < 2:
                continue
            x0, x1 = int(span[0]), int(span[1])
            xa = int(x0 * scale)
            xb = min(dw, max(xa + 1, int(round(x1 * scale))))
            if xa >= dw or xb <= xa:
                continue
            img[y1:y2, xa:xb, 0] = color[0]
            img[y1:y2, xa:xb, 1] = color[1]
            img[y1:y2, xa:xb, 2] = color[2]
            img[y1:y2, xa:xb, 3] = alpha
    buf = io.BytesIO()
    Image.fromarray(img, "RGBA").save(buf, format="PNG")
    return buf.getvalue()