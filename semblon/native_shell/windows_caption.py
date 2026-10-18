"""Native Windows caption colour for the archive shell.

Keeps the system title-bar buttons. Uses immersive dark mode plus caption
and text colours when DwmSetWindowAttribute supports them. Failures leave
the system caption unchanged.
"""

from __future__ import annotations

import sys


def _colorref(hex_color: str) -> int:
    """Convert #RRGGBB to a COLORREF (0x00BBGGRR)."""
    raw = str(hex_color or "").strip().lstrip("#")
    if len(raw) != 6:
        return 0x00100B0A
    r = int(raw[0:2], 16)
    g = int(raw[2:4], 16)
    b = int(raw[4:6], 16)
    return int(b | (g << 8) | (r << 16))


def apply_dark_caption(bg_hex: str = "#0a0b10", text_hex: str = "#f2f3f5") -> None:
    """Tint top-level Qt windows on Windows. No-op elsewhere."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        from PySide6.QtWidgets import QApplication
    except Exception:  # noqa: BLE001
        return

    app = QApplication.instance()
    if app is None:
        return

    dwmapi = ctypes.WinDLL("dwmapi")
    DwmSetWindowAttribute = dwmapi.DwmSetWindowAttribute
    DwmSetWindowAttribute.argtypes = [
        wintypes.HWND,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    DwmSetWindowAttribute.restype = wintypes.LONG

    # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE; 35 = CAPTION_COLOR; 36 = TEXT_COLOR
    dark = ctypes.c_int(1)
    caption = ctypes.c_int(_colorref(bg_hex))
    text = ctypes.c_int(_colorref(text_hex))

    for window in app.topLevelWindows():
        try:
            hwnd = int(window.winId())
        except Exception:  # noqa: BLE001
            continue
        if not hwnd:
            continue
        try:
            DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
            DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))
        except Exception:  # noqa: BLE001 — leave the system caption
            continue
