"""Shared types for experimental inference backends."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TimedEmbed:
    faces: list[dict]
    decode_s: float = 0.0
    view_s: float = 0.0
    detect_s: float = 0.0
    align_s: float = 0.0
    embed_s: float = 0.0
    total_s: float = 0.0
    extras: dict = field(default_factory=dict)


def face_row_to_result(face: np.ndarray, embedding: np.ndarray) -> dict:
    x, y, w, h = float(face[0]), float(face[1]), float(face[2]), float(face[3])
    score = float(face[14]) if face.size > 14 else float(face[-1])
    return {
        "bbox": (x, y, x + w, y + h),
        "det_score": score,
        "face_w": int(w),
        "face_h": int(h),
        "dim": int(embedding.size),
        "embedding": embedding,
        "face_row": np.asarray(face, dtype=np.float32),
    }
