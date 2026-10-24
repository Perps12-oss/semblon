"""Thumbnail and focus frames for the archive field.

QML asks for a media id. This provider reads the path from the session and
decodes off the UI thread. It does not open the store from QML and it does
not decode the whole library.
"""

from __future__ import annotations

import hashlib
import shutil
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
_THUMB_DISK = 384
_TINY_DISK = 96
_DECODE_COUNT = 0
_DECODE_LOCK = threading.Lock()
_DISK_LOCK = threading.Lock()


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


_THUMB_CACHE = ImageDecodeCache(max_items=240, max_bytes=80 * 1024 * 1024)
_FOCUS_CACHE = ImageDecodeCache(max_items=8, max_bytes=96 * 1024 * 1024)


def thumb_cache_dir(store: Path) -> Path:
    """Small JPEGs beside the store. Originals are not written."""
    store = Path(store)
    return store.with_name(store.stem + ".thumbs")


def clear_thumb_cache(store: Path) -> None:
    directory = thumb_cache_dir(store)
    if directory.is_dir():
        shutil.rmtree(directory, ignore_errors=True)


def reset_image_cache() -> None:
    global _DECODE_COUNT
    clear_decoded_frames()
    with _DECODE_LOCK:
        _DECODE_COUNT = 0


def clear_decoded_frames() -> None:
    _THUMB_CACHE.clear()
    _FOCUS_CACHE.clear()


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


def _disk_thumb_path(cache_dir: Path, key) -> Path:
    digest = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()
    return Path(cache_dir) / digest[:2] / f"{digest}.jpg"


def _read_disk_thumb(path: Path) -> QImage:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    loaded = reader.read()
    if loaded.isNull():
        return QImage()
    return loaded


def _write_disk_thumb(path: Path, image: QImage) -> None:
    if image.isNull():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".jpg.part")
    with _DISK_LOCK:
        if image.save(str(partial), "JPEG", 82):
            partial.replace(path)
        elif partial.is_file():
            partial.unlink(missing_ok=True)


def _decode_original(path: str, max_side: int) -> QImage:
    image = QImage()
    file = Path(path) if path else None
    if file is not None and file.is_file() and file.suffix.lower() in {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".m4v",
    }:
        return _video_frame(file, max_side)
    if file is None or not file.is_file():
        return image
    reader = QImageReader(str(file))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max_side > 0:
        longest = max(size.width(), size.height(), 1)
        scale = min(1.0, float(max_side) / float(longest))
        reader.setScaledSize(
            QSize(
                max(1, int(size.width() * scale)),
                max(1, int(size.height() * scale)),
            )
        )
    loaded = reader.read()
    if not loaded.isNull():
        image = loaded
    return image


def _memory_cache(thumb: bool) -> ImageDecodeCache:
    return _THUMB_CACHE if thumb else _FOCUS_CACHE


def peek_display_image(path: str, max_side: int, *, cache_dir: Path | None) -> QImage | object:
    """Return a decoded frame already in memory, or ``_MISS``."""
    thumb = cache_dir is not None and max_side <= _THUMB_CEILING
    side = min(max_side, _THUMB_DISK) if thumb else max_side
    key = _cache_key(path, side)
    if key is None:
        return _MISS
    return _memory_cache(thumb).get(key)


def load_display_image(path: str, max_side: int, *, cache_dir: Path | None = None) -> QImage:
    """Thumbnails prefer a small JPEG beside the store. Focus frames stay in memory."""
    thumb = cache_dir is not None and max_side <= _THUMB_CEILING
    side = min(max_side, _THUMB_DISK) if thumb else max_side
    key = _cache_key(path, side)
    cache = _memory_cache(thumb)
    cached = cache.get(key) if key is not None else _MISS
    if cached is not _MISS:
        return cached
    image = QImage()
    disk_path = _disk_thumb_path(cache_dir, key) if thumb and key is not None and cache_dir else None
    if disk_path is not None and disk_path.is_file():
        image = _read_disk_thumb(disk_path)
    if image.isNull():
        _note_decode()
        image = _decode_original(path, side)
        if disk_path is not None and not image.isNull():
            _write_disk_thumb(disk_path, image)
    if key is not None:
        cache.put(key, image)
    return image


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
    def __init__(self, response: "ArchiveImageResponse", path: str, max_side: int, cache_dir: Path | None):
        super().__init__()
        self._response = response
        self._path = path
        self._max_side = max_side
        self._cache_dir = cache_dir

    def run(self) -> None:
        if self._response.cancelled:
            self._response.finished.emit()
            return
        image = load_display_image(self._path, self._max_side, cache_dir=self._cache_dir)
        if not self._response.cancelled:
            self._response._image = image
        self._response.finished.emit()


class ArchiveImageResponse(QQuickImageResponse):
    def __init__(self, path: str, max_side: int, cache_dir: Path | None = None):
        super().__init__()
        self._image = QImage()
        self._path = path
        self._max_side = max_side
        self._cache_dir = cache_dir
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def start(self) -> None:
        """Decode after Qt has connected ``finished``. An immediate thread can finish first."""
        cached = peek_display_image(self._path, self._max_side, cache_dir=self._cache_dir)
        if cached is not _MISS:
            self._image = cached
            QTimer.singleShot(0, self.finished.emit)
            return
        QThreadPool.globalInstance().start(_Decode(self, self._path, self._max_side, self._cache_dir))

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

    def __init__(self, lookup: Lookup, cache_dir: Path | None = None):
        super().__init__()
        self._lookup = lookup
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None

    def requestImageResponse(self, image_id: str, requestedSize):
        kind, _, media_id = str(image_id).partition("/")
        path = self._lookup(media_id) or ""
        if kind in ("t", "s"):
            # Two disk tiers: 96px for far-out zoom, 384px for everything closer.
            max_side = _TINY_DISK if kind == "s" else _THUMB_DISK
            cache_dir = self._cache_dir
        else:
            ceiling = _FOCUS_CEILING
            max_side = 1600
            if requestedSize is not None and requestedSize.isValid():
                max_side = max(requestedSize.width(), requestedSize.height(), 1)
            max_side = min(int(max_side), ceiling)
            cache_dir = None
        response = ArchiveImageResponse(path, max_side, cache_dir)
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
