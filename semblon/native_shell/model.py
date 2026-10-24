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
_SIMILAR_NX = Qt.ItemDataRole.UserRole + 3
_SIMILAR_NY = Qt.ItemDataRole.UserRole + 4
_SIMILAR_NW = Qt.ItemDataRole.UserRole + 5
_SIMILAR_NH = Qt.ItemDataRole.UserRole + 6
# The results tray scrolls every hit this search already returned.
# Search itself caps the list. This only stops a runaway model.
_STRIP_CAP = 48


def _when(mtime_ns: int | None) -> str:
    """"8 Feb 2025, 14:32" on the same clock the day dividers use."""
    from datetime import datetime, timezone

    if not mtime_ns:
        return ""
    try:
        stamp = datetime.fromtimestamp(int(mtime_ns) / 1e9, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return ""
    return f"{stamp.day} {stamp.strftime('%b %Y, %H:%M')}"


class ArchiveModel(QAbstractListModel):
    def __init__(self, app: Application):
        super().__init__()
        self._app = app
        self._count = 0
        self._cache: list = []
        self._cache_start = -1
        self._ids: list[str] | None = None

    def reload(self) -> None:
        self.beginResetModel()
        self._ids = None
        self._count = self._app.archive_count()
        self._cache = []
        self._cache_start = -1
        self.endResetModel()

    def set_media_ids(self, media_ids: list[str] | None) -> None:
        """Limit the Field to an explicit id list from a browse bucket.

        ``None`` restores the archive window. Ids are not a second library.
        """
        self.beginResetModel()
        if media_ids is None:
            self._ids = None
            self._count = self._app.archive_count()
        else:
            self._ids = [str(item) for item in media_ids if item]
            self._count = len(self._ids)
        self._cache = []
        self._cache_start = -1
        self.endResetModel()

    def media_ids(self) -> list[str] | None:
        """Current Field id list, or None when showing the full archive window."""
        if self._ids is None:
            return None
        return list(self._ids)

    def days(self) -> list[str]:
        """Day key of every row, in the order the Roll shows them."""
        if self._ids is None:
            return self._app.archive_days()
        out = []
        for media_id in self._ids:
            item = self._app.media(media_id)
            out.append(item.day if item is not None else "")
        return out

    def row_info(self, row: int) -> dict:
        item = self._at(row)
        if item is None:
            return {"mediaId": "", "day": "", "name": "", "when": ""}
        return {"mediaId": item.media_id, "day": item.day, "name": item.name, "when": _when(item.mtime_ns)}

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
        if self._ids is not None:
            return self._app.media(self._ids[row])
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
        self._rows: list[tuple] = []

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def roleNames(self):  # noqa: N802
        return {
            _SIMILAR_ID: b"mediaId",
            _SIMILAR_SCORE: b"score",
            _SIMILAR_NX: b"matchX",
            _SIMILAR_NY: b"matchY",
            _SIMILAR_NW: b"matchW",
            _SIMILAR_NH: b"matchH",
        }

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        media_id, score, nx, ny, nw, nh = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, _SIMILAR_ID):
            return media_id
        if role == _SIMILAR_SCORE:
            return score
        if role == _SIMILAR_NX:
            return nx
        if role == _SIMILAR_NY:
            return ny
        if role == _SIMILAR_NW:
            return nw
        if role == _SIMILAR_NH:
            return nh
        return None

    def set_rows(self, rows: list) -> None:
        packed = []
        for row in list(rows)[:_STRIP_CAP]:
            media_id = str(row[0])
            score = float(row[1])
            if len(row) >= 6:
                packed.append(
                    (media_id, score, float(row[2]), float(row[3]), float(row[4]), float(row[5]))
                )
            else:
                packed.append((media_id, score, 0.0, 0.0, 0.0, 0.0))
        if packed == self._rows:
            return
        self.beginResetModel()
        self._rows = packed
        self.endResetModel()

    def media_id(self, row: int) -> str:
        if row < 0 or row >= len(self._rows):
            return ""
        return self._rows[row][0]


_GROUP_ID = Qt.ItemDataRole.UserRole + 1
_GROUP_TITLE = Qt.ItemDataRole.UserRole + 2
_GROUP_COUNT = Qt.ItemDataRole.UserRole + 3
_GROUP_NAMED = Qt.ItemDataRole.UserRole + 4
_GROUP_MEDIA = Qt.ItemDataRole.UserRole + 5
_GROUP_FACE = Qt.ItemDataRole.UserRole + 6
_GROUP_KIND = Qt.ItemDataRole.UserRole + 7
_GROUP_BAND = Qt.ItemDataRole.UserRole + 8
_GROUP_BAND_LABEL = Qt.ItemDataRole.UserRole + 9


class PeopleModel(QAbstractListModel):
    """Candidate groups and named persons from the review board. Not a second archive."""

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def roleNames(self):  # noqa: N802
        return {
            _GROUP_ID: b"subject",
            _GROUP_TITLE: b"title",
            _GROUP_COUNT: b"faceCount",
            _GROUP_NAMED: b"named",
            _GROUP_MEDIA: b"mediaId",
            _GROUP_FACE: b"faceId",
            _GROUP_KIND: b"kind",
            _GROUP_BAND: b"band",
            _GROUP_BAND_LABEL: b"bandLabel",
        }

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, _GROUP_TITLE):
            return row["title"]
        if role == _GROUP_ID:
            return row["subject"]
        if role == _GROUP_COUNT:
            return row["count"]
        if role == _GROUP_NAMED:
            return row["named"]
        if role == _GROUP_MEDIA:
            return row["mediaId"]
        if role == _GROUP_FACE:
            return row["faceId"]
        if role == _GROUP_KIND:
            return row["kind"]
        if role == _GROUP_BAND:
            return row.get("band") or ""
        if role == _GROUP_BAND_LABEL:
            return row.get("bandLabel") or ""
        return None

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row(self, subject: str) -> dict | None:
        for item in self._rows:
            if item["subject"] == subject:
                return item
        return None
