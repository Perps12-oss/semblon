"""Confidence model v1 — versioned so Inc 5+ need not reverse-engineer Inc 4."""

from __future__ import annotations

CONFIDENCE_MODEL_VERSION = 1


def tag_confidence(support_count: int) -> float:
    """Aggregate confidence for a Tag vocabulary node."""
    n = max(0, int(support_count))
    return float(min(1.0, 0.5 + 0.1 * n))


def object_cluster_confidence(member_count: int) -> float:
    """ObjectCluster: strong once ≥3 members; otherwise provisional."""
    return 1.0 if int(member_count) >= 3 else 0.5


def object_cluster_status(member_count: int) -> str:
    return "tentative" if int(member_count) >= 3 else "candidate"


def photo_confidence() -> float:
    return 1.0
