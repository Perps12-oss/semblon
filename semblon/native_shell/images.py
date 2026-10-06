"""Thumbnail, focus frames, and face crops for the archive.

QML asks for a media id or a face id. This provider reads the path from the
session and decodes off the UI thread. It does not open the store from QML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRunnable, QSize, QThreadPool, QTimer
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtQuick import QQuickAsyncImageProvider, QQuickImageResponse, QQuickTextureFactory

Lookup = Callable[[str], str | None]
BoxLookup = Callable[[str], tuple | None]


def face_crop_qimage(path: str, box: tuple) -> QImage:
    """Crop a detector box, then apply the same orientation the photo uses on screen."""
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        return QImage()
    height, width = image.shape[:2]
    try:
        x1, y1, x2, y2 = (int(box[0]), int(box[1]), int(box[2]), int(box[3]))
    except (TypeError, ValueError, IndexError):
        return QImage()
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    pad_x = max(4, int((x2 - x1) * 0.18))
    pad_y = max(4, int((y2 - y1) * 0.18))
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(width, x2 + pad_x)
    y2 = min(height, y2 + pad_y)
    if x2 <= x1 or y2 <= y1:
        return QImage()
    crop = image[y1:y2, x1:x2]
    return _qimage_from_bgr(_orient_crop(path, crop))


def _orient_crop(path: str, crop):
    """EXIF is a whole-image transform. Applying it to the raw crop matches the displayed photo."""
    try:
        from PIL import Image, ImageOps
        import numpy as np
    except Exception:
        return crop
    try:
        with Image.open(path) as raw:
            orientation = raw.getexif().get(274)
        if not orientation or int(orientation) == 1:
            return crop
        rgb = crop[:, :, ::-1]
        pil = Image.fromarray(rgb)
        exif = Image.Exif()
        exif[274] = int(orientation)
        pil.info["exif"] = exif.tobytes()
        turned = ImageOps.exif_transpose(pil)
        if turned is None:
            return crop
        out = np.asarray(turned.convert("RGB"))
        return out[:, :, ::-1].copy()
    except Exception:
        return crop


def _qimage_from_bgr(crop) -> QImage:
    import numpy as np

    rgb = np.ascontiguousarray(crop[:, :, ::-1])
    height, width = rgb.shape[:2]
    image = QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888)
    return image.copy()


class _Decode(QRunnable):
    def __init__(self, response: "ArchiveImageResponse", path: str, max_side: int, box: tuple | None = None):
        super().__init__()
        self._response = response
        self._path = path
        self._max_side = max_side
        self._box = box

    def run(self) -> None:
        image = QImage()
        file = Path(self._path) if self._path else None
        if file is not None and file.is_file():
            if self._box is not None:
                image = face_crop_qimage(str(file), self._box)
            else:
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
    def __init__(self, path: str, max_side: int, box: tuple | None = None):
        super().__init__()
        self._image = QImage()
        self._path = path
        self._max_side = max_side
        self._box = box

    def start(self) -> None:
        """Decode after Qt has connected ``finished``. An immediate thread can finish first."""
        QThreadPool.globalInstance().start(_Decode(self, self._path, self._max_side, self._box))

    def textureFactory(self):
        return QQuickTextureFactory.textureFactoryForImage(self._image)


class ArchiveImageProvider(QQuickAsyncImageProvider):
    """image://archive/t/<id> thumb, image://archive/f/<id> focus, image://archive/c/<face> crop."""

    def __init__(self, lookup: Lookup, face_box: BoxLookup | None = None):
        super().__init__()
        self._lookup = lookup
        self._face_box = face_box

    def requestImageResponse(self, image_id: str, requestedSize):
        kind, _, ident = str(image_id).partition("/")
        box = None
        if kind == "c" and self._face_box is not None:
            spec = self._face_box(ident)
            path = str(spec[0]) if spec else ""
            box = spec[1] if spec else None
        else:
            path = self._lookup(ident) or ""
        max_side = 1600 if kind == "f" else 320
        if requestedSize is not None and requestedSize.isValid():
            max_side = max(requestedSize.width(), requestedSize.height(), 1)
        response = ArchiveImageResponse(path, max_side, box)
        QTimer.singleShot(0, response.start)
        return response
