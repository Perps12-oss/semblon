"""Staged hashing: size -> partial -> full. SHA-256 only.

Ported from dedup ``engine/hashing.py`` with its XXHash64/MD5/BLAKE3 strategies removed on
purpose. The partial digest is SHA-256 over sampled slices (+ size) and exists only to shrink the
candidate set; only ``full_sha256`` may confirm two files as identical.
"""

from __future__ import annotations

import hashlib
import os
import threading
from typing import Protocol

from .models import CancelToken, FileEntry, ScanCancelled

CHUNK = 1 << 20
PARTIAL_SAMPLE = 64 * 1024
PARTIAL_VERSION = "v1"


class ByteMeter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.bytes_read = 0

    def add(self, n: int) -> None:
        with self._lock:
            self.bytes_read += n


class HashCache(Protocol):
    def get(self, kind: str, entry: FileEntry) -> str | None: ...

    def put(self, kind: str, entry: FileEntry, digest: str) -> None: ...


class MemoryHashCache:
    """Keyed by (path, size, mtime_ns, kind): a changed file never reuses a stale digest."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[tuple[str, int, int, str], str] = {}

    @staticmethod
    def _key(kind: str, e: FileEntry) -> tuple[str, int, int, str]:
        return (os.path.normcase(e.path), e.size, e.mtime_ns, kind)

    def get(self, kind: str, entry: FileEntry) -> str | None:
        with self._lock:
            return self._data.get(self._key(kind, entry))

    def put(self, kind: str, entry: FileEntry, digest: str) -> None:
        with self._lock:
            self._data[self._key(kind, entry)] = digest

    def __len__(self) -> int:
        return len(self._data)

    def export(self) -> list[list]:
        with self._lock:
            return [[p, s, m, k, d] for (p, s, m, k), d in self._data.items()]

    @classmethod
    def load(cls, rows: list[list]) -> MemoryHashCache:
        c = cls()
        for p, s, m, k, d in rows:
            c._data[(p, int(s), int(m), k)] = d
        return c


def partial_kind(sample: int) -> str:
    return f"partial-sha256-{PARTIAL_VERSION}-{sample}"


FULL_KIND = "full-sha256"


def _check(cancel: CancelToken | None) -> None:
    if cancel is not None and cancel.cancelled:
        raise ScanCancelled


def full_sha256(
    path: str, *, meter: ByteMeter | None = None, cancel: CancelToken | None = None
) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            _check(cancel)
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
            if meter is not None:
                meter.add(len(chunk))
    return h.hexdigest()


def partial_sha256(
    path: str,
    size: int,
    *,
    sample: int = PARTIAL_SAMPLE,
    meter: ByteMeter | None = None,
    cancel: CancelToken | None = None,
) -> str:
    """SHA-256 over size + first/middle/last ``sample`` bytes. Candidate reduction only."""
    _check(cancel)
    h = hashlib.sha256()
    h.update(size.to_bytes(8, "little"))
    offsets = [0, max(0, size // 2 - sample // 2), max(0, size - sample)]
    seen: set[int] = set()
    with open(path, "rb") as f:
        for off in offsets:
            if off in seen:
                continue
            seen.add(off)
            f.seek(off)
            data = f.read(sample)
            h.update(data)
            if meter is not None:
                meter.add(len(data))
    return h.hexdigest()


def partial_is_useful(size: int, sample: int = PARTIAL_SAMPLE) -> bool:
    """Below ~3 samples the partial read costs as much as a full read; go straight to full."""
    return size > sample * 3
