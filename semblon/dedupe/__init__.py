"""Isolated exact-duplicate engine (port of the reusable parts of Perps12-oss/dedup).

Pure stdlib. Must not import ``semblon.store``, identity code, or Qt (enforced by tests).
SHA-256 of full file bytes is the only duplicate authority.
"""

from __future__ import annotations

from .deletion import (
    DeletionPlan,
    PlanOutcome,
    execute_plan,
    verify_against_keeper,
    plan_deletions,
    verify_plan,
)
from .discovery import DiscoveryManifest, discover_files, stat_files
from .hashing import MemoryHashCache, full_sha256, partial_sha256
from .models import (
    CONFIRM_ALGORITHM,
    CancelToken,
    DuplicateGroup,
    DuplicateMember,
    FileEntry,
    ScanEvent,
    ScanOptions,
    ScanResult,
    ScanStats,
)
from .pipeline import scan_exact
from .resume import from_checkpoint, to_checkpoint

__all__ = [
    "CONFIRM_ALGORITHM",
    "CancelToken",
    "DeletionPlan",
    "DiscoveryManifest",
    "DuplicateGroup",
    "DuplicateMember",
    "FileEntry",
    "MemoryHashCache",
    "PlanOutcome",
    "ScanEvent",
    "ScanOptions",
    "ScanResult",
    "ScanStats",
    "discover_files",
    "execute_plan",
    "from_checkpoint",
    "full_sha256",
    "partial_sha256",
    "plan_deletions",
    "scan_exact",
    "stat_files",
    "to_checkpoint",
    "verify_against_keeper",
    "verify_plan",
]
