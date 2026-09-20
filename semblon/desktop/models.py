"""Qt list models for the optional desktop / S8 presentation path.

Do not write ``Qt.ItemFlag.ItemIsKeyboardFocusable`` here. That name is
missing on some PySide6 ItemFlag enums (the live crash on
``flags()``). Use ``list_item_flags()``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from semblon.desktop.qtcompat import list_item_flags


class SemblonListModel(QAbstractListModel):
    """Enabled + selectable rows; keyboard focus only when the enum has it."""

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return list_item_flags()


class ReviewListModel(SemblonListModel):
    """Board rows for a Qt view. Presentation only; mutations stay in review.py."""

    LabelRole = Qt.ItemDataRole.UserRole + 1
    KindRole = Qt.ItemDataRole.UserRole + 2
    ClusterIdRole = Qt.ItemDataRole.UserRole + 3
    FaceIdRole = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, self.LabelRole):
            return row.get("label") or ""
        if role == self.KindRole:
            return row.get("kind") or ""
        if role == self.ClusterIdRole:
            return row.get("cluster_id") or row.get("clusterId") or ""
        if role == self.FaceIdRole:
            return row.get("face_id") or row.get("faceId") or ""
        return None

    def roleNames(self) -> dict[int, bytes]:  # type: ignore[override]
        return {
            int(Qt.ItemDataRole.DisplayRole): b"display",
            int(self.LabelRole): b"label",
            int(self.KindRole): b"kind",
            int(self.ClusterIdRole): b"clusterId",
            int(self.FaceIdRole): b"faceId",
        }

    def reset_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()
