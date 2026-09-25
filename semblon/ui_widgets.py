"""Canonical Tk controls for the visual design language.

One button class. ``kind`` selects primary, secondary, tertiary, destructive,
or nav. Callers keep ``configure(text=..., state=...)``, ``pack``, and
``state(["pressed"])`` — the same surface Home and Review already use.
"""

from __future__ import annotations

try:
    import tkinter as tk
    from tkinter import font as tkfont
except ModuleNotFoundError:  # pragma: no cover
    tk = None
    tkfont = None

from semblon.ui_icons import draw as draw_icon
from semblon.ui_theme import px
from semblon.ui_tokens import (
    ACCENT_SUBTLE,
    BG_CANVAS,
    BG_HOVER,
    BG_PRESSED,
    BG_SUBTLE,
    BG_SURFACE,
    FOCUS_RING,
    NAV_ACTIVE,
    BODY,
    BODY_STRONG,
    BORDER_DEFAULT,
    BORDER_STRONG,
    DANGER,
    INK_DISABLED,
    INK_PRIMARY,
    INK_SECONDARY,
    NAV_HEIGHT,
    PRIMARY_HEIGHT,
    RADIUS_SM,
    SECONDARY_HEIGHT,
    TERTIARY_HEIGHT,
)

_HEIGHT = {
    "primary": PRIMARY_HEIGHT,
    "secondary": SECONDARY_HEIGHT,
    "tertiary": TERTIARY_HEIGHT,
    "destructive": SECONDARY_HEIGHT,
    "nav": NAV_HEIGHT,
}
_FONT = {
    "primary": BODY_STRONG,
    "secondary": BODY,
    "tertiary": BODY,
    "destructive": BODY,
    "nav": BODY,
}


