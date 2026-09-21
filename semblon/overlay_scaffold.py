"""R3 three-layer media-adaptive overlay scaffold (draw instructions only).

Gate: ``live_overlay`` / ``SEMBLON_GATE_LIVE_OVERLAY`` (wiring is separate).

Visual grammar from ``docs/R3-BRIEF.md`` §1. Display states are human-facing
labels over evidence × decision — **not** identity conclusions.

Identity firewall:
- Never writes ``person_id``.
- Never treats cluster as person.
- Does not invent ACCEPT / named-person claims from overlay paint alone.
"""

from __future__ import annotations

from typing import Any, Mapping

# Five display states (R3 matrix). Adjectival labels only.
DISPLAY_STATES: tuple[str, ...] = (
    "unknown",
    "possible",
    "confirmed",
    "ruled_out",
    "ignored",
)

# Semantic stroke colors reinforce state; notch + texture are load-bearing.
_SEMANTIC_COLOR: Mapping[str, str] = {
    "unknown": "#9AA0A6",
    "possible": "#C4A35A",
    "confirmed": "#5B8C5A",
    "ruled_out": "#A65D57",
    "ignored": "#6B6B6B",
}

_LAYER_WIDTH_PX = 1.5
_IGNORED_OPACITY = 0.35

# Border texture (R3 §1 visual grammar).
_BORDER: Mapping[str, Mapping[str, Any]] = {
    "unknown": {
        "style": "dashed",
        "dash": (6, 4),
        "mark": None,
        "visible": True,
    },
    "possible": {
        "style": "dashed",
        "dash": (3, 2),
        "mark": None,
        "visible": True,
    },
    "confirmed": {
        "style": "solid",
        "dash": None,
        "mark": None,
        "visible": True,
    },
    "ruled_out": {
        "style": "dashed",
        "dash": (6, 4),
        "mark": "≠",
        "visible": True,
    },
    "ignored": {
        "style": "none",
        "dash": None,
        "mark": None,
        "visible": False,
    },
}

# Notch is the primary carrier (texture + mark).
_NOTCH: Mapping[str, Mapping[str, Any]] = {
    "unknown": {
        "fill": "empty_outline",
        "mark": None,
        "visible": True,
    },
    "possible": {
        "fill": "half_filled",
        "mark": None,
        "visible": True,
    },
    "confirmed": {
        "fill": "solid",
        "mark": None,
        "visible": True,
    },
    "ruled_out": {
        "fill": "empty_outline",
        "mark": "slash",
        "visible": True,
    },
    "ignored": {
        "fill": "none",
        "mark": None,
        "visible": False,
    },
}


def normalize_display_state(state: str) -> str:
    """Canonicalize a display-state token. Raises on unknown values."""
    key = str(state).strip().lower().replace(" ", "_").replace("-", "_")
    if key not in _BORDER:
        raise ValueError(
            f"unknown display_state {state!r}; expected one of {DISPLAY_STATES}"
        )
    return key


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _halo_rgb(local_luminance: float) -> str:
    """Inverse-luminance achromatic halo for uncontrolled media crops.

    ``local_luminance`` is mean crop luminance in ``[0, 1]``. Dark crops get a
    light halo; light crops get a dark halo.
    """
    inv = 1.0 - _clamp01(local_luminance)
    # Keep halo readable: avoid pure black/white crush at extremes.
    level = int(round(32 + inv * 191))
    return f"#{level:02X}{level:02X}{level:02X}"


def stroke_layers(local_luminance: float, state: str) -> dict[str, Any]:
    """Three-layer stroke plan: outer halo + semantic (+ notch handled separately).

    Returns draw instructions only — no pixels, no store writes.
    """
    key = normalize_display_state(state)
    opacity = _IGNORED_OPACITY if key == "ignored" else 1.0
    return {
        "display_state": key,
        "outer_halo": {
            "width_px": _LAYER_WIDTH_PX,
            "color": _halo_rgb(local_luminance),
            "role": "inverse_luminance",
            "visible": key != "ignored",
        },
        "semantic": {
            "width_px": _LAYER_WIDTH_PX,
            "color": _SEMANTIC_COLOR[key],
            "role": "reinforce_state",
            "visible": key != "ignored",
        },
        "opacity": opacity,
        # Explicit non-claims so callers cannot smuggle identity from paint.
        "identity": {
            "auto_assign_person_id": False,
            "cluster_is_person": False,
            "conclusion": None,
        },
    }


def notch_spec(state: str) -> dict[str, Any]:
    """Notch / mark grammar for one display state (primary visual carrier)."""
    key = normalize_display_state(state)
    spec = dict(_NOTCH[key])
    return {
        "display_state": key,
        "fill": spec["fill"],
        "mark": spec["mark"],
        "visible": spec["visible"],
        "identity_conclusion": None,
    }


def box_style(display_state: str) -> dict[str, Any]:
    """Full draw-instruction dict for one face/observation box.

    Does not require local luminance; halo defaults to mid-gray inverse
    (luminance 0.5). Call ``stroke_layers`` when a crop mean is available.
    """
    key = normalize_display_state(display_state)
    border = dict(_BORDER[key])
    layers = stroke_layers(0.5, key)
    notch = notch_spec(key)
    return {
        "display_state": key,
        "border": {
            "style": border["style"],
            "dash": border["dash"],
            "mark": border["mark"],
            "visible": border["visible"],
            "width_px": _LAYER_WIDTH_PX,
        },
        "notch": {
            "fill": notch["fill"],
            "mark": notch["mark"],
            "visible": notch["visible"],
        },
        "layers": {
            "outer_halo": layers["outer_halo"],
            "semantic": layers["semantic"],
        },
        "opacity": layers["opacity"],
        "identity": {
            "auto_assign_person_id": False,
            "cluster_is_person": False,
            "conclusion": None,
        },
    }
