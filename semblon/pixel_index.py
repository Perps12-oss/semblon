"""Pixel → segment index for instantaneous hover lookup.

Hot path: (x, y) → segment_id. No model, no SQLite, no polygon math.
Map is in source-image coordinates (uint16; 0 = none).
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

import numpy as np

from semblon.visual_segment import VisualSegment


@dataclass
class PixelSegmentIndex:
    """Dense per-pixel segment id map + id→VisualSegment table."""

    height: int
    width: int
    # 0 = no segment; else 1-based index into `order`
    map: np.ndarray
    order: list[str]  # segment_id by index (1-based into map values)
    by_id: dict[str, VisualSegment]

    def lookup(self, x: int, y: int) -> VisualSegment | None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return None
        idx = int(self.map[y, x])
        if idx <= 0 or idx > len(self.order):
            return None
        sid = self.order[idx - 1]
        return self.by_id.get(sid)

    def coverage_frac(self) -> float:
        if self.map.size == 0:
            return 0.0
        return float(np.count_nonzero(self.map)) / float(self.map.size)

    def labelled_frac(self) -> float:
        if not self.order:
            return 0.0
        n = sum(
            1
            for sid in self.order
            if (self.by_id.get(sid) and (self.by_id[sid].label or "").strip())
        )
        return n / float(len(self.order))


def build_pixel_index(
    segments: list[VisualSegment],
    *,
    height: int,
    width: int,
    masks: dict[str, np.ndarray] | None = None,
) -> PixelSegmentIndex:
    """Paint segments into a map. Smaller / child regions overwrite parents."""
    masks = masks or {}
    flat = np.zeros((height, width), dtype=np.uint16)
    # Paint large → small so finer regions win at overlapping pixels.
    ordered = sorted(
        enumerate(segments),
        key=lambda t: (
            -(t[1].bbox[2] - t[1].bbox[0]) * (t[1].bbox[3] - t[1].bbox[1])
        ),
    )
    order: list[str] = []
    by_id: dict[str, VisualSegment] = {}
    for paint_i, (_orig_i, seg) in enumerate(ordered, start=1):
        if paint_i > 65535:
            break
        order.append(seg.segment_id)
        by_id[seg.segment_id] = seg
        x1, y1, x2, y2 = seg.bbox
        ix1 = int(max(0, min(width, round(x1))))
        iy1 = int(max(0, min(height, round(y1))))
        ix2 = int(max(0, min(width, round(x2))))
        iy2 = int(max(0, min(height, round(y2))))
        if ix2 <= ix1 or iy2 <= iy1:
            continue
        mask = masks.get(seg.segment_id)
        if mask is not None and mask.shape[:2] == (height, width):
            flat[mask.astype(bool)] = paint_i
        elif mask is not None and mask.shape[:2] == (iy2 - iy1, ix2 - ix1):
            sub = flat[iy1:iy2, ix1:ix2]
            sub[mask.astype(bool)] = paint_i
        else:
            flat[iy1:iy2, ix1:ix2] = paint_i
    return PixelSegmentIndex(
        height=height, width=width, map=flat, order=order, by_id=by_id
    )


MAGIC = b"SVPI1\n"


def encode_index(index: PixelSegmentIndex) -> bytes:
    """Compact zlib payload for cache sidecars (map only; segments stored as JSON)."""
    header = struct.pack("<II", index.height, index.width)
    body = zlib.compress(index.map.tobytes(), level=6)
    order_blob = ("\n".join(index.order)).encode("utf-8")
    return MAGIC + header + struct.pack("<I", len(order_blob)) + order_blob + body


def decode_map(blob: bytes, order: list[str]) -> np.ndarray:
    if not blob.startswith(MAGIC):
        raise ValueError("bad pixel index magic")
    off = len(MAGIC)
    height, width = struct.unpack_from("<II", blob, off)
    off += 8
    (n_order,) = struct.unpack_from("<I", blob, off)
    off += 4
    order_blob = blob[off : off + n_order].decode("utf-8")
    off += n_order
    parsed = [line for line in order_blob.split("\n") if line]
    if order and parsed and parsed != order:
        # Prefer embedded order when present.
        order[:] = parsed
    raw = zlib.decompress(blob[off:])
    return np.frombuffer(raw, dtype=np.uint16).reshape((height, width)).copy()
