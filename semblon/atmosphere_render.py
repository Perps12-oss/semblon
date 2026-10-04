"""AtmosphereRenderer — capability-aware paint for Semblon chrome.

Contract: docs/ATMOSPHERE.md

Owns: Spotlight, ProcessingCue, theme transition, PreviewTheatre.
Does not touch identity, ingest, or schema.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from semblon.atmosphere import (
    ATMOSPHERE_LABELS,
    DARK_ATMOSPHERE_IDS,
    AtmosphereSpec,
    InteractionState,
    VisualTokens,
    get_atmosphere,
    interpolable_hex_fields,
    lerp_field_map,
    normalize_atmosphere_id,
    palette_for,
    resolve,
)
from semblon.ui_tokens import Palette, mix, publish

# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------


class Capability(str, Enum):
    FULL = "full"
    REDUCED = "reduced"
    STATIC = "static"


_CAPABILITY: Capability | None = None
_FORCE_CAPABILITY: Capability | None = None


def system_prefers_reduced_motion() -> bool | None:
    """True/False on Windows when the accessibility key is readable. Else None."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Accessibility",
        ) as key:
            # Undocumented but common; treat missing as unknown.
            value, _kind = winreg.QueryValueEx(key, "DynamicNotification")
    except OSError:
        pass
    else:
        try:
            if int(value) == 0:
                return True
        except (TypeError, ValueError):
            pass
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop\WindowMetrics",
        ) as key:
            # MinAnimate 0 → reduced window animations.
            value, _kind = winreg.QueryValueEx(key, "MinAnimate")
    except OSError:
        return None
    try:
        return str(value).strip() in ("0", "False", "false")
    except (TypeError, ValueError):
        return None


def detect_capability(*, force: Capability | None = None) -> Capability:
    """Probe once per process. ``force`` overrides for tests."""
    global _CAPABILITY, _FORCE_CAPABILITY
    if force is not None:
        _FORCE_CAPABILITY = force
        _CAPABILITY = force
        return force
    if _FORCE_CAPABILITY is not None:
        return _FORCE_CAPABILITY
    if _CAPABILITY is not None:
        return _CAPABILITY
    reduced = system_prefers_reduced_motion()
    if reduced is True:
        _CAPABILITY = Capability.REDUCED
    else:
        _CAPABILITY = Capability.FULL
    return _CAPABILITY


def reset_capability_for_tests() -> None:
    global _CAPABILITY, _FORCE_CAPABILITY
    _CAPABILITY = None
    _FORCE_CAPABILITY = None


def allows_continuous_motion(cap: Capability | None = None) -> bool:
    level = cap or detect_capability()
    return level is Capability.FULL


# ---------------------------------------------------------------------------
# Active atmosphere tracking
# ---------------------------------------------------------------------------

_ACTIVE_ATMOSPHERE = "light"
_TRANSITION_JOB: object | None = None
_LISTENERS: list[Callable[[str], None]] = []


def active_atmosphere_id() -> str:
    return _ACTIVE_ATMOSPHERE


def on_atmosphere_changed(cb: Callable[[str], None]) -> None:
    if cb not in _LISTENERS:
        _LISTENERS.append(cb)


def _notify(atmosphere_id: str) -> None:
    for cb in list(_LISTENERS):
        try:
            cb(atmosphere_id)
        except Exception:  # noqa: BLE001 — listener must not break publish
            pass


def publish_atmosphere(atmosphere_id: str) -> Palette:
    """Publish resting palette for ``atmosphere_id`` immediately."""
    global _ACTIVE_ATMOSPHERE
    aid = normalize_atmosphere_id(atmosphere_id)
    _ACTIVE_ATMOSPHERE = aid
    pal = palette_for(aid)
    publish(pal)
    _notify(aid)
    return pal


