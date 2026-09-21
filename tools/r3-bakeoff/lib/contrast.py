"""WCAG 2.x relative luminance and contrast helpers (auto-measurable math only)."""

from __future__ import annotations

from typing import Sequence


def _channel(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def parse_hex(color: str) -> tuple[int, int, int]:
    s = color.strip().lstrip("#")
    if len(s) == 8:
        s = s[:6]  # drop alpha for contrast of opaque pair
    if len(s) != 6:
        raise ValueError(f"expected #RRGGBB, got {color!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def relative_luminance(rgb: Sequence[int]) -> float:
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1 = relative_luminance(parse_hex(fg))
    l2 = relative_luminance(parse_hex(bg))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def aa_pass(ratio: float, *, large_text: bool = False, ui_component: bool = False) -> bool:
    if ui_component or large_text:
        return ratio >= 3.0
    return ratio >= 4.5
