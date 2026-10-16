"""Lab capture convenience filter — not a security boundary.

Windows whose titles start with ``semblon`` are skipped for lab capture.
That does not stop other apps, renamed windows, or OS-level capture APIs.
Product screen-capture UI is deferred; see docs/decisions/2026-10-16-screen-capture-deferred.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowRect:
    title: str
    x: int
    y: int
    w: int
    h: int


def intersects(ax: int, ay: int, aw: int, ah: int, bx: int, by: int, bw: int, bh: int) -> bool:
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def blocked_hit(
    x: int,
    y: int,
    w: int,
    h: int,
    windows: tuple[WindowRect, ...] | list[WindowRect],
) -> WindowRect | None:
    for window in windows:
        if intersects(x, y, w, h, window.x, window.y, window.w, window.h):
            return window
    return None


def semblon_windows_win32() -> tuple[WindowRect, ...]:
    """Own top-level windows on Windows. Empty on every other system."""
    import sys

    if sys.platform != "win32":
        return ()
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[WindowRect] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _each(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""
        if not title.lower().startswith("semblon"):
            return True
        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            found.append(
                WindowRect(
                    title=title,
                    x=int(rect.left),
                    y=int(rect.top),
                    w=int(rect.right - rect.left),
                    h=int(rect.bottom - rect.top),
                )
            )
        return True

    user32.EnumWindows(_each, 0)
    return tuple(found)
