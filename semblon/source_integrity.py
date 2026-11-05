"""I3 — analysis must use the exact bytes whose digest it records.

Read once → hash that buffer → decode that buffer. Never fall back to a second
path read after decode failure. A digest mismatch is a retryable source change,
not a successful analysis.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Keep aligned with semblon.ingest caps (duplicate to avoid import cycles).
MAX_STILL_BYTES = 256 * 1024 * 1024
MAX_IMAGE_PIXELS = 80_000_000

SOURCE_CHANGED_MESSAGE = "Changed during scan — will retry."
SOURCE_CHANGED_OUTCOME = "source_changed"


class SourceIntegrityError(Exception):
    """Base for source-byte integrity failures."""


class SourceChanged(SourceIntegrityError):
    """Path bytes no longer match the digest the library recorded."""


class SourceDecodeError(SourceIntegrityError):
    """Bytes were read but could not be decoded as an image."""


@dataclass(frozen=True)
class SourceBuffer:
    digest: str
    data: bytes
    mtime_ns: int
    byte_size: int


def read_source_buffer(path: Path) -> SourceBuffer:
    """One I/O: bytes + sha256 + mtime_ns + byte_size. Refuses oversized stills."""
    path = Path(path)
    st = path.stat()
    size = int(st.st_size)
    if size > MAX_STILL_BYTES:
        raise OSError("still exceeds byte cap")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    return SourceBuffer(
        digest=digest,
        data=data,
        mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
        byte_size=size,
    )


def _header_pixels(data: bytes) -> int | None:
    """Best-effort pixel count from headers; None when unknown."""
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        # IHDR width/height at bytes 16–23
        import struct

        width, height = struct.unpack(">II", data[16:24])
        return int(width) * int(height)
    if len(data) >= 2 and data[:2] == b"\xff\xd8":
        # Soft gate: JPEG SOF scan is in ingest; here only a cheap refusal.
        return None
    return None


def decode_bgr_buffer(data: bytes) -> np.ndarray | None:
    """Decode BGR from an in-memory buffer only. Never opens a filesystem path."""
    if not data:
        return None
    if len(data) > MAX_STILL_BYTES:
        return None
    pixels = _header_pixels(data)
    if pixels is not None and pixels > MAX_IMAGE_PIXELS:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    img = _orient_display(img, data)
    height, width = img.shape[:2]
    if int(height) * int(width) > MAX_IMAGE_PIXELS:
        return None
    return img


def _orient_display(image: np.ndarray, payload: bytes) -> np.ndarray:
    """Match shell EXIF display when OpenCV did not already apply orientation."""
    if image is None:
        return image
    if hasattr(cv2, "IMREAD_IGNORE_ORIENTATION"):
        return image
    if not payload:
        return image
    try:
        from io import BytesIO

        from PIL import Image, ImageOps
    except Exception:
        return image
    try:
        with Image.open(BytesIO(payload)) as raw:
            exif = raw.getexif()
            orientation = exif.get(0x0112) if exif is not None else None
            if orientation in (None, 0, 1):
                return image
            oriented = ImageOps.exif_transpose(raw)
            rgb = np.asarray(oriented.convert("RGB"))
    except Exception:
        return image
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        return image
    return rgb[:, :, ::-1].copy()


def load_source_bgr(
    path: Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[np.ndarray, SourceBuffer]:
    """Read once, optionally verify digest, decode the same buffer.

    Raises:
        OSError: missing / unreadable / oversize
        SourceChanged: digest does not match expected_sha256
        SourceDecodeError: buffer will not decode
    """
    buf = read_source_buffer(path)
    expected = str(expected_sha256 or "").strip()
    if expected and buf.digest != expected:
        raise SourceChanged(SOURCE_CHANGED_MESSAGE)
    img = decode_bgr_buffer(buf.data)
    if img is None:
        raise SourceDecodeError("The photo could not be read.")
    return img, buf
