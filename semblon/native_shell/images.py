"""Thumbnail and focus frames for the archive field.

QML asks for a media id. This provider reads the path from the session and
decodes off the UI thread. It does not open the store from QML and it does
not decode the whole library.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRect, QRunnable, QSize, QThreadPool, Qt, QTimer
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtQuick import QQuickAsyncImageProvider, QQuickImageResponse, QQuickTextureFactory

Lookup = Callable[[str], str | None]
_MISS = object()
_FOCUS_CEILING = 2048
_THUMB_CEILING = 512
_DECODE_COUNT = 0
_DECODE_LOCK = threading.Lock()


class ImageDecodeCache:
    """Bounded decoded frames. Thumbnails and focus frames do not share a size."""

    def __init__(self, max_items: int = 48, max_bytes: int = 96 * 1024 * 1024):
        self._max_items = max_items
        self._max_bytes = max_bytes
        self._items: OrderedDict = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key not in self._items:
                return _MISS
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key, image) -> None:
        weight = _image_bytes(image)
        with self._lock:
            if key in self._items:
                self._bytes -= _image_bytes(self._items.pop(key))
            self._items[key] = image
            self._bytes += weight
            while self._items and (
                len(self._items) > self._max_items or self._bytes > self._max_bytes
            ):
                _key, old = self._items.popitem(last=False)
                self._bytes -= _image_bytes(old)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0


def _image_bytes(image) -> int:
    if image is None or image.isNull():
        return 0
    return int(image.sizeInBytes())


_CACHE = ImageDecodeCache()


def reset_image_cache() -> None:
    global _DECODE_COUNT
    _CACHE.clear()
    with _DECODE_LOCK:
        _DECODE_COUNT = 0


def image_decode_count() -> int:
    with _DECODE_LOCK:
        return _DECODE_COUNT


def _note_decode() -> None:
    global _DECODE_COUNT
    with _DECODE_LOCK:
        _DECODE_COUNT += 1


def _cache_key(path: str, max_side: int):
    file = Path(path) if path else None
    if file is None or not file.is_file():
        return None
    try:
        stat = file.stat()
    except OSError:
        return None
    return (str(file.resolve()), int(stat.st_mtime_ns), int(stat.st_size), int(max_side))


def _video_frame(path: Path, max_side: int) -> QImage:
    """First decoded frame. This is not a player."""
    try:
        import cv2

        from semblon.temporal import read_bgr
    except Exception:
        return QImage()
    frame = read_bgr(path, frame_id=0)
    if frame is None:
        return QImage()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    if max_side > 0:
        longest = max(width, height, 1)
        scale = min(1.0, float(max_side) / float(longest))
        if scale < 1.0:
            rgb = cv2.resize(
                rgb,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
            height, width = rgb.shape[:2]
    image = QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888)
    return image.copy()


class _Decode(QRunnable):
    def __init__(self, response: "ArchiveImageResponse", path: str, max_side: int):
        super().__init__()
        self._response = response
        self._path = path
        self._max_side = max_side

    def run(self) -> None:
        if self._response.cancelled:
            self._response.finished.emit()
            return
        key = _cache_key(self._path, self._max_side)
        cached = _CACHE.get(key) if key is not None else _MISS
        if cached is not _MISS:
            if not self._response.cancelled:
                self._response._image = cached
            self._response.finished.emit()
            return
        _note_decode()
        image = QImage()
        file = Path(self._path) if self._path else None
        if file is not None and file.is_file() and file.suffix.lower() in {
            ".mp4",
            ".mov",
            ".avi",
            ".mkv",
            ".webm",
            ".m4v",
        }:
            image = _video_frame(file, self._max_side)
        elif file is not None and file.is_file():
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
        if key is not None:
            _CACHE.put(key, image)
        if not self._response.cancelled:
            self._response._image = image
        self._response.finished.emit()


class ArchiveImageResponse(QQuickImageResponse):
    def __init__(self, path: str, max_side: int):
        super().__init__()
        self._image = QImage()
        self._path = path
        self._max_side = max_side
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def start(self) -> None:
        """Decode after Qt has connected ``finished``. An immediate thread can finish first."""
        key = _cache_key(self._path, self._max_side)
        cached = _CACHE.get(key) if key is not None else _MISS
        if cached is not _MISS:
            self._image = cached
            QTimer.singleShot(0, self.finished.emit)
            return
        QThreadPool.globalInstance().start(_Decode(self, self._path, self._max_side))

    def textureFactory(self):
        return QQuickTextureFactory.textureFactoryForImage(self._image)


class _CropFace(QRunnable):
    def __init__(self, response: "FaceCropImageResponse", path: str, bbox: tuple[int, int, int, int], max_side: int):
        super().__init__()
        self._response = response
        self._path = path
        self._bbox = bbox
        self._max_side = max_side

    def run(self) -> None:
        image = QImage()
        file = Path(self._path) if self._path else None
        if self._response.cancelled:
            self._response.finished.emit()
            return
        if file is not None and file.is_file():
            reader = QImageReader(str(file))
            reader.setAutoTransform(True)
            x, y, w, h = self._bbox
            size = reader.size()
            if size.isValid() and size.width() > 0 and size.height() > 0:
                x = max(0, min(size.width() - 1, int(x)))
                y = max(0, min(size.height() - 1, int(y)))
                w = max(1, int(w))
                h = max(1, int(h))
                if x + w > size.width():
                    w = max(1, size.width() - x)
                if y + h > size.height():
                    h = max(1, size.height() - y)
                # Clip before decode. setScaledSize would distort the bbox.
                reader.setClipRect(QRect(x, y, w, h))
            loaded = reader.read()
            if self._response.cancelled:
                self._response.finished.emit()
                return
            if not loaded.isNull():
                crop = loaded
                if not size.isValid():
                    x = max(0, min(max(0, loaded.width() - 1), int(x)))
                    y = max(0, min(max(0, loaded.height() - 1), int(y)))
                    w = max(1, int(w))
                    h = max(1, int(h))
                    if x + w > loaded.width():
                        w = max(1, loaded.width() - x)
                    if y + h > loaded.height():
                        h = max(1, loaded.height() - y)
                    crop = loaded.copy(x, y, w, h)
                if not crop.isNull():
                    if self._max_side > 0 and max(crop.width(), crop.height()) > self._max_side:
                        crop = crop.scaled(
                            QSize(self._max_side, self._max_side),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    image = crop
                else:
                    image = loaded
        if not self._response.cancelled:
            self._response._image = image
        self._response.finished.emit()


class FaceCropImageResponse(QQuickImageResponse):
    def __init__(self, path: str, bbox: tuple[int, int, int, int], max_side: int):
        super().__init__()
        self._image = QImage()
        self._path = path
        self._bbox = bbox
        self._max_side = max_side
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def start(self) -> None:
        QThreadPool.globalInstance().start(_CropFace(self, self._path, self._bbox, self._max_side))

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
        ceiling = _FOCUS_CEILING if kind == "f" else _THUMB_CEILING
        max_side = 1600 if kind == "f" else 480
        if requestedSize is not None and requestedSize.isValid():
            max_side = max(requestedSize.width(), requestedSize.height(), 1)
        max_side = min(int(max_side), ceiling)
        response = ArchiveImageResponse(path, max_side)
        response.start()
        return response


class FaceCropImageProvider(QQuickAsyncImageProvider):
    """image://face/<face_id> face crop thumbnail."""

    def __init__(self, lookup: Callable[[str], dict | None]):
        super().__init__()
        self._lookup = lookup

    def requestImageResponse(self, image_id: str, requestedSize):
        face_id = str(image_id)
        spec = self._lookup(face_id) or {}
        path = str(spec.get("path") or "")
        bbox = spec.get("bbox") or (0, 0, 1, 1)
        try:
            x, y, w, h = (int(float(v)) for v in bbox[:4])
        except Exception:
            x, y, w, h = 0, 0, 1, 1
        max_side = 160
        if requestedSize is not None and requestedSize.isValid():
            max_side = max(requestedSize.width(), requestedSize.height(), 1)
        response = FaceCropImageResponse(path, (x, y, w, h), max_side)
        response.start()
        return response
