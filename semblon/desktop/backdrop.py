"""Optional Windows DWM backdrop. Failure falls back to solid."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_MICA_EFFECT = 1029
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMSBT_MAINWINDOW = 2
_MICA_MIN_BUILD = 22000
_BACKDROP_TYPE_MIN_BUILD = 22621


class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


def apply_mica(hwnd: int | None) -> str:
    if sys.platform != "win32" or not hwnd:
        return "solid"
    try:
        build = int(sys.getwindowsversion().build)
        dwm = ctypes.windll.dwmapi
        margins = MARGINS(-1, -1, -1, -1)
        dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(int(hwnd)), ctypes.byref(margins))
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(
            wintypes.HWND(int(hwnd)),
            ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(val),
            ctypes.sizeof(val),
        )
        if build >= _BACKDROP_TYPE_MIN_BUILD:
            kind = ctypes.c_int(DWMSBT_MAINWINDOW)
            hr = dwm.DwmSetWindowAttribute(
                wintypes.HWND(int(hwnd)),
                ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
                ctypes.byref(kind),
                ctypes.sizeof(kind),
            )
            if hr == 0:
                return "mica"
        if build >= _MICA_MIN_BUILD:
            mica = ctypes.c_int(1)
            hr = dwm.DwmSetWindowAttribute(
                wintypes.HWND(int(hwnd)),
                ctypes.c_uint(DWMWA_MICA_EFFECT),
                ctypes.byref(mica),
                ctypes.sizeof(mica),
            )
            if hr == 0:
                return "mica"
    except (AttributeError, OSError, ValueError):
        return "solid"
    return "solid"
