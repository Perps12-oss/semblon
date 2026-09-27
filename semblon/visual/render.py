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
