"""compare() contract: pack_id + dim + payload. No clustering here.

ARCH-003 envelope (face identity space only): pack_id is the space key
(family + versions + weight hashes). Dim and l2 payload must match.
Incompatible spaces raise CompareError. A second modality must not
silently vote on identity. buffalo_l is a family name, not the key.

P1 I1: non-finite values, empty pack, and non-l2 face payloads fail closed.
Non-face compare_space refuses face and still rejects non-finite payloads,
but does not require L2 (region/object spaces are not the identity contract).
"""

from __future__ import annotations

import math
import struct

# Absolute deviation from unit L2 allowed for float32 pack/unpack noise.
L2_TOLERANCE = 1e-3


class CompareError(ValueError):
    pass


def _norm(vec: bytes, dim: int) -> None:
    if vec is None:
        raise CompareError("NULL embedding")
    if dim is None or dim <= 0:
        raise CompareError("invalid dim")
    if len(vec) != 4 * dim:
        raise CompareError("embedding length != 4 * dim")


def _require_pack(pack_id: str) -> str:
    if not isinstance(pack_id, str) or not pack_id.strip():
        raise CompareError("empty pack_id")
    return pack_id


def unpack_embedding(blob: bytes, dim: int) -> tuple[float, ...]:
    """Unpack float32 embedding and refuse non-finite components."""
    _norm(blob, dim)
    values = struct.unpack(f"<{dim}f", blob)
    if not all(math.isfinite(x) for x in values):
        raise CompareError("non-finite embedding")
    return values


def l2_norm(values: tuple[float, ...] | list[float]) -> float:
    return math.sqrt(sum(x * x for x in values))


def validate_identity_embedding(pack_id: str, dim: int, blob: bytes) -> tuple[float, ...]:
    """Fail-closed face identity vector contract. Shared by compare and persist gates."""
    _require_pack(pack_id)
    values = unpack_embedding(blob, dim)
    norm = l2_norm(values)
    if not math.isfinite(norm) or abs(norm - 1.0) > L2_TOLERANCE:
        raise CompareError("embedding not l2-normalised")
    return values


def require_finite_threshold(threshold: float) -> float:
    """Identity policy threshold: finite and in [0, 1]. Does not change DEFAULT_THRESHOLD."""
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise CompareError("invalid threshold")
    value = float(threshold)
    if not math.isfinite(value):
        raise CompareError("non-finite threshold")
    if value < 0.0 or value > 1.0:
        raise CompareError("threshold out of range")
    return value


def _dot(pack_a: str, dim_a: int, blob_a: bytes, pack_b: str, dim_b: int, blob_b: bytes) -> float:
    pack_a = _require_pack(pack_a)
    pack_b = _require_pack(pack_b)
    if pack_a != pack_b:
        raise CompareError("pack_id mismatch")
    if dim_a != dim_b:
        raise CompareError("dimension mismatch")
    a = unpack_embedding(blob_a, dim_a)
    b = unpack_embedding(blob_b, dim_b)
    return float(sum(x * y for x, y in zip(a, b)))


def compare(
    pack_a: str,
    dim_a: int,
    blob_a: bytes,
    pack_b: str,
    dim_b: int,
    blob_b: bytes,
) -> float:
    """Identity compare. FaceKit pack_id + dim + l2 payload only."""
    pack_a = _require_pack(pack_a)
    pack_b = _require_pack(pack_b)
    if pack_a != pack_b:
        raise CompareError("pack_id mismatch")
    if dim_a != dim_b:
        raise CompareError("dimension mismatch")
    a = validate_identity_embedding(pack_a, dim_a, blob_a)
    b = validate_identity_embedding(pack_b, dim_b, blob_b)
    return float(sum(x * y for x, y in zip(a, b)))


def compare_space(
    modality_a: str,
    pack_a: str,
    dim_a: int,
    blob_a: bytes,
    modality_b: str,
    pack_b: str,
    dim_b: int,
    blob_b: bytes,
) -> float:
    """Non-identity similarity. Incompatible spaces never compare. Not a person score."""
    if not modality_a or modality_a != modality_b:
        raise CompareError("modality mismatch")
    if modality_a == "face":
        raise CompareError("face identity must use compare(), not compare_space()")
    return _dot(pack_a, dim_a, blob_a, pack_b, dim_b, blob_b)
