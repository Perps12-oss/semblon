"""Exact grouping from staged candidates. Pure functions, no I/O."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import DuplicateGroup, DuplicateMember, FileEntry


def size_candidates(entries: Iterable[FileEntry]) -> list[FileEntry]:
    """Entries sharing a byte size with at least one other entry (files of unique size can't match)."""
    buckets: dict[int, list[FileEntry]] = defaultdict(list)
    for e in entries:
        buckets[e.size].append(e)
    out: list[FileEntry] = []
    for size in sorted(buckets):
        if len(buckets[size]) >= 2:
            out.extend(buckets[size])
    return out


def narrow_by_digest(
    entries: Iterable[FileEntry], digests: dict[str, str]
) -> list[FileEntry]:
    """Keep entries that share a (size, digest) bucket with another entry. Reduction only."""
    buckets: dict[tuple[int, str], list[FileEntry]] = defaultdict(list)
    for e in entries:
        d = digests.get(e.path)
        if d is not None:
            buckets[(e.size, d)].append(e)
    out: list[FileEntry] = []
    for key in sorted(buckets):
        if len(buckets[key]) >= 2:
            out.extend(buckets[key])
    return out


def group_by_full_sha256(
    items: Iterable[tuple[FileEntry, str]],
) -> list[DuplicateGroup]:
    """Group by full SHA-256. Duplicate paths collapse; groups need 2+ distinct paths."""
    buckets: dict[str, dict[str, FileEntry]] = defaultdict(dict)
    for entry, digest in items:
        buckets[digest][entry.path] = entry
    groups: list[DuplicateGroup] = []
    for digest, by_path in buckets.items():
        if len(by_path) < 2:
            continue
        members = tuple(
            DuplicateMember(e.path, e.size, e.mtime_ns)
            for e in sorted(by_path.values(), key=lambda e: e.path.lower())
        )
        groups.append(DuplicateGroup(digest, members))
    groups.sort(key=lambda g: (-len(g.members), g.sha256))
    return groups