def _palette_from_fields(atmosphere_id: str, fields: dict[str, str]) -> Palette:
    name = "light" if atmosphere_id == "light" else atmosphere_id
    return Palette(
        name=name,
        text_primary=fields["text_primary"],
        text_secondary=fields["text_secondary"],
        text_tertiary=fields["text_tertiary"],
        text_quaternary=fields["text_quaternary"],
        surface=fields["surface"],
        surface_muted=fields["surface_muted"],
        surface_raised=fields["surface_raised"],
        border=fields["border"],
        accent=fields["accent"],
        danger=fields["danger"],
        warning=fields["warning"],
        positive=fields["positive"],
        focus_ring=fields["focus_ring"],
    )


def transition_to(
    root,
    atmosphere_id: str,
    *,
    on_done: Callable[[], None] | None = None,
    duration_ms: int | None = None,
) -> None:
    """Lerp interpolable hex fields then publish. Snaps when motion reduced.

    Owner for theme interpolation (docs/ATMOSPHERE.md).
    """
    global _TRANSITION_JOB, _ACTIVE_ATMOSPHERE
    aid = normalize_atmosphere_id(atmosphere_id)
    target = get_atmosphere(aid)
    dest_fields = interpolable_hex_fields(target)
    src_spec = get_atmosphere(_ACTIVE_ATMOSPHERE)
    src_fields = interpolable_hex_fields(src_spec)

    # Cancel prior transition.
    if _TRANSITION_JOB is not None and root is not None:
        try:
            root.after_cancel(_TRANSITION_JOB)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            pass
        _TRANSITION_JOB = None

    if not allows_continuous_motion() or root is None or duration_ms == 0:
        publish_atmosphere(aid)
        if on_done is not None:
            on_done()
        return

    total = duration_ms if duration_ms is not None else target.theme_transition_ms
    steps = max(4, min(12, total // 40))
    step_ms = max(16, total // steps)
    step_i = {"i": 0}

    def tick() -> None:
        global _TRANSITION_JOB, _ACTIVE_ATMOSPHERE
        i = step_i["i"] + 1
        step_i["i"] = i
        t = min(1.0, i / steps)
        fields = lerp_field_map(src_fields, dest_fields, t)
        pal = _palette_from_fields(aid, fields)
        publish(pal)
        if t >= 1.0:
            _TRANSITION_JOB = None
            _ACTIVE_ATMOSPHERE = aid
            publish_atmosphere(aid)
            if on_done is not None:
                on_done()
            return
        try:
            _TRANSITION_JOB = root.after(step_ms, tick)
        except Exception:  # noqa: BLE001
            _TRANSITION_JOB = None
            publish_atmosphere(aid)
            if on_done is not None:
                on_done()

    tick()


# ---------------------------------------------------------------------------
# Spotlight — concentric alpha rings (Tk approximation of radial illumination)
# ---------------------------------------------------------------------------


@dataclass
class Spotlight:
    """Local atmospheric illumination under the pointer.

    Tk cannot do GPU bloom; concentric ovals approximate the contract.
    """

    canvas: object
    tag: str = "atm_spotlight"

    def clear(self) -> None:
        try:
            self.canvas.delete(self.tag)
        except Exception:  # noqa: BLE001
            pass

    def paint(
        self,
        x: float,
        y: float,
        tokens: VisualTokens,
        *,
        capability: Capability | None = None,
    ) -> None:
        self.clear()
        cap = capability or detect_capability()
        if cap is Capability.STATIC:
            return
        if tokens.illumination <= 0 and tokens.state is InteractionState.RESTING:
            return
        intensity = tokens.illumination or tokens.spotlight_intensity * 0.5
        if intensity <= 0:
            return
        radius = max(40, int(tokens.spotlight_radius_px * (0.55 + 0.45 * intensity)))
        rings = 4 if allows_continuous_motion(cap) else 2
        accent = tokens.accent
        base = tokens.surface_raised
        for i in range(rings, 0, -1):
            r = radius * i / rings
            amount = intensity * (0.08 + 0.10 * (1.0 - i / rings))
            color = mix(accent, base, amount)
            try:
                self.canvas.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    outline="",
                    fill=color,
                    tags=(self.tag,),
                )
            except Exception:  # noqa: BLE001
                return
        # Keep spotlight behind interactive overlays when tag stacking allows.
        try:
            self.canvas.tag_lower(self.tag)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# ProcessingCue — footer / control pulse; dual-tone for Tokyo
# ---------------------------------------------------------------------------


class ProcessingCue:
    """Restrained processing illumination. Stops when idle.

    Owner: docs/ATMOSPHERE.md § Processing pulse / dual-tone.
    """

    def __init__(self, root, *, on_tick: Callable[[str, float], None] | None = None):
        self._root = root
        self._on_tick = on_tick
        self._job = None
        self._active = False
        self._phase = 0.0
        self._atmosphere_id = active_atmosphere_id()

    @property
    def active(self) -> bool:
        return self._active

    def start(self, atmosphere_id: str | None = None) -> None:
        self._atmosphere_id = normalize_atmosphere_id(
            atmosphere_id or active_atmosphere_id()
        )
        self._active = True
        self._phase = 0.0
        if not allows_continuous_motion():
            # Static processing tint once.
            tokens = resolve(self._atmosphere_id, InteractionState.PROCESSING)
            if self._on_tick is not None:
                self._on_tick(tokens.accent, 1.0)
            return
        self._schedule()

    def stop(self) -> None:
        self._active = False
        if self._job is not None and self._root is not None:
            try:
                self._root.after_cancel(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None
        if self._on_tick is not None:
            resting = resolve(self._atmosphere_id, InteractionState.RESTING)
            self._on_tick(resting.accent, 0.0)

    def _schedule(self) -> None:
        if not self._active or self._root is None:
            return
        spec = get_atmosphere(self._atmosphere_id)
        period = max(400, spec.processing_period_ms)
        # ~12 fpsish for soft pulse without busy looping.
        frame_ms = 80
        self._phase = (self._phase + frame_ms / period) % 1.0
        # Triangle wave 0→1→0
        p = self._phase
        brightness = 1.0 - abs(2.0 * p - 1.0)
        if spec.dual_tone:
            color = mix(spec.accent_b, spec.accent, brightness)
        else:
            color = mix(spec.mist, spec.accent, 0.35 + 0.45 * brightness)
        if self._on_tick is not None:
            self._on_tick(color, brightness)
        try:
            self._job = self._root.after(frame_ms, self._schedule)
        except Exception:  # noqa: BLE001
            self._job = None


# ---------------------------------------------------------------------------
# PreviewTheatre — Settings tiles using the same resolve() path
# ---------------------------------------------------------------------------


class PreviewTheatre:
    """Small Canvas demo of an atmosphere. Same tokens as the real app."""

    DEMO_STATES = (
        InteractionState.RESTING,
        InteractionState.HOVER,
        InteractionState.SELECTED,
        InteractionState.PROCESSING,
        InteractionState.DISABLED,
    )

    def __init__(
        self,
        master,
        atmosphere_id: str,
        *,
        width: int = 168,
        height: int = 96,
        selected: bool = False,
        command: Callable[[str], None] | None = None,
    ):
        import tkinter as tk

        self.atmosphere_id = normalize_atmosphere_id(atmosphere_id)
        self._command = command
        self._selected = selected
        self._demo_i = 0
        self._job = None
        self._cap = detect_capability()
        self.canvas = tk.Canvas(
            master,
            width=width,
            height=height,
            highlightthickness=2 if selected else 1,
            bd=0,
            cursor="hand2",
        )
        self._w = width
        self._h = height
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Enter>", lambda _e: self._paint(InteractionState.HOVER))
        self.canvas.bind("<Leave>", lambda _e: self._paint(self._rest_state()))
        self._paint(self._rest_state())
        if allows_continuous_motion(self._cap) and not selected:
            self._arm_demo()

    def widget(self):
        return self.canvas

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        try:
            self.canvas.configure(highlightthickness=2 if selected else 1)
        except Exception:  # noqa: BLE001
            pass
        self._paint(self._rest_state())
        if selected:
            self._cancel_demo()
        elif allows_continuous_motion(self._cap):
            self._arm_demo()

    def destroy(self) -> None:
        self._cancel_demo()
        try:
            self.canvas.destroy()
        except Exception:  # noqa: BLE001
            pass

    def _rest_state(self) -> InteractionState:
        return InteractionState.SELECTED if self._selected else InteractionState.RESTING

    def _on_click(self, _event=None) -> None:
        if self._command is not None:
            self._command(self.atmosphere_id)

    def _arm_demo(self) -> None:
        self._cancel_demo()
        try:
            self._job = self.canvas.after(900, self._demo_tick)
        except Exception:  # noqa: BLE001
            self._job = None

    def _cancel_demo(self) -> None:
        if self._job is not None:
            try:
                self.canvas.after_cancel(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None

    def _demo_tick(self) -> None:
        self._demo_i = (self._demo_i + 1) % len(self.DEMO_STATES)
        self._paint(self.DEMO_STATES[self._demo_i])
        try:
            self._job = self.canvas.after(700, self._demo_tick)
        except Exception:  # noqa: BLE001
            self._job = None

    def _paint(self, state: InteractionState) -> None:
        tokens = resolve(self.atmosphere_id, state)
        c = self.canvas
        w, h = self._w, self._h
        try:
            c.delete("all")
            c.configure(
                bg=tokens.surface,
                highlightbackground=tokens.border if not self._selected else tokens.accent,
                highlightcolor=tokens.accent,
            )
            # Raised chrome plate
            pad = 8
            c.create_rectangle(
                pad,
                pad,
                w - pad,
                h - pad - 18,
                fill=tokens.fill,
                outline=tokens.border,
                width=1 + tokens.elevation,
            )
            # Stage strip (media)
            c.create_rectangle(
                pad + 6,
                pad + 6,
                w - pad - 6,
                h // 2,
                fill=tokens.surface_stage,
                outline="",
            )
            # Region glyph
            rx0, ry0 = pad + 14, pad + 12
            rx1, ry1 = pad + 44, pad + 36
            reg = tokens.region
            if reg.fill:
                c.create_rectangle(rx0, ry0, rx1, ry1, fill=reg.fill, outline="")
            if reg.aura:
                c.create_rectangle(
                    rx0 - 2, ry0 - 2, rx1 + 2, ry1 + 2, outline=reg.aura, width=2
                )
            c.create_rectangle(
                rx0, ry0, rx1, ry1, outline=reg.outline, width=reg.outline_width
            )
            # Accent bar / processing cue
            bar = tokens.accent
            if state is InteractionState.PROCESSING and tokens.dual_tone:
                bar = mix(tokens.accent_b, tokens.accent, 0.5)
            c.create_rectangle(pad, h - 14, w - pad, h - 8, fill=bar, outline="")
            # Label
            label = ATMOSPHERE_LABELS.get(self.atmosphere_id, self.atmosphere_id)
            c.create_text(
                w // 2,
                h - 4,
                text=label,
                fill=tokens.text_secondary,
                font=("Segoe UI", 8),
                anchor="s",
            )
            if tokens.glow and state is not InteractionState.RESTING:
                c.create_rectangle(
                    pad - 1,
                    pad - 1,
                    w - pad + 1,
                    h - pad - 17,
                    outline=tokens.glow,
                    width=1,
                )
        except Exception:  # noqa: BLE001
            pass


def build_atmosphere_previews(
    master,
    *,
    current: str,
    on_select: Callable[[str], None],
) -> list[PreviewTheatre]:
    """Four dark-atmosphere preview theatres for Appearance settings."""
    tiles: list[PreviewTheatre] = []
    cur = normalize_atmosphere_id(current)
    for aid in DARK_ATMOSPHERE_IDS:
        tile = PreviewTheatre(
            master,
            aid,
            selected=(aid == cur),
            command=on_select,
        )
        tiles.append(tile)
    return tiles


# ---------------------------------------------------------------------------
# StageCapabilityCard — Model D Stage entry points (spotlight + selection)
# ---------------------------------------------------------------------------


class StageCapabilityCard:
    """Home Stage capability surface.

    HOVER → local spotlight (never conflated with SELECTED).
    SELECTED → accent elevation / bloom edge.
    Click → product intention (Explore / Discover / People).
    """

    def __init__(
        self,
        master,
        *,
        title: str,
        body: str,
        command: Callable[[], None] | None = None,
        primary: bool = False,
        width: int | None = None,
        height: int | None = None,
        atmosphere_id: str | None = None,
    ):
        import tkinter as tk
        from semblon.ui_tokens import BODY, BODY_STRONG, H1

        self._command = command
        self._primary = primary
        self._title = title
        self._body = body
        self._cap = detect_capability()
        self._atmosphere_id = normalize_atmosphere_id(
            atmosphere_id or active_atmosphere_id()
        )
        self._state = InteractionState.RESTING
        self._w = int(width or (420 if primary else 280))
        self._h = int(height or (200 if primary else 140))
        self.canvas = tk.Canvas(
            master,
            width=self._w,
            height=self._h,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._spotlight = Spotlight(self.canvas, tag="stage_spot")
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Button-1>", self._on_click)
        self._font_title = H1 if primary else BODY_STRONG
        self._font_body = BODY
        self.paint(InteractionState.RESTING)

    def widget(self):
        return self.canvas

    def set_atmosphere(self, atmosphere_id: str) -> None:
        self._atmosphere_id = normalize_atmosphere_id(atmosphere_id)
        self.paint(self._state)

    def paint(self, state: InteractionState) -> None:
        self._state = state
        tokens = resolve(self._atmosphere_id, state)
        c = self.canvas
        try:
            c.delete("all")
        except Exception:  # noqa: BLE001
            return
        try:
            c.configure(bg=tokens.surface_raised, highlightthickness=0)
        except Exception:  # noqa: BLE001
            pass
        # Card plate
        edge = 3 if state is InteractionState.SELECTED else (
            2 if state is InteractionState.HOVER else 1
        )
        try:
            c.create_rectangle(
                edge,
                edge,
                self._w - edge,
                self._h - edge,
                fill=tokens.surface_raised,
                outline=tokens.border if state is not InteractionState.RESTING else tokens.surface,
                width=edge,
                tags=("plate",),
            )
        except Exception:  # noqa: BLE001
            return
        # Title + body
        pad_x = 18
        try:
            c.create_text(
                pad_x,
                22 if self._primary else 18,
                text=self._title,
                anchor="nw",
                fill=tokens.text_primary,
                font=self._font_title,
                tags=("title",),
            )
            c.create_text(
                pad_x,
                58 if self._primary else 48,
                text=self._body,
                anchor="nw",
                fill=tokens.text_secondary,
                font=self._font_body,
                width=self._w - pad_x * 2,
                tags=("body",),
            )
            if self._primary:
                c.create_text(
                    pad_x,
                    self._h - 28,
                    text="Open Explore →",
                    anchor="sw",
                    fill=tokens.accent,
                    font=self._font_body,
                    tags=("cta",),
                )
        except Exception:  # noqa: BLE001
            pass
        # Selected bloom — soft accent aura (not the same as hover spotlight).
        if state is InteractionState.SELECTED and tokens.glow:
            try:
                for i, amount in ((1, 0.12), (2, 0.06)):
                    inset = 2 + i * 2
                    color = mix(tokens.accent, tokens.surface_raised, amount)
                    c.create_rectangle(
                        inset,
                        inset,
                        self._w - inset,
                        self._h - inset,
                        outline=color,
                        width=1,
                        tags=("bloom",),
                    )
                c.tag_lower("bloom")
            except Exception:  # noqa: BLE001
                pass
        try:
            c.tag_lower("plate")
        except Exception:  # noqa: BLE001
            pass

    def _on_enter(self, _event=None) -> None:
        if self._state is InteractionState.SELECTED:
            return
        self.paint(InteractionState.HOVER)

    def _on_leave(self, _event=None) -> None:
        self._spotlight.clear()
        if self._state is InteractionState.SELECTED:
            self.paint(InteractionState.SELECTED)
            return
        self.paint(InteractionState.RESTING)

    def _on_motion(self, event) -> None:
        if self._state is InteractionState.SELECTED:
            return
        if self._state is not InteractionState.HOVER:
            self.paint(InteractionState.HOVER)
        tokens = resolve(self._atmosphere_id, InteractionState.HOVER)
        self._spotlight.paint(event.x, event.y, tokens, capability=self._cap)

    def _on_click(self, _event=None) -> None:
        self.paint(InteractionState.SELECTED)
        if self._command is not None:
            self._command()


def dissolve_stage(
    root,
    *,
    on_done: Callable[[], None],
    atmosphere_id: str | None = None,
    duration_ms: int = 250,
) -> None:
    """Stage → Memory transition. Full: stepped mist tint; reduced/static: snap."""
    cap = detect_capability()
    aid = normalize_atmosphere_id(atmosphere_id or active_atmosphere_id())
    if not allows_continuous_motion(cap) or root is None:
        on_done()
        return
    tokens_rest = resolve(aid, InteractionState.RESTING)
    spec = get_atmosphere(aid)
    steps = max(3, duration_ms // 50)
    frame = max(40, duration_ms // steps)
    state = {"i": 0}

    def tick() -> None:
        i = state["i"]
        if i >= steps:
            on_done()
            return
        t = (i + 1) / steps
        # Soft mist toward resting surface — chrome recedes as Memory arrives.
        try:
            color = mix(spec.mist, tokens_rest.surface, t)
            root.configure(bg=color)
        except Exception:  # noqa: BLE001
            pass
        state["i"] = i + 1
        try:
            root.after(frame, tick)
        except Exception:  # noqa: BLE001
            on_done()

    tick()


# Re-export for callers
__all__ = [
    "Capability",
    "ProcessingCue",
    "PreviewTheatre",
    "Spotlight",
    "StageCapabilityCard",
    "active_atmosphere_id",
    "allows_continuous_motion",
    "build_atmosphere_previews",
    "detect_capability",
    "dissolve_stage",
    "on_atmosphere_changed",
    "publish_atmosphere",
    "reset_capability_for_tests",
    "resolve",
    "system_prefers_reduced_motion",
    "transition_to",
]


def mix_hex(a: str, b: str, t: float) -> str:
    def rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    ar, ag, ab = rgb(a)
    br, bg, bb = rgb(b)
    t = min(1.0, max(0.0, t))
    return "#{:02X}{:02X}{:02X}".format(
        int(ar + (br - ar) * t),
        int(ag + (bg - ag) * t),
        int(ab + (bb - ab) * t),
    )


def paint_vertical_gradient(canvas, c1: str, c2: str, height: int | None = None) -> None:
    """Paint a two-stop vertical gradient. Tk has no gradient fill."""
    canvas.delete("gradient")
    width = max(canvas.winfo_width(), 2)
    height = height or max(canvas.winfo_height(), 2)
    steps = max(height, 2)
    for i in range(steps):
        color = mix_hex(c1, c2, i / (steps - 1))
        canvas.create_line(0, i, width, i, fill=color, tags="gradient")
    canvas.tag_lower("gradient")


class GradientBackdrop:
    """Full-window gradient behind the shell. Content frames stay solid cards."""

    def __init__(self, root) -> None:
        import tkinter as tk

        self.root = root
        self.canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.canvas.lower()
        self._c1 = "#141A22"
        self._c2 = "#12343A"
        root.bind("<Configure>", self._on_resize, add="+")

    def set_stops(self, c1: str, c2: str) -> None:
        self._c1 = c1
        self._c2 = c2
        try:
            self.root.configure(bg=c1)
        except Exception:
            pass
        self.paint()

    def paint(self) -> None:
        self.canvas.lower()
        paint_vertical_gradient(self.canvas, self._c1, self._c2)

    def _on_resize(self, event) -> None:
        if event.widget is not self.root:
            return
        self.paint()
