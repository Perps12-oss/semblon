"""Optional desktop helpers. Importing this package does not require PySide6.

Pages, widgets, window, and app live in sibling modules and need `.[gui]`.
"""

from semblon.desktop.qtcompat import list_item_flags

__all__ = ["list_item_flags"]
