"""Canvas button and theme — appearance only, same configure/state surface."""

from __future__ import annotations

import pytest

pytest.importorskip("tkinter")

from semblon.ui_theme import apply_theme, px, reset_theme_for_tests
from semblon.ui_tokens import ACCENT, ACCENT_SUBTLE, BG_CANVAS, INK_ON_ACCENT, INK_PRIMARY, PRIMARY_HEIGHT
from semblon.ui_widgets import Button


@pytest.fixture(scope="module")
def root():
    """One Tk interpreter. A second Tk() in the same process can fail to read init.tcl on Windows."""
    import tkinter as tk

    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"tkinter could not start: {exc}")
    r.withdraw()
    reset_theme_for_tests()
    apply_theme(r)
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass
    reset_theme_for_tests()


@pytest.fixture(autouse=True)
def _clear(root):
    yield
    for child in list(root.winfo_children()):
        child.destroy()


def test_button_configure_state_blocks_command(root):
    calls = []
    btn = Button(root, text="Review people", command=lambda: calls.append(1), kind="primary")
    btn.invoke()
    assert calls == [1]
    btn.configure(state="disabled")
    btn.invoke()
    assert calls == [1]
    assert btn.cget("state") == "disabled"
    btn.configure(text="Resume", state="normal")
    assert btn.cget("text") == "Resume"
    btn.invoke()
    assert calls == [1, 1]


def test_nav_pressed_state(root):
    btn = Button(root, text="Home", kind="nav", icon="home", plate=BG_CANVAS)
    assert btn.state() == ()
    btn.state(["pressed"])
    assert btn.state() == ("pressed",)
    btn.state(["!pressed"])
    assert btn.state() == ()


def test_nav_badge_uses_accent_subtle_fill():
    """To review count chip must read clearly in dark mode."""
    import inspect

    from semblon import ui_widgets

    src = inspect.getsource(ui_widgets.Button._draw_badge)
    assert "ACCENT_SUBTLE" in src
    assert "INK_PRIMARY" in src
    assert "BG_SURFACE" not in src or "fill=ACCENT_SUBTLE" in src
    assert ACCENT_SUBTLE != "#1A1A1A"  # not the low-contrast surface


def test_button_set_kind_switches_weight(root):
    btn = Button(root, text="Add a photo folder", kind="primary")
    btn.set_kind("secondary")
    assert btn._kind == "secondary"
    btn.set_kind("primary")
    assert btn._kind == "primary"


def test_one_button_class_covers_kinds(root):
    kinds = ("primary", "secondary", "tertiary", "destructive", "nav")
    for kind in kinds:
        btn = Button(root, text=kind, kind=kind)
        btn.update_idletasks()
        assert btn.winfo_reqheight() >= 4


def test_theme_scaling_grows_pixel_metrics(root):
    root.tk.call("tk", "scaling", 1.333333)
    base = px(root, PRIMARY_HEIGHT)
    root.tk.call("tk", "scaling", 2.0)  # 150%
    mid = px(root, PRIMARY_HEIGHT)
    root.tk.call("tk", "scaling", 2.333333)  # 175%
    high = px(root, PRIMARY_HEIGHT)
    assert mid > base
    assert high > mid
    btn = Button(root, text="Add a photo folder", kind="primary")
    btn.update_idletasks()
    assert btn.winfo_reqheight() >= high - 2
    # Primary actions use atmosphere accent illumination.
    assert ACCENT == "#2E6BE6"
    fill, ink, border = btn._palette()
    assert fill == ACCENT
    assert ink == INK_ON_ACCENT
    assert border == ""
