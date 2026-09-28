"""Clam ttk theme bound to ``ui_tokens``. One theme for every Tk surface."""

from __future__ import annotations

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    tk = None
    ttk = None
    tkfont = None

from semblon.ui_tokens import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_SUBTLE,
    FOCUS_RING,
    BG_CANVAS,
    BG_INSET,
    BG_PRESSED,
    BG_SUBTLE,
    BG_SURFACE,
    BODY,
    BODY_STRONG,
    CAPTION,
    BORDER_DEFAULT,
    BORDER_STRONG,
    BORDER_SUBTLE,
    FONT_MONO,
    FONT_MONO_FALLBACK,
    FONT_TEXT,
    FONT_TEXT_FALLBACK,
    H3,
    INK_DISABLED,
    INK_ON_ACCENT,
    INK_PRIMARY,
    INK_SECONDARY,
    INK_TERTIARY,
)

_APPLIED: set[int] = set()


def px(widget, n: int) -> int:
    """Scale a 96-DPI pixel metric by Tk's current scaling (100% / 150% / 175%)."""
    if widget is None:
        return n
    try:
        scaling = float(widget.tk.call("tk", "scaling"))
    except (tk.TclError, AttributeError, TypeError, ValueError):
        return n
    factor = scaling / (96 / 72)
    return max(1, int(round(n * factor)))


def _family(installed: set[str], preferred: str, fallback: str) -> str:
    if preferred in installed:
        return preferred
    if fallback in installed:
        return fallback
    return preferred


