"""Plain data types for the dedupe engine (stdlib only, no Semblon imports)."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# SHA-256 is the only confirmation authority. Partial/size stages narrow candidates only.
CONFIRM_ALGORITHM = "sha256"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def is_sha256_hex(value: str) -> bool:
    return bool(_HEX64.match(value or ""))


@dataclass(frozen=True, slots=True)
class FileEntry:
    path: str
    size: int
    mtime_ns: int


@dataclass(slots=True)
class ScanOptions:
    """Discovery filters. ``roots`` walk is only used when no explicit file list is given."""

    roots: list[Path] = field(default_factory=list)
    allowed_extensions: set[str] | None = None  # lowercase, with leading dot
    min_size_bytes: int = 0
    max_size_bytes: int | None = None
    include_hidden: bool = False
    follow_symlinks: bool = False
    scan_subfolders: bool = True
    exclude_dirs: set[str] = field(default_factory=set)  # directory *names*
    exclude_paths: set[str] = field(default_factory=set)  # absolute paths (and everything below)
    max_workers: int = 4


@dataclass(frozen=True, slots=True)
class DuplicateMember:
    path: str
    size: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    """Files whose full SHA-256 is identical. Never built from partial hashes."""

    sha256: str
    members: tuple[DuplicateMember, ...]

    def __post_init__(self) -> None:
        if not is_sha256_hex(self.sha256):
            raise ValueError("DuplicateGroup requires a full SHA-256 hex digest")
        if len(self.members) < 2:
            raise ValueError("DuplicateGroup requires 2+ members")


@dataclass(frozen=True, slots=True)
class ScanEvent:
    stage: str  # discover | size | partial | full | done | cancelled
    done: int = 0
    total: int = 0
    path: str | None = None


EventSink = Callable[[ScanEvent], None]


class CancelToken:
    """Thread-safe cooperative cancellation. ``want_cancel`` callables are adapted to this."""

    def __init__(self, want_cancel: Callable[[], bool] | None = None) -> None:
        self._event = threading.Event()
        self._want = want_cancel

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        if self._event.is_set():
            return True
        if self._want is not None:
            try:
                if self._want():
                    self._event.set()
                    return True
            except Exception:  # noqa: BLE001
                return False
        return False


class ScanCancelled(Exception):
    pass


@dataclass(slots=True)
class ScanStats:
    files_considered: int = 0
    size_candidates: int = 0
    partial_candidates: int = 0
    partial_hashed: int = 0
    full_hashed: int = 0
    cache_hits: int = 0
    unreadable: int = 0
    bytes_read: int = 0
    dirs_scanned: int = 0
    dirs_reused: int = 0


@dataclass(slots=True)
class ScanResult:
    groups: list[DuplicateGroup]
    stats: ScanStats
    cancelled: bool = False
