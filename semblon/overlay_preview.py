"""Gate-aware preview helpers for the live/canvas overlay scaffold.

When ``live_overlay`` is OFF:
- ``apply_overlay_styles`` / ``apply_to_canvas`` no-op (safe for future canvas calls).
- Explicit enable paths use ``require_enabled`` and raise.

Does not write ``person_id`` or invent identity conclusions.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from semblon import gates
from semblon.overlay_scaffold import box_style, normalize_display_state

GATE_KEY = "live_overlay"


def render_overlay_enabled() -> bool:
    """True only when ``SEMBLON_GATE_LIVE_OVERLAY`` enables the gate."""
    return gates.is_enabled(GATE_KEY)


def apply_overlay_styles(
    boxes: Sequence[Mapping[str, Any]],
    styles: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Attach draw styles to observation boxes.

    No-op when the gate is OFF: returns shallow copies of ``boxes`` unchanged
    (no ``overlay_style`` key added). When ON, merges ``styles[box_id]`` or
    derives ``box_style(display_state)`` from each box's ``display_state``.
    """
    if not render_overlay_enabled():
        return [dict(b) for b in boxes]

    out: list[dict[str, Any]] = []
    style_map = styles or {}
    for box in boxes:
        item = dict(box)
        box_id = str(item.get("id") or "")
        if box_id and box_id in style_map:
            item["overlay_style"] = dict(style_map[box_id])
        else:
            state = item.get("display_state") or "unknown"
            item["overlay_style"] = box_style(normalize_display_state(str(state)))
        # Firewall: never smuggle a person assignment through paint.
        item.pop("person_id_assign", None)
        out.append(item)
    return out


def apply_to_canvas(
    boxes: Sequence[Mapping[str, Any]],
    styles: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Canvas-callable wire helper. No-op when gate OFF (same as apply_overlay_styles)."""
    return apply_overlay_styles(boxes, styles)


def require_overlay_enabled() -> None:
    """Explicit enable path — raises while the gate is OFF."""
    gates.require_enabled(GATE_KEY)


def build_styled_boxes(
    boxes: Sequence[Mapping[str, Any]],
    styles: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Explicit enable path: require gate, then apply styles."""
    require_overlay_enabled()
    return apply_overlay_styles(boxes, styles)