def apply_theme(root, *, force: bool = False) -> None:
    """Configure the process ttk theme. Safe to call once per Tcl interpreter.

    ``force`` rebinds colors after ``ui_tokens.publish`` (appearance switch).
    """
    if tk is None or ttk is None or root is None:
        return
    # Theme is interpreter-global. Key off the Tcl interpreter, not the widget.
    key = id(getattr(root, "tk", root))
    if key in _APPLIED and not force:
        try:
            root.configure(bg=BG_CANVAS)
        except tk.TclError:
            pass
        return
    _APPLIED.add(key)

    installed: set[str] = set()
    if tkfont is not None:
        try:
            installed = set(tkfont.families(root))
        except tk.TclError:
            installed = set()
    text = _family(installed, FONT_TEXT, FONT_TEXT_FALLBACK)
    mono = _family(installed, FONT_MONO, FONT_MONO_FALLBACK)

    def face(spec):
        family = spec[0]
        if family in (FONT_TEXT, "Segoe UI Variable Display") and text != family:
            if family == "Segoe UI Variable Display" and "Segoe UI Variable Display" in installed:
                return spec
            family = text
        if family == FONT_MONO and mono != family:
            family = mono
        return (family, *spec[1:])

    body = face(BODY)
    h3 = face(H3)

    try:
        root.configure(bg=BG_CANVAS)
    except tk.TclError:
        return

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        ".",
        background=BG_CANVAS,
        foreground=INK_PRIMARY,
        font=body,
        borderwidth=0,
        relief="flat",
    )
    style.configure("TFrame", background=BG_CANVAS)
    style.configure("TLabel", background=BG_CANVAS, foreground=INK_PRIMARY, font=body)
    style.configure(
        "Muted.TLabel", background=BG_CANVAS, foreground=INK_SECONDARY, font=body
    )
    style.configure(
        "Caption.TLabel", background=BG_CANVAS, foreground=INK_TERTIARY, font=face(CAPTION),
    )
    style.configure("Surface.TFrame", background=BG_SURFACE)
    style.configure(
        "Surface.TLabel", background=BG_SURFACE, foreground=INK_PRIMARY, font=body
    )
    style.configure(
        "SurfaceMuted.TLabel",
        background=BG_SURFACE,
        foreground=INK_SECONDARY,
        font=body,
    )
    style.configure(
        "SurfaceTitle.TLabel", background=BG_SURFACE, foreground=INK_PRIMARY, font=h3
    )
    style.configure("Subtle.TFrame", background=BG_SUBTLE)
    style.configure(
        "Subtle.TLabel", background=BG_SUBTLE, foreground=INK_TERTIARY, font=body
    )
    style.configure(
        "TButton",
        background=BG_SURFACE,
        foreground=INK_PRIMARY,
        bordercolor=BORDER_DEFAULT,
        lightcolor=BG_SURFACE,
        darkcolor=BG_SURFACE,
        relief="flat",
        padding=(16, 8),
        font=body,
        focusthickness=2,
        focuscolor=FOCUS_RING,
    )
    style.map(
        "TButton",
        background=[
            ("pressed", BG_PRESSED),
            ("active", BG_SUBTLE),
            ("disabled", BG_SUBTLE),
        ],
        foreground=[("disabled", INK_DISABLED)],
        bordercolor=[("focus", FOCUS_RING), ("active", BORDER_STRONG), ("!focus", BORDER_DEFAULT)],
    )
    style.configure(
        "Primary.TButton",
        background=ACCENT,
        foreground=INK_ON_ACCENT,
        bordercolor=ACCENT,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        font=face(BODY_STRONG),
        padding=(20, 10),
    )
    style.map(
        "Primary.TButton",
        background=[
            ("pressed", ACCENT_HOVER),
            ("active", ACCENT_HOVER),
            ("disabled", BG_SUBTLE),
        ],
        foreground=[("disabled", INK_DISABLED), ("!disabled", INK_ON_ACCENT)],
    )
    style.configure(
        "TEntry",
        fieldbackground=BG_INSET,
        foreground=INK_PRIMARY,
        bordercolor=BORDER_DEFAULT,
        lightcolor=BG_INSET,
        darkcolor=BG_INSET,
        padding=(12, 8),
        relief="flat",
        font=body,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", FOCUS_RING), ("!focus", BORDER_DEFAULT)],
        lightcolor=[("focus", ACCENT_SUBTLE)],
    )
    style.configure(
        "TMenubutton",
        background=BG_SURFACE,
        foreground=INK_SECONDARY,
        bordercolor=BORDER_DEFAULT,
        relief="flat",
        padding=(12, 6),
        font=body,
        arrowsize=0,
    )
    style.map(
        "TMenubutton",
        background=[("active", BG_SUBTLE), ("pressed", BG_PRESSED)],
        foreground=[("active", INK_PRIMARY)],
    )
    style.configure(
        "TCheckbutton",
        background=BG_CANVAS,
        foreground=INK_PRIMARY,
        font=body,
    )
    style.map("TCheckbutton", background=[("active", BG_CANVAS)])
    style.configure(
        "TLabelframe",
        background=BG_CANVAS,
        bordercolor=BORDER_SUBTLE,
        relief="flat",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=BG_CANVAS,
        foreground=INK_TERTIARY,
        font=body,
    )
    style.configure(
        "TScrollbar",
        background=BG_SUBTLE,
        troughcolor=BG_CANVAS,
        bordercolor=BG_CANVAS,
        arrowsize=12,
        relief="flat",
    )
    try:
        root.option_add("*Font", body)
        root.option_add("*Menu.font", body)
        root.option_add("*Menu.background", BG_SURFACE)
        root.option_add("*Menu.foreground", INK_PRIMARY)
        root.option_add("*Menu.activeBackground", BG_SUBTLE)
        root.option_add("*Menu.activeForeground", INK_PRIMARY)
        root.option_add("*Menu.borderWidth", 0)
    except tk.TclError:
        pass


def style_listbox(widget) -> None:
    """Flat listbox using the same ink and surface as the rest of the product."""
    if widget is None:
        return
    try:
        widget.configure(
            bg=BG_SURFACE,
            fg=INK_PRIMARY,
            selectbackground=ACCENT_SUBTLE,
            selectforeground=INK_PRIMARY,
            font=BODY,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            highlightcolor=FOCUS_RING,
            activestyle="none",
            bd=0,
        )
    except tk.TclError:
        pass


def reset_theme_for_tests() -> None:
    """Allow a fresh interpreter-less unit to apply the theme again."""
    _APPLIED.clear()
