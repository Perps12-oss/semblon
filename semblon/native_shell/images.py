"""Thumbnail and focus frames for the archive field.

QML asks for a media id. This provider reads the path from the session and
decodes off the UI thread. It does not open the store from QML and it does
not decode the whole library.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRunnable, QSize, QThreadPool, QTimer
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtQuick import QQuickAsyncImageProvider, QQuickImageResponse, QQuickTextureFactory

Lookup = Callable[[str], str | None]


class _Decode(QRunnable):
    def __init__(self, response: "ArchiveImageResponse", path: str, max_side: int):
        super().__init__()
        self._response = response
        self._path = path
        self._max_side = max_side

    def run(self) -> None:
        image = QImage()
        file = Path(self._path) if self._path else None
        if file is not None and file.is_file():
            reader = QImageReader(str(file))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid() and self._max_side > 0:
                longest = max(size.width(), size.height(), 1)
                scale = min(1.0, float(self._max_side) / float(longest))
                reader.setScaledSize(
                    QSize(
                        max(1, int(size.width() * scale)),
                        max(1, int(size.height() * scale)),
                    )
                )
            loaded = reader.read()
            if not loaded.isNull():
                image = loaded
        self._response._image = image
        self._response.finished.emit()


class ArchiveImageResponse(QQuickImageResponse):
    def __init__(self, path: str, max_side: int):
        super().__init__()
        self._image = QImage()
        self._path = path
        self._max_side = max_side

    def start(self) -> None:
        """Decode after Qt has connected ``finished``. An immediate thread can finish first."""
        QThreadPool.globalInstance().start(_Decode(self, self._path, self._max_side))

    def textureFactory(self):
        return QQuickTextureFactory.textureFactoryForImage(self._image)


class ArchiveImageProvider(QQuickAsyncImageProvider):
    """image://archive/t/<id> thumb, image://archive/f/<id> focus frame."""

    def __init__(self, lookup: Lookup):
        super().__init__()
        self._lookup = lookup

    def requestImageResponse(self, image_id: str, requestedSize):
        kind, _, media_id = str(image_id).partition("/")
        path = self._lookup(media_id) or ""
        max_side = 1600 if kind == "f" else 480
        if requestedSize is not None and requestedSize.isValid():
            max_side = max(requestedSize.width(), requestedSize.height(), 1)
        response = ArchiveImageResponse(path, max_side)
        QTimer.singleShot(0, response.start)
        return response
