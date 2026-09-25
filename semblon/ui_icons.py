"""Stroke icons in one family, drawn in a 24px viewBox.

Lucide's metaphors and 1.5px stroke, drawn with Tk lines because Tk does not
render SVG. One module, reused by nav and buttons. Not Unicode glyphs.
"""

from __future__ import annotations

from typing import Any

# Operations in a 24×24 box: line, stroked rounded-rect, oval, arc.
# ("L", [(x,y), ...]) ("R", x, y, w, h) ("O", x, y, w, h) ("A", x, y, w, h, start, extent)
ICONS: dict[str, tuple[tuple[Any, ...], ...]] = {
    "home": (
        ("L", ((3, 10), (12, 3), (21, 10))),
        ("L", ((6, 9), (6, 20), (10, 20), (10, 14), (14, 14), (14, 20), (18, 20), (18, 9))),
    ),
    "images": (
        ("R", 3, 3, 18, 18),
        ("O", 8, 7, 3.5, 3.5),
        ("L", ((6, 17), (10, 13), (13, 16), (16, 13), (20, 17))),
    ),
    "film": (
        ("R", 4, 4, 16, 16),
        ("L", ((8, 4), (8, 20))),
        ("L", ((16, 4), (16, 20))),
        ("L", ((4, 8), (8, 8))),
        ("L", ((4, 12), (8, 12))),
        ("L", ((4, 16), (8, 16))),
        ("L", ((16, 8), (20, 8))),
        ("L", ((16, 12), (20, 12))),
        ("L", ((16, 16), (20, 16))),
    ),
    "users": (
        ("O", 8, 4, 6, 6),
        ("A", 5, 12, 12, 10, 200, 140),
        ("O", 15, 6, 5, 5),
        ("A", 13, 13, 9, 8, 200, 140),
    ),
    "inbox": (
        ("R", 3, 5, 18, 14),
        ("L", ((3, 8), (12, 14), (21, 8))),
    ),
    "history": (
        ("O", 3, 3, 18, 18),
        ("L", ((12, 7), (12, 12), (16, 14))),
    ),
    "search": (
        ("O", 4, 4, 12, 12),
        ("L", ((14, 14), (20, 20))),
    ),
    "settings": (
        ("O", 9, 9, 6, 6),
        ("O", 3, 3, 18, 18),
    ),
    "plus": (
        ("L", ((12, 5), (12, 19))),
        ("L", ((5, 12), (19, 12))),
    ),
    "check": (("L", ((5, 12), (10, 17), (19, 7))),),
    "x": (
        ("L", ((6, 6), (18, 18))),
        ("L", ((18, 6), (6, 18))),
    ),
    "more-horizontal": (
        ("O", 3, 10, 4, 4),
        ("O", 10, 10, 4, 4),
        ("O", 17, 10, 4, 4),
    ),
    "pause": (
        ("R", 6, 5, 3.5, 14),
        ("R", 14.5, 5, 3.5, 14),
    ),
    "play": (("L", ((8, 5), (8, 19), (18, 12), (8, 5))),),
    "circle-alert": (
        ("O", 3, 3, 18, 18),
        ("L", ((12, 8), (12, 13))),
        ("O", 11, 16, 2, 2),
    ),
    "circle-check": (
        ("O", 3, 3, 18, 18),
        ("L", ((8, 12), (11, 15), (16, 9))),
    ),
    "folder-plus": (
        ("L", ((3, 7), (3, 19), (21, 19), (21, 7), (12, 7), (10, 4), (3, 4), (3, 7))),
        ("L", ((12, 11), (12, 16))),
        ("L", ((9.5, 13.5), (14.5, 13.5))),
    ),
    "shield": (
        ("L", ((12, 3), (20, 7), (20, 12), (12, 21), (4, 12), (4, 7), (12, 3))),
    ),
    "lens": (
        ("O", 3, 3, 18, 18),
        ("O", 9, 9, 6, 6),
    ),
}

NAV_ICONS = {
    "home": "home",
    "photos": "images",
    "videos": "film",
    "people": "users",
    "unknown": "inbox",
    "activity": "history",
    "canvas": "images",
    "lens": "lens",
}


def draw(
    canvas,
    name: str,
    x: float,
    y: float,
    size: float,
    color: str,
    *,
    tag: str = "icon",
) -> None:
    """Stroke ``name`` into ``canvas`` with its top-left at (x, y)."""
    spec = ICONS.get(name)
    if not spec or size <= 0:
        return
    scale = size / 24.0
    stroke = max(1, int(round(size / 16.0)))

    def pt(px: float, py: float) -> tuple[float, float]:
        return x + px * scale, y + py * scale

    for op in spec:
        kind = op[0]
        if kind == "L":
            pts: list[float] = []
            for px, py in op[1]:
                sx, sy = pt(px, py)
                pts.extend((sx, sy))
            if len(pts) >= 4:
                canvas.create_line(
                    *pts, fill=color, width=stroke, capstyle="round", joinstyle="round", tags=tag
                )
        elif kind == "O":
            x0, y0 = pt(op[1], op[2])
            x1, y1 = pt(op[1] + op[3], op[2] + op[4])
            canvas.create_oval(
                x0, y0, x1, y1, outline=color, width=stroke, tags=tag
            )
        elif kind == "R":
            x0, y0 = pt(op[1], op[2])
            x1, y1 = pt(op[1] + op[3], op[2] + op[4])
            canvas.create_rectangle(
                x0, y0, x1, y1, outline=color, width=stroke, tags=tag
            )
        elif kind == "A":
            x0, y0 = pt(op[1], op[2])
            x1, y1 = pt(op[1] + op[3], op[2] + op[4])
            canvas.create_arc(
                x0,
                y0,
                x1,
                y1,
                start=op[5],
                extent=op[6],
                style="arc",
                outline=color,
                width=stroke,
                tags=tag,
            )
