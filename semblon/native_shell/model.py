"""Windowed media model for the Field.

rowCount is the archive size. QML GridView builds delegates only for the
viewport. Each data() call fills a small cache through Application.archive_window,
which is a SQL LIMIT/OFFSET slice owned by the application archive session.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from semblon.application import Application, MediaRef

_WINDOW = 120

_MEDIA_ID = Qt.ItemDataRole.UserRole + 1
_KIND = Qt.ItemDataRole.UserRole + 2
_DAY = Qt.ItemDataRole.UserRole + 3
_NAME = Qt.ItemDataRole.UserRole + 4

_SIMILAR_ID = Qt.ItemDataRole.UserRole + 1
_SIMILAR_SCORE = Qt.ItemDataRole.UserRole + 2
_STRIP_CAP = 8


class ArchiveModel(QAbstractListModel):
    def __init__(self, app: Application):
        super().__init__()
        self._app = app
        self._count = 0
        self._cache: list = []
        self._cache_start = -1

    def reload(self) -> None:
        self.beginResetModel()
        self._count = self._app.archive_count()
        self._cache = []
        self._cache_start = -1
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return self._count

    def roleNames(self):  # noqa: N802
        return {
            _MEDIA_ID: b"mediaId",
            _KIND: b"kind",
            _DAY: b"day",
            _NAME: b"name",
        }

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._at(index.row())
        if item is None:
            return None
        if role in (Qt.ItemDataRole.DisplayRole, _NAME):
            return item.name
        if role == _MEDIA_ID:
            return item.media_id
        if role == _KIND:
            return item.source_type
        if role == _DAY:
            return item.day
        return None

    def _at(self, row: int) -> MediaRef | None:
        if row < 0 or row >= self._count:
            return None
        if self._cache_start < 0 or row < self._cache_start or row >= self._cache_start + len(self._cache):
            start = max(0, row - 40)
            self._cache = self._app.archive_window(start, _WINDOW)
            self._cache_start = start
        local = row - self._cache_start
        if local < 0 or local >= len(self._cache):
            return None
        return self._cache[local]


class SimilarStripModel(QAbstractListModel):
    """Contextual similar-memory strip. media id plus score. Not an archive."""

    def __init__(self):
        super().__init__()
        self._rows: list[tuple[str, float]] = []

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def roleNames(self):  # noqa: N802
        return {_SIMILAR_ID: b"mediaId", _SIMILAR_SCORE: b"score"}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        media_id, score = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, _SIMILAR_ID):
            return media_id
        if role == _SIMILAR_SCORE:
            return score
        return None

    def set_rows(self, rows: list[tuple[str, float]]) -> None:
        self.beginResetModel()
        self._rows = list(rows[:_STRIP_CAP])
        self.endResetModel()

    def media_id(self, row: int) -> str:
        if row < 0 or row >= len(self._rows):
            return ""
        return self._rows[row][0]