def _blend(hex_color: str, onto: str, amount: float) -> str:
    """Mix ``hex_color`` into ``onto``. ``amount`` is how much of hex_color remains."""

    def rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    a = rgb(hex_color)
    b = rgb(onto)
    t = min(1.0, max(0.0, amount))
    mixed = tuple(int(round(a[i] * t + b[i] * (1.0 - t))) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


if tk is None:

    class Button:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("tkinter is required")

else:

    class Button(tk.Canvas):
        """Rounded action or nav item. One class, four kinds plus nav."""

        def __init__(
            self,
            master,
            text: str = "",
            command=None,
            kind: str = "secondary",
            icon: str | None = None,
            plate: str | None = None,
            **kw,
        ):
            self._kind = kind if kind in _HEIGHT else "secondary"
            self._text = text
            self._command = command
            self._icon = icon
            self._enabled = True
            self._hover = False
            self._pressed = False
            self._active = False
            self._badge: str | None = None
            self._plate = plate or BG_SURFACE
            height = px(master, _HEIGHT[self._kind])
            super().__init__(
                master,
                height=height,
                highlightthickness=0,
                bd=0,
                bg=self._plate,
                cursor="hand2",
                **kw,
            )
            self._font = _FONT[self._kind]
            self.bind("<Configure>", lambda _e: self._redraw())
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            self.bind("<ButtonPress-1>", self._on_press)
            self.bind("<ButtonRelease-1>", self._on_release)
            self.bind("<FocusIn>", lambda _e: self._redraw())
            self.bind("<FocusOut>", lambda _e: self._redraw())
            self.bind("<Return>", lambda _e: self.invoke())
            self.bind("<space>", lambda _e: self.invoke())
            try:
                super().configure(takefocus=True)
            except tk.TclError:
                pass
            self._redraw()

        def cget(self, key):
            if key in ("text", "-text"):
                return self._text
            if key in ("state", "-state"):
                return tk.NORMAL if self._enabled else tk.DISABLED
            return super().cget(key)

        def configure(self, cnf=None, **kw):
            if isinstance(cnf, str) and not kw:
                return self.cget(cnf)
            if isinstance(cnf, dict):
                kw = {**cnf, **kw}
            if "text" in kw:
                self._text = kw.pop("text")
            if "state" in kw:
                state = str(kw.pop("state"))
                self._enabled = state not in ("disabled", str(tk.DISABLED))
                self.configure_cursor()
            if "command" in kw:
                self._command = kw.pop("command")
            if "badge" in kw:
                self.set_badge(kw.pop("badge"))
            if kw:
                super().configure(**kw)
            # Grow with the label when the row is not already stretched by pack.
            try:
                if self.winfo_width() <= self._measure() + 4:
                    super().configure(width=self._measure())
            except tk.TclError:
                pass
            self._redraw()
            return None

        config = configure

        def configure_cursor(self) -> None:
            try:
                super().configure(cursor="hand2" if self._enabled else "arrow")
            except tk.TclError:
                pass

        def set_kind(self, kind: str) -> None:
            """Switch primary/secondary/… weight without rebuilding the control."""
            if kind not in _HEIGHT:
                kind = "secondary"
            self._kind = kind
            self._font = _FONT[kind]
            try:
                super().configure(height=px(self, _HEIGHT[kind]))
            except tk.TclError:
                pass
            try:
                if self.winfo_width() <= self._measure() + 4:
                    super().configure(width=self._measure())
            except tk.TclError:
                pass
            self._redraw()

        def set_badge(self, count) -> None:
            """Nav count. Hidden at 0 or None. The count must already be real."""
            try:
                n = int(count)
            except (TypeError, ValueError):
                n = 0
            self._badge = str(n) if n > 0 else None
            self._redraw()

        def state(self, statespec=None):
            """ttk-style ``state(["pressed"])`` / ``state(["!pressed"])`` for nav."""
            if statespec is None:
                return ("pressed",) if self._active else ()
            for spec in statespec:
                if spec == "pressed":
                    self._active = True
                elif spec == "!pressed":
                    self._active = False
            self._redraw()
            return None

        def invoke(self) -> None:
            if self._enabled and self._command is not None:
                self._command()

        def _on_enter(self, _event=None) -> None:
            self._hover = True
            self._redraw()

        def _on_leave(self, _event=None) -> None:
            self._hover = False
            self._pressed = False
            self._redraw()

        def _on_press(self, _event=None) -> None:
            if not self._enabled:
                return
            self._pressed = True
            self.focus_set()
            self._redraw()

        def _on_release(self, event=None) -> None:
            was = self._pressed
            self._pressed = False
            self._redraw()
            if not was or not self._enabled or self._command is None:
                return
            if event is not None:
                inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
                if not inside:
                    return
            self._command()

        def _palette(self) -> tuple[str, str, str]:
            """Return fill, ink, border for the current interaction state."""
            kind = self._kind
            if not self._enabled:
                if kind == "primary":
                    return _blend(INK_PRIMARY, self._plate, 0.40), INK_DISABLED, ""
                if kind == "destructive":
                    return self._plate, INK_DISABLED, _blend(DANGER, self._plate, 0.30)
                return BG_SUBTLE, INK_DISABLED, BORDER_DEFAULT if kind == "secondary" else ""
            if kind == "primary":
                # Ink button. Accent stays on progress and status, not on actions.
                ink = BG_CANVAS
                if self._pressed:
                    return _blend(INK_PRIMARY, BG_CANVAS, 0.70), ink, ""
                if self._hover:
                    return _blend(INK_PRIMARY, BG_CANVAS, 0.85), ink, ""
                return INK_PRIMARY, ink, ""
            if kind == "destructive":
                fill = _blend(DANGER, self._plate, 0.10) if (self._hover or self._pressed) else self._plate
                return fill, DANGER, _blend(DANGER, self._plate, 0.30)
            if kind == "nav":
                if self._active:
                    return NAV_ACTIVE, INK_PRIMARY, ""
                if self._pressed or self._hover:
                    return BG_HOVER, INK_PRIMARY, ""
                return self._plate, INK_SECONDARY, ""
            if kind == "tertiary":
                if self._pressed:
                    return BG_PRESSED, INK_PRIMARY, ""
                if self._hover:
                    return BG_HOVER, INK_PRIMARY, ""
                return self._plate, INK_SECONDARY, ""
            # secondary
            if self._pressed:
                return BG_PRESSED, INK_PRIMARY, BORDER_STRONG
            if self._hover:
                return BG_HOVER, INK_PRIMARY, BORDER_STRONG
            return BG_SURFACE, INK_PRIMARY, BORDER_DEFAULT

        def _measure(self) -> int:
            if tkfont is None:
                return 80
            try:
                fnt = tkfont.Font(font=self._font, root=self)
                text_w = fnt.measure(self._text) if self._text else 0
            except tk.TclError:
                text_w = 8 * max(len(self._text), 1)
            icon_w = px(self, 20) + px(self, 8) if self._icon else 0
            pad = px(self, 20 if self._kind == "primary" else 16)
            if self._kind in ("tertiary", "nav"):
                pad = px(self, 12)
            return text_w + icon_w + pad * 2

        def _redraw(self) -> None:
            self.delete("all")
            width = self.winfo_width()
            height = self.winfo_height()
            if width <= 1:
                width = max(self._measure(), px(self, 36))
                try:
                    super().configure(width=width)
                except tk.TclError:
                    pass
            if height <= 1:
                height = px(self, _HEIGHT[self._kind])
            fill, ink, border = self._palette()
            radius = px(self, RADIUS_SM)
            show_plate = not (
                self._kind == "nav" and not (self._hover or self._active or self._pressed)
            )
            if show_plate:
                self._round(
                    1, 1, width - 2, height - 2, radius, fill=fill, outline=border or ""
                )
            icon_size = px(self, 20 if self._kind == "nav" else 16)
            x = px(self, 12)
            icon_ink = ink
            if self._icon:
                draw_icon(self, self._icon, x, (height - icon_size) / 2, icon_size, icon_ink)
                x += icon_size + px(self, 8)
            reserve = 0
            if self._badge and self._kind == "nav":
                reserve = self._badge_width() + px(self, 8)
            shown = self._text
            if shown and tkfont is not None and reserve:
                try:
                    fnt = tkfont.Font(font=self._font, root=self)
                    avail = max(12, width - x - reserve)
                    if fnt.measure(shown) > avail:
                        trimmed = shown
                        while trimmed and fnt.measure(trimmed + "…") > avail:
                            trimmed = trimmed[:-1]
                        shown = (trimmed + "…") if trimmed != shown else shown
                except tk.TclError:
                    pass
            if shown:
                anchor = "w" if (self._icon or self._kind == "nav") else "center"
                tx = x if anchor == "w" else width / 2
                self.create_text(
                    tx, height / 2, text=shown, fill=ink, font=self._font, anchor=anchor
                )
            if self._badge and self._kind == "nav":
                self._draw_badge(width, height)
            try:
                focused = self.focus_get() == self
            except tk.TclError:
                focused = False
            if focused and self._enabled:
                self._round(
                    1, 1, width - 2, height - 2, radius, fill="", outline=FOCUS_RING, width=2
                )

        def _badge_width(self) -> int:
            label = self._badge or ""
            if not label:
                return 0
            if tkfont is None:
                return 8 * len(label) + px(self, 16)
            try:
                fnt = tkfont.Font(font=self._font, root=self)
                text_w = fnt.measure(label)
            except tk.TclError:
                text_w = 8 * len(label)
            return text_w + px(self, 8)

        def _draw_badge(self, width: int, height: int) -> None:
            label = self._badge or ""
            if not label or tkfont is None:
                return
            badge_w = self._badge_width()
            badge_h = px(self, 18)
            x2 = width - px(self, 8)
            x1 = x2 - badge_w
            y1 = (height - badge_h) / 2
            y2 = y1 + badge_h
            self._round(
                x1, y1, x2, y2, badge_h / 2, fill=ACCENT_SUBTLE, outline=BORDER_DEFAULT
            )
            self.create_text(
                (x1 + x2) / 2,
                height / 2,
                text=label,
                fill=INK_PRIMARY,
                font=self._font,
            )

        def _round(self, x1, y1, x2, y2, r, fill="", outline="", width=1):
            r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
            if r < 1:
                return self.create_rectangle(
                    x1, y1, x2, y2, fill=fill or "", outline=outline or ""
                )
            points = [
                x1 + r, y1,
                x2 - r, y1,
                x2, y1,
                x2, y1 + r,
                x2, y2 - r,
                x2, y2,
                x2 - r, y2,
                x1 + r, y2,
                x1, y2,
                x1, y2 - r,
                x1, y1 + r,
                x1, y1,
            ]
            if fill:
                self.create_polygon(points, smooth=True, splinesteps=16, fill=fill, outline="")
            if outline:
                self.create_line(
                    points + [x1 + r, y1],
                    fill=outline,
                    width=width,
                    smooth=True,
                    splinesteps=16,
                )
            return None
