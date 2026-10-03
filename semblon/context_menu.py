"""Button-3 context menu host over GuiCommand registry (surfaces=context).

No second command catalogue. Availability gated per command.
"""

from __future__ import annotations

from typing import Any

__all__ = ["build_context_menu", "popup_context_menu"]


def build_context_menu(host: Any, registry: Any, context: dict | None = None):
    """Return a tk.Menu populated from registry context commands, or None."""
    try:
        import tkinter as tk
    except ImportError:
        return None
    if registry is None or host is None:
        return None
    try:
        root = getattr(host, "root", None) or getattr(host, "frame", None)
        if root is None:
            return None
        menu = tk.Menu(root, tearoff=0)
    except Exception:  # noqa: BLE001
        return None
    ctx = context if isinstance(context, dict) else {}
    commands = list(registry.commands(surface="context") or [])
    added = 0
    for cmd in commands:
        try:
            if getattr(cmd, "requires_context", False) and not cmd.is_available(host, ctx):
                continue
            if hasattr(cmd, "is_available") and not cmd.is_available(host, ctx):
                continue
        except Exception:  # noqa: BLE001
            continue
        label = str(getattr(cmd, "label", None) or getattr(cmd, "id", "Action"))
        try:
            menu.add_command(
                label=label,
                command=lambda c=cmd: c.execute(host, ctx),
            )
            added += 1
        except Exception:  # noqa: BLE001
            continue
    if added == 0:
        try:
            menu.destroy()
        except Exception:  # noqa: BLE001
            pass
        return None
    return menu


def popup_context_menu(host: Any, event, *, context: dict | None = None) -> bool:
    """Show Button-3 menu at event. Returns True if a menu was shown."""
    registry = getattr(host, "_registry", None)
    menu = build_context_menu(host, registry, context)
    if menu is None:
        return False
    try:
        menu.tk_popup(int(event.x_root), int(event.y_root))
    except Exception:  # noqa: BLE001
        try:
            menu.destroy()
        except Exception:  # noqa: BLE001
            pass
        return False
    finally:
        try:
            menu.grab_release()
        except Exception:  # noqa: BLE001
            pass
    return True
