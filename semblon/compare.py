"""compare() contract: pack_id + dim + payload. No clustering here.

ARCH-003 envelope (face identity space only): pack_id is the space key
(family + versions + weight hashes). Dim and l2 payload must match.
Incompatible spaces raise CompareError. A second modality must not
silently vote on identity. buffalo_l is a family name, not the key.
"""

from __future__ import annotations

import struct


class CompareError(ValueError):
    pass


def _norm(vec: bytes, dim: int) -> None:
    if vec is None:
        raise CompareError("NULL embedding")
    if dim is None or dim <= 0:
        raise CompareError("invalid dim")
    if len(vec) != 4 * dim:
        raise CompareError("embedding length != 4 * dim")


def compare(
    pack_a: str,
    dim_a: int,
    blob_a: bytes,
    pack_b: str,
    dim_b: int,
    blob_b: bytes,
) -> float:
    """Identity compare. FaceKit pack_id + dim + payload only."""
    if pack_a != pack_b:
        raise CompareError("pack_id mismatch")
    if dim_a != dim_b:
        raise CompareError("dimension mismatch")
    _norm(blob_a, dim_a)
    _norm(blob_b, dim_b)
    n = dim_a
    a = struct.unpack(f"<{n}f", blob_a)
    b = struct.unpack(f"<{n}f", blob_b)
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
    return compare(pack_a, dim_a, blob_a, pack_b, dim_b, blob_b)
