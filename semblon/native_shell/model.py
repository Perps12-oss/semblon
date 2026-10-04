"""Windowed media model for the Field.

rowCount is the archive size. QML GridView builds delegates only for the
viewport. Each data() call fills a small cache through ArchiveSession.window,
which is a SQL LIMIT/OFFSET slice.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from semblon.archive_session import ArchiveSession, MediaRef

_WINDOW = 120

_MEDIA_ID = Qt.ItemDataRole.UserRole + 1
_KIND = Qt.ItemDataRole.UserRole + 2
_DAY = Qt.ItemDataRole.UserRole + 3
_NAME = Qt.ItemDataRole.UserRole + 4


class ArchiveModel(QAbstractListModel):
    def __init__(self, session: ArchiveSession):
        super().__init__()
        self._session = session
        self._count = 0
        self._cache: list[MediaRef] = []
        self._cache_start = -1

    def reload(self) -> None:
        self.beginResetModel()
        self._count = self._session.count()
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
            self._cache = self._session.window(start, _WINDOW)
            self._cache_start = start
        local = row - self._cache_start
        if local < 0 or local >= len(self._cache):
            return None
        return self._cache[local]
