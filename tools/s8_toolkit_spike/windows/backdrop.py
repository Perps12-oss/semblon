"""Windows DWM backdrop adapter. QML must not call DWM.

Returns a material name: mica | acrylic | solid.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_MICA_EFFECT = 1029  # Win11 22000
DWMWA_SYSTEMBACKDROP_TYPE = 38  # Win11 22621+
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2  # Mica
DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
DWMSBT_TABBEDWINDOW = 4  # Mica Alt

_MICA_MIN_BUILD = 22000
_BACKDROP_TYPE_MIN_BUILD = 22621


class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


def windows_build() -> int:
    if sys.platform != "win32":
        return 0
    return int(sys.getwindowsversion().build)


def _dwm_set(hwnd: int, attr: int, value: int) -> bool:
    dwm = ctypes.windll.dwmapi
    val = ctypes.c_int(value)
    hr = dwm.DwmSetWindowAttribute(
        wintypes.HWND(hwnd),
        ctypes.c_uint(attr),
        ctypes.byref(val),
        ctypes.sizeof(val),
    )
    return hr == 0


def _extend_frame(hwnd: int) -> bool:
    dwm = ctypes.windll.dwmapi
    margins = MARGINS(-1, -1, -1, -1)
    hr = dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins))
    return hr == 0


class WindowsBackdropAdapter:
    """Window-owned material. Surfaces only sit on the backdrop."""

    def apply(self, hwnd: int | None, *, prefer: str = "mica") -> str:
        if sys.platform != "win32" or not hwnd:
            return "solid"
        build = windows_build()
        try:
            _extend_frame(int(hwnd))
            _dwm_set(int(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
            prefer = (prefer or "mica").lower()
            if build >= _BACKDROP_TYPE_MIN_BUILD:
                kind = DWMSBT_MAINWINDOW if prefer != "acrylic" else DWMSBT_TRANSIENTWINDOW
                if _dwm_set(int(hwnd), DWMWA_SYSTEMBACKDROP_TYPE, kind):
                    return "mica" if kind == DWMSBT_MAINWINDOW else "acrylic"
            if build >= _MICA_MIN_BUILD and prefer != "acrylic":
                if _dwm_set(int(hwnd), DWMWA_MICA_EFFECT, 1):
                    return "mica"
            if prefer == "acrylic" and build >= _BACKDROP_TYPE_MIN_BUILD:
                if _dwm_set(int(hwnd), DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_TRANSIENTWINDOW):
                    return "acrylic"
        except (AttributeError, OSError, ValueError):
            return "solid"
        return "solid"
