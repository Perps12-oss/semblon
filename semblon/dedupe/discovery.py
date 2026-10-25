"""File discovery: filtered, cancellable, threaded directory walk with optional incremental reuse.

Ported from dedup ``engine/discovery.py`` (UI/DI/profiler removed). Output is a deterministic,
sorted list of ``FileEntry``. Incremental mode (``DiscoveryManifest``) skips ``scandir`` for
directories whose mtime is unchanged; reused files are re-``stat``-ed so size/mtime are never stale.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from queue import Empty, Queue

from .models import CancelToken, FileEntry, ScanOptions, ScanStats
from .path_policy import build_exclusion_keys, canonical_path, is_excluded, is_hidden_name, path_key


def options_fingerprint(options: ScanOptions) -> str:
    return json.dumps(
        {
            "ext": sorted(options.allowed_extensions) if options.allowed_extensions else None,
            "min": options.min_size_bytes,
            "max": options.max_size_bytes,
            "hidden": options.include_hidden,
            "links": options.follow_symlinks,
            "sub": options.scan_subfolders,
            "xd": sorted(options.exclude_dirs),
            "xp": sorted(path_key(p) for p in options.exclude_paths),
        },
        sort_keys=True,
    )


@dataclass(slots=True)
class DirRecord:
    mtime_ns: int
    files: list[str]  # file names directly in the directory that passed name filters
    subdirs: list[str]  # child directory names that passed filters


@dataclass(slots=True)
class DiscoveryManifest:
    """In-memory prior-scan directory index. Persistence is a later, sidecar-only concern."""

    fingerprint: str = ""
    dirs: dict[str, DirRecord] = field(default_factory=dict)


def discover_files(
    options: ScanOptions,
    cancel: CancelToken | None = None,
    *,
    manifest: DiscoveryManifest | None = None,
    stats: ScanStats | None = None,
) -> list[FileEntry]:
    cancel = cancel or CancelToken()
    stats = stats if stats is not None else ScanStats()
    fp = options_fingerprint(options)
    prior = manifest.dirs if manifest is not None and manifest.fingerprint == fp else {}
    new_dirs: dict[str, DirRecord] = {}
    exclusion = build_exclusion_keys(options.exclude_paths)
    exclude_names = {n.lower() for n in options.exclude_dirs}
    exts = {e.lower() for e in options.allowed_extensions} if options.allowed_extensions else None

    lock = threading.Lock()
    found: dict[str, FileEntry] = {}
    work: Queue[str | None] = Queue()
    pending = 0

    def keep_name(name: str) -> bool:
        return options.include_hidden or not is_hidden_name(name)

    def keep_entry(path: str, st: os.stat_result) -> FileEntry | None:
        size = st.st_size
        if size < options.min_size_bytes:
            return None
        if options.max_size_bytes is not None and size > options.max_size_bytes:
            return None
        return FileEntry(path=path, size=size, mtime_ns=st.st_mtime_ns)

    def emit(entry: FileEntry | None) -> None:
        if entry is None:
            return
        with lock:
            found[path_key(entry.path)] = entry

    def visit(directory: str) -> list[str]:
        key = path_key(directory)
        try:
            dir_mtime = os.stat(directory).st_mtime_ns
        except OSError:
            with lock:
                stats.unreadable += 1
            return []
        rec = prior.get(key)
        if rec is not None and rec.mtime_ns == dir_mtime:
            names, subdirs = list(rec.files), list(rec.subdirs)
            with lock:
                stats.dirs_reused += 1
                new_dirs[key] = rec
            for name in names:
                p = os.path.join(directory, name)
                try:
                    st = os.stat(p) if options.follow_symlinks else os.lstat(p)
                except OSError:
                    continue
                if not options.follow_symlinks and os.path.islink(p):
                    continue
                emit(keep_entry(p, st))
            return [os.path.join(directory, s) for s in subdirs]

        files: list[str] = []
        subdirs: list[str] = []
        try:
            it = os.scandir(directory)
        except OSError:
            with lock:
                stats.unreadable += 1
            return []
        with it:
            for de in it:
                if cancel.cancelled:
                    break
                name = de.name
                if not keep_name(name):
                    continue
                try:
                    is_link = de.is_symlink()
                    if is_link and not options.follow_symlinks:
                        continue
                    if de.is_dir(follow_symlinks=options.follow_symlinks):
                        if name.lower() in exclude_names:
                            continue
                        if exclusion and is_excluded(de.path, exclusion):
                            continue
                        subdirs.append(name)
                    elif de.is_file(follow_symlinks=options.follow_symlinks):
                        if exts is not None and os.path.splitext(name)[1].lower() not in exts:
                            continue
                        if exclusion and is_excluded(de.path, exclusion):
                            continue
                        entry = keep_entry(de.path, de.stat(follow_symlinks=options.follow_symlinks))
                        emit(entry)
                        files.append(name)
                except OSError:
                    with lock:
                        stats.unreadable += 1
        with lock:
            stats.dirs_scanned += 1
            if not cancel.cancelled:
                new_dirs[key] = DirRecord(dir_mtime, files, subdirs)
        return [os.path.join(directory, s) for s in subdirs]

    roots = []
    for r in options.roots:
        p = canonical_path(r)
        if p.is_dir() and not (exclusion and is_excluded(p, exclusion)):
            roots.append(str(p))
    if not options.scan_subfolders:
        # Only the root level: visit but never enqueue children.
        for r in roots:
            if cancel.cancelled:
                break
            visit(r)
    else:
        done = threading.Event()
        counter = {"pending": 0}

        def worker() -> None:
            while not done.is_set():
                try:
                    d = work.get(timeout=0.05)
                except Empty:
                    continue
                if d is None:
                    return
                try:
                    children = [] if cancel.cancelled else visit(d)
                    with lock:
                        counter["pending"] += len(children)
                    for c in children:
                        work.put(c)
                finally:
                    with lock:
                        counter["pending"] -= 1
                        if counter["pending"] == 0:
                            done.set()

        counter["pending"] = len(roots)
        if roots:
            for r in roots:
                work.put(r)
            n = max(1, min(int(options.max_workers or 1), 16))
            threads = [threading.Thread(target=worker, daemon=True) for _ in range(n)]
            for t in threads:
                t.start()
            done.wait()
            for t in threads:
                t.join(timeout=1.0)

    if manifest is not None and not cancel.cancelled:
        manifest.fingerprint = fp
        manifest.dirs = new_dirs
    stats.files_considered = len(found)
    return sorted(found.values(), key=lambda e: e.path.lower())


def stat_files(
    paths: Iterable[str | os.PathLike],
    cancel: CancelToken | None = None,
    *,
    stats: ScanStats | None = None,
) -> list[FileEntry]:
    """Explicit file list (Semblon candidate scope). Unreadable/missing paths are skipped and counted."""
    cancel = cancel or CancelToken()
    out: list[FileEntry] = []
    for p in paths:
        if cancel.cancelled:
            break
        try:
            st = os.stat(p)
        except OSError:
            if stats is not None:
                stats.unreadable += 1
            continue
        out.append(FileEntry(path=str(p), size=st.st_size, mtime_ns=st.st_mtime_ns))
    if stats is not None:
        stats.files_considered = len(out)
    return out
