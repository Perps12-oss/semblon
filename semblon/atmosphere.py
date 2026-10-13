"""Atmosphere definitions and InteractionState → VisualTokens.

Product contract: docs/ATMOSPHERE.md

Pipeline: Atmosphere → InteractionState → VisualTokens → AtmosphereRenderer.
Appearance only — no identity, ingest, or schema behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from semblon.ui_tokens import Palette, mix

# ---------------------------------------------------------------------------
# State model
# ---------------------------------------------------------------------------


class InteractionState(str, Enum):
    RESTING = "resting"
    HOVER = "hover"
    SELECTED = "selected"
    PROCESSING = "processing"
    DISABLED = "disabled"


ATMOSPHERE_IDS = (
    "light",
    "mica_dark",
    "cyber_obsidian",
    "neon_ember",
    "tokyo_synth",
    "aurora",
    "dusk",
    "harbor",
    "ember_glass",
    "glacier",
    "orchid",
    "forest",
    "copper",
    "midnight_blue",
    "rose_quartz",
)

DARK_ATMOSPHERE_IDS = (
    "mica_dark",
    "cyber_obsidian",
    "neon_ember",
    "tokyo_synth",
    "aurora",
    "dusk",
    "harbor",
    "ember_glass",
    "glacier",
    "orchid",
    "forest",
    "copper",
    "midnight_blue",
    "rose_quartz",
)

DEFAULT_DARK_ATMOSPHERE = "mica_dark"

# Stored preference modes (single key — not a second system).
THEME_MODES = (
    "system",
    "light",
    "dark",  # alias → mica_dark
    *DARK_ATMOSPHERE_IDS,
)

ATMOSPHERE_LABELS: Mapping[str, str] = {
    "light": "Light",
    "mica_dark": "Mica Dark",
    "cyber_obsidian": "Cyber Obsidian",
    "neon_ember": "Neon Ember",
    "tokyo_synth": "Tokyo Synth",
    "aurora": "Aurora",
    "dusk": "Dusk",
    "harbor": "Harbor",
    "ember_glass": "Ember Glass",
    "glacier": "Glacier",
    "orchid": "Orchid",
    "forest": "Forest",
    "copper": "Copper",
    "midnight_blue": "Midnight Blue",
    "rose_quartz": "Rose Quartz",
}


# ---------------------------------------------------------------------------
# Token shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegionTokens:
    """Photo-region overlay for one interaction state."""

    outline: str
    outline_width: int
    fill: str  # "" = no fill
    label_fg: str
    label_visible: bool
    aura: str  # "" = no aura


@dataclass(frozen=True)
class VisualTokens:
    """Resolved paint for one atmosphere × state."""

    atmosphere_id: str
    state: InteractionState
    # Surfaces / type
    surface: str
    surface_muted: str
    surface_raised: str
    surface_stage: str
    surface_inset: str
    text_primary: str
    text_secondary: str
    text_tertiary: str
    text_disabled: str
    border: str
    border_strong: str
    accent: str
    accent_b: str  # dual-tone secondary (Tokyo); else equals accent
    danger: str
    warning: str
    positive: str
    focus_ring: str
    # Illumination / elevation
    elevation: int  # 0–3
    illumination: float  # 0–1 local light strength
    glow: str  # "" when none
    fill: str  # control fill for this state
    ink: str
    # Region
    region: RegionTokens
    # Motion / spotlight (atmosphere-level, echoed for callers)
    spotlight_radius_px: int
    spotlight_intensity: float
    processing_period_ms: int
    theme_transition_ms: int
    dual_tone: bool


@dataclass(frozen=True)
class AtmosphereSpec:
    """One named atmosphere. State overlays derive from these bases."""

    id: str
    label: str
    surface: str
    surface_muted: str
    surface_raised: str
    surface_stage: str
    surface_inset: str
    text_primary: str
    text_secondary: str
    text_tertiary: str
    text_quaternary: str
    border: str
    border_strong: str
    accent: str
    accent_b: str
    danger: str
    warning: str
    positive: str
    focus_ring: str
    mist: str  # soft illumination tint
    dual_tone: bool
    spotlight_radius_px: int
    spotlight_intensity: float
    processing_period_ms: int
    theme_transition_ms: int = 250

    def as_palette(self) -> Palette:
        return Palette(
            name=self.id if self.id != "light" else "light",
            text_primary=self.text_primary,
            text_secondary=self.text_secondary,
            text_tertiary=self.text_tertiary,
            text_quaternary=self.text_quaternary,
            surface=self.surface,
            surface_muted=self.surface_muted,
            surface_raised=self.surface_raised,
            border=self.border,
            accent=self.accent,
            danger=self.danger,
            warning=self.warning,
            positive=self.positive,
            focus_ring=self.focus_ring,
        )


# ---------------------------------------------------------------------------
# Atmosphere tables
# ---------------------------------------------------------------------------

LIGHT = AtmosphereSpec(
    id="light",
    label="Light",
    surface="#FFFFFF",
    surface_muted="#F5F5F4",
    surface_raised="#FFFFFF",
    surface_stage="#1A1C20",
    surface_inset="#EEEEEC",
    text_primary="#171717",
    text_secondary="#565656",
    text_tertiary="#6E6E6E",
    text_quaternary="#B9B9B9",
    border="#E4E4E2",
    border_strong="#C8C8C4",
    accent="#2E6BE6",
    accent_b="#2E6BE6",
    danger="#C92A2A",
    warning="#9C6500",
    positive="#1A7F37",
    focus_ring="#171717",
    mist="#D6E4FF",
    dual_tone=False,
    spotlight_radius_px=140,
    spotlight_intensity=0.18,
    processing_period_ms=1600,
)

MICA_DARK = AtmosphereSpec(
    id="mica_dark",
    label="Mica Dark",
    # Aligned to review chrome: page #141A22, rail #10161C, card #1C2430, accent #2DD4BF.
    surface="#141A22",
    surface_muted="#10161C",
    surface_raised="#1C2430",
    surface_stage="#0E141B",
    surface_inset="#10161C",
    text_primary="#F4F7FB",
    text_secondary="#A8B3C2",
    text_tertiary="#7E8B9C",
    text_quaternary="#5C6A7A",
    border="#2A3544",
    border_strong="#3A4558",
    accent="#2DD4BF",
    accent_b="#5EEAD4",
    danger="#E5484D",
    warning="#D9A13B",
    positive="#3FB27F",
    focus_ring="#F4F7FB",
    mist="#12343A",
    dual_tone=False,
    spotlight_radius_px=160,
    spotlight_intensity=0.28,
    processing_period_ms=1800,
)

CYBER_OBSIDIAN = AtmosphereSpec(
    id="cyber_obsidian",
    label="Cyber Obsidian",
    surface="#050608",
    surface_muted="#0A0C10",
    surface_raised="#12151A",
    surface_stage="#000000",
    surface_inset="#0C0E12",
    text_primary="#E6F7FF",
    text_secondary="#8FB8C8",
    text_tertiary="#678491",
    text_quaternary="#3A4E58",
    border="#1A2830",
    border_strong="#2A4050",
    accent="#00E5FF",
    accent_b="#00E5FF",
    danger="#FF3B5C",
    warning="#FFB020",
    positive="#00D68F",
    focus_ring="#00E5FF",
    mist="#003844",
    dual_tone=False,
    spotlight_radius_px=150,
    spotlight_intensity=0.34,
    processing_period_ms=1400,
)

NEON_EMBER = AtmosphereSpec(
    id="neon_ember",
    label="Neon Ember",
    surface="#1A1410",
    surface_muted="#221C16",
    surface_raised="#2A221A",
    surface_stage="#0F0C09",
    surface_inset="#1E1812",
    text_primary="#F5ECDC",
    text_secondary="#C4B49A",
    text_tertiary="#988976",
    text_quaternary="#5C5040",
    border="#3A3026",
    border_strong="#524636",
    accent="#E8A045",
    accent_b="#E8A045",
    danger="#E05545",
    warning="#E8A045",
    positive="#7CB87A",
    focus_ring="#F5ECDC",
    mist="#4A3018",
    dual_tone=False,
    spotlight_radius_px=155,
    spotlight_intensity=0.30,
    processing_period_ms=2000,
)

TOKYO_SYNTH = AtmosphereSpec(
    id="tokyo_synth",
    label="Tokyo Synth",
    surface="#120E1A",
    surface_muted="#1A1424",
    surface_raised="#241C32",
    surface_stage="#0A0810",
    surface_inset="#16101E",
    text_primary="#F0E8FF",
    text_secondary="#B8A8D0",
    text_tertiary="#90839D",
    text_quaternary="#4E4458",
    border="#322840",
    border_strong="#4A3A5C",
    accent="#FF2D95",
    accent_b="#2DFFB0",
    danger="#FF4D6A",
    warning="#FFC14D",
    positive="#2DFFB0",
    focus_ring="#FF2D95",
    mist="#3A1840",
    dual_tone=True,
    spotlight_radius_px=165,
    spotlight_intensity=0.32,
    processing_period_ms=1200,
)


def _gradient(spec_id: str, label: str, surface: str, muted: str, raised: str, accent: str, accent_b: str, mist: str) -> AtmosphereSpec:
    return AtmosphereSpec(
        id=spec_id,
        label=label,
        surface=surface,
        surface_muted=muted,
        surface_raised=raised,
        surface_stage=muted,
        surface_inset=muted,
        text_primary="#F4F7FB",
        text_secondary="#C5D0DE",
        text_tertiary="#8A9BB0",
        text_quaternary="#5C6A7A",
        border="#2A3544",
        border_strong="#3A4558",
        accent=accent,
        accent_b=accent_b,
        danger="#E5484D",
        warning="#D9A13B",
        positive="#3FB27F",
        focus_ring="#F4F7FB",
        mist=mist,
        dual_tone=True,
        spotlight_radius_px=170,
        spotlight_intensity=0.30,
        processing_period_ms=1600,
    )


AURORA = _gradient("aurora", "Aurora", "#142033", "#10182A", "#1C2C44", "#2DD4BF", "#7C8CFF", "#1B3A4A")
DUSK = _gradient("dusk", "Dusk", "#24182C", "#1A1222", "#32243C", "#C084FC", "#F0ABFC", "#3A2450")
HARBOR = _gradient("harbor", "Harbor", "#15242C", "#101C24", "#1C303C", "#38BDF8", "#67E8F9", "#123044")
EMBER_GLASS = _gradient("ember_glass", "Ember Glass", "#2A1C16", "#201610", "#3A2820", "#FB923C", "#FDBA74", "#4A2A18")
GLACIER = _gradient("glacier", "Glacier", "#172430", "#121C28", "#223244", "#7DD3FC", "#BAE6FD", "#1A3348")
ORCHID = _gradient("orchid", "Orchid", "#2A1830", "#1E1224", "#3A2444", "#E879F9", "#F0ABFC", "#4A2060")
FOREST = _gradient("forest", "Forest", "#14241C", "#101C16", "#1C3226", "#34D399", "#6EE7B7", "#143828")
COPPER = _gradient("copper", "Copper", "#2A2018", "#201810", "#3A2C22", "#D4A574", "#E7C7A1", "#4A3424")
MIDNIGHT_BLUE = _gradient("midnight_blue", "Midnight Blue", "#121C32", "#0E1628", "#1A2744", "#60A5FA", "#93C5FD", "#1A2C58")
ROSE_QUARTZ = _gradient("rose_quartz", "Rose Quartz", "#2C1C24", "#22161C", "#3C2832", "#FB7185", "#FDA4AF", "#4A2434")

ATMOSPHERES: Mapping[str, AtmosphereSpec] = {
    LIGHT.id: LIGHT,
    MICA_DARK.id: MICA_DARK,
    CYBER_OBSIDIAN.id: CYBER_OBSIDIAN,
    NEON_EMBER.id: NEON_EMBER,
    TOKYO_SYNTH.id: TOKYO_SYNTH,
    AURORA.id: AURORA,
    DUSK.id: DUSK,
    HARBOR.id: HARBOR,
    EMBER_GLASS.id: EMBER_GLASS,
    GLACIER.id: GLACIER,
    ORCHID.id: ORCHID,
    FOREST.id: FOREST,
    COPPER.id: COPPER,
    MIDNIGHT_BLUE.id: MIDNIGHT_BLUE,
    ROSE_QUARTZ.id: ROSE_QUARTZ,
}


def normalize_atmosphere_id(raw: str | None) -> str:
    """Map stored theme / aliases to an atmosphere id."""
    picked = (raw or "").strip().lower()
    if picked == "dark":
        return DEFAULT_DARK_ATMOSPHERE
    if picked in ATMOSPHERES:
        return picked
    return "light"


def get_atmosphere(atmosphere_id: str) -> AtmosphereSpec:
    return ATMOSPHERES[normalize_atmosphere_id(atmosphere_id)]


def _region_for(spec: AtmosphereSpec, state: InteractionState) -> RegionTokens:
    accent = spec.accent
    if state is InteractionState.RESTING:
        return RegionTokens(
            outline=mix(accent, spec.surface_stage, 0.35),
            outline_width=1,
            fill="",
            label_fg=spec.text_tertiary,
            label_visible=False,
            aura="",
        )
    if state is InteractionState.HOVER:
        return RegionTokens(
            outline=mix(accent, "#FFFFFF", 0.15),
            outline_width=2,
            fill=mix(accent, spec.surface_stage, 0.18),
            label_fg=spec.text_primary,
            label_visible=True,
            aura=mix(spec.mist, spec.surface_stage, 0.40),
        )
    if state is InteractionState.SELECTED:
        return RegionTokens(
            outline=accent,
            outline_width=3,
            fill=mix(accent, spec.surface_stage, 0.22),
            label_fg=spec.text_primary,
            label_visible=True,
            aura=mix(accent, spec.surface_stage, 0.28),
        )
    if state is InteractionState.PROCESSING:
        return RegionTokens(
            outline=mix(accent, spec.accent_b, 0.50) if spec.dual_tone else accent,
            outline_width=2,
            fill=mix(accent, spec.surface_stage, 0.14),
            label_fg=spec.text_secondary,
            label_visible=True,
            aura=mix(spec.mist, spec.surface_stage, 0.35),
        )
    # DISABLED
    return RegionTokens(
        outline=mix(spec.text_quaternary, spec.surface_stage, 0.40),
        outline_width=1,
        fill="",
        label_fg=spec.text_quaternary,
        label_visible=False,
        aura="",
    )


def resolve(atmosphere_id: str, state: InteractionState | str) -> VisualTokens:
    """Resolve VisualTokens for atmosphere × state."""
    if isinstance(state, str):
        state = InteractionState(state)
    spec = get_atmosphere(atmosphere_id)
    aid = spec.id

    if state is InteractionState.RESTING:
        fill = spec.surface_raised
        ink = spec.text_primary
        border = spec.border
        glow = ""
        elevation = 0
        illumination = 0.0
    elif state is InteractionState.HOVER:
        fill = mix(spec.mist, spec.surface_raised, 0.22)
        ink = spec.text_primary
        border = mix(spec.accent, spec.border, 0.45)
        glow = mix(spec.mist, spec.surface_raised, 0.35)
        elevation = 1
        illumination = spec.spotlight_intensity * 0.7
    elif state is InteractionState.SELECTED:
        fill = mix(spec.accent, spec.surface_raised, 0.16)
        ink = spec.text_primary
        border = spec.accent
        glow = mix(spec.accent, spec.surface_raised, 0.28)
        elevation = 2
        illumination = spec.spotlight_intensity
    elif state is InteractionState.PROCESSING:
        fill = mix(spec.accent, spec.surface_raised, 0.12)
        ink = spec.text_primary
        border = mix(spec.accent, spec.accent_b, 0.5) if spec.dual_tone else spec.accent
        glow = mix(spec.mist, spec.surface_raised, 0.40)
        elevation = 1
        illumination = spec.spotlight_intensity * 0.85
    else:  # DISABLED
        fill = spec.surface_muted
        ink = spec.text_quaternary
        border = mix(spec.border, spec.surface, 0.5)
        glow = ""
        elevation = 0
        illumination = 0.0

    return VisualTokens(
        atmosphere_id=aid,
        state=state,
        surface=spec.surface,
        surface_muted=spec.surface_muted,
        surface_raised=spec.surface_raised,
        surface_stage=spec.surface_stage,
        surface_inset=spec.surface_inset,
        text_primary=spec.text_primary,
        text_secondary=spec.text_secondary,
        text_tertiary=spec.text_tertiary,
        text_disabled=spec.text_quaternary,
        border=border if state is not InteractionState.RESTING else spec.border,
        border_strong=spec.border_strong,
        accent=spec.accent,
        accent_b=spec.accent_b,
        danger=spec.danger,
        warning=spec.warning,
        positive=spec.positive,
        focus_ring=spec.focus_ring,
        elevation=elevation,
        illumination=illumination,
        glow=glow,
        fill=fill,
        ink=ink,
        region=_region_for(spec, state),
        spotlight_radius_px=spec.spotlight_radius_px,
        spotlight_intensity=spec.spotlight_intensity,
        processing_period_ms=spec.processing_period_ms,
        theme_transition_ms=spec.theme_transition_ms,
        dual_tone=spec.dual_tone,
    )


def palette_for(atmosphere_id: str) -> Palette:
    """Resting palette for publish / ttk theme."""
    return get_atmosphere(atmosphere_id).as_palette()


def interpolable_hex_fields(spec: AtmosphereSpec) -> dict[str, str]:
    """Fields that theme transition may lerp."""
    return {
        "surface": spec.surface,
        "surface_muted": spec.surface_muted,
        "surface_raised": spec.surface_raised,
        "surface_stage": spec.surface_stage,
        "surface_inset": spec.surface_inset,
        "text_primary": spec.text_primary,
        "text_secondary": spec.text_secondary,
        "text_tertiary": spec.text_tertiary,
        "text_quaternary": spec.text_quaternary,
        "border": spec.border,
        "border_strong": spec.border_strong,
        "accent": spec.accent,
        "accent_b": spec.accent_b,
        "danger": spec.danger,
        "warning": spec.warning,
        "positive": spec.positive,
        "focus_ring": spec.focus_ring,
        "mist": spec.mist,
    }


def lerp_hex(a: str, b: str, t: float) -> str:
    """Linear interpolate two #RRGGBB colors. ``t`` in [0, 1]."""
    return mix(b, a, min(1.0, max(0.0, t)))


def lerp_field_map(
    src: Mapping[str, str], dst: Mapping[str, str], t: float
) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, end in dst.items():
        start = src.get(key, end)
        out[key] = lerp_hex(start, end, t)
    return out
