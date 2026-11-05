"""Canonical embedding helpers — int8 quantised centroids."""

from __future__ import annotations

import numpy as np


def mean_l2_int8(vectors: list[bytes], dim: int) -> bytes:
    """Mean of float32 L2 vectors → re-L2 → int8 in [-127, 127]."""
    if not vectors:
        raise ValueError("empty vector list")
    arr = np.stack(
        [np.frombuffer(v, dtype=np.float32).copy() for v in vectors],
        axis=0,
    )
    if arr.shape[1] != dim:
        raise ValueError(f"dim mismatch: expected {dim}, got {arr.shape[1]}")
    mean = arr.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm > 0:
        mean = mean / norm
    q = np.clip(np.round(mean * 127.0), -127, 127).astype(np.int8)
    return q.tobytes()
