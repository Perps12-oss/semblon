"""PySide6 ItemFlag helpers that survive older / slimmer Qt enum bindings.

``Qt.ItemFlag.ItemIsKeyboardFocusable`` exists on some PySide6 builds and
not others. A direct attribute lookup inside ``QAbstractListModel.flags()``
raises AttributeError and Qt logs 'Error calling Python override of
QAbstractListModel::flags()' for every row.
"""

from __future__ import annotations

from typing import Any


def list_item_flags(item_flag: Any | None = None) -> Any:
    """Enabled + selectable, plus keyboard-focusable only when the enum has it."""
    if item_flag is None:
        from PySide6.QtCore import Qt

        item_flag = Qt.ItemFlag
    flags = item_flag.ItemIsEnabled | item_flag.ItemIsSelectable
    flags |= getattr(item_flag, "ItemIsKeyboardFocusable", item_flag.NoItemFlags)
    return flags
