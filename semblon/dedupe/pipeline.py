"""Scan coordinator: discovery -> size -> partial -> full SHA-256, with events and cancellation.

Isolated pure-Python engine. SHA-256 of the full file bytes is the only thing that confirms a
duplicate; size and partial stages only decide which files are worth fully hashing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from os import PathLike

from .discovery import DiscoveryManifest, discover_files, stat_files
from .grouping import group_by_full_sha256, narrow_by_digest, size_candidates
from .hashing import (
    FULL_KIND,
    PARTIAL_SAMPLE,
    ByteMeter,
    HashCache,
    MemoryHashCache,
    full_sha256,
    partial_is_useful,
    partial_kind,
    partial_sha256,
)
from .models import (
    CancelToken,
    EventSink,
    FileEntry,
    ScanCancelled,
    ScanEvent,
    ScanOptions,
    ScanResult,
    ScanStats,
    is_sha256_hex,
)


def scan_exact(
    files: Iterable[str | PathLike] | None = None,
    options: ScanOptions | None = None,
    *,
    extra_digests: dict[str, str] | None = None,
    cache: HashCache | None = None,
    manifest: DiscoveryManifest | None = None,
    cancel: CancelToken | None = None,
    want_cancel: Callable[[], bool] | None = None,
    on_event: EventSink | None = None,
    workers: int | None = None,
    partial_sample: int = PARTIAL_SAMPLE,
) -> ScanResult:
    """Find exact duplicates.

    ``files`` is an explicit candidate list (Semblon's scope); otherwise ``options.roots`` is walked.
    ``extra_digests`` maps paths that are not readable on disk to a known SHA-256 (library fallback);
    they join grouping without being re-hashed.
    """
    cancel = cancel or CancelToken(want_cancel)
    options = options or ScanOptions()
    stats = ScanStats()
    meter = ByteMeter()
    cache = cache if cache is not None else MemoryHashCache()
    n_workers = max(1, int(workers or options.max_workers or 1))

    def emit(stage: str, done: int = 0, total: int = 0, path: str | None = None) -> None:
        if on_event is not None:
            try:
                on_event(ScanEvent(stage, done, total, path))
            except Exception:  # noqa: BLE001
                pass

    def finish(groups, cancelled=False) -> ScanResult:
        stats.bytes_read = meter.bytes_read
        emit("cancelled" if cancelled else "done", stats.files_considered, stats.files_considered)
        return ScanResult(groups=groups, stats=stats, cancelled=cancelled)

    emit("discover")
    if files is not None:
        entries = stat_files(files, cancel, stats=stats)
    else:
        entries = discover_files(options, cancel, manifest=manifest, stats=stats)
    extra = {
        p: d.lower() for p, d in (extra_digests or {}).items() if is_sha256_hex((d or "").lower())
    }
    stats.files_considered += len(extra)
    if cancel.cancelled:
        return finish([], True)

    def run_stage(stage: str, items: list[FileEntry], fn) -> dict[str, str]:
        results: dict[str, str] = {}
        total = len(items)
        if not total:
            return results
        done = 0

        def job(e: FileEntry):
            if cancel.cancelled:
                raise ScanCancelled
            return e, fn(e)

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(job, e) for e in items]
            for fut in futures:
                try:
                    e, digest = fut.result()
                except ScanCancelled:
                    cancel.cancel()
                    continue
                except OSError:
                    stats.unreadable += 1
                    continue
                finally:
                    done += 1
                    emit(stage, done, total)
                if digest is not None:
                    results[e.path] = digest
        return results

    emit("size", 0, len(entries))
    on_disk = {e.path for e in entries}
    extra_missing = {p: d for p, d in extra.items() if p not in on_disk}
    # A missing-on-disk library file has no known size, so size/partial can't safely exclude anyone.
    candidates = list(entries) if extra_missing else size_candidates(entries)
    stats.size_candidates = len(candidates)
    if cancel.cancelled:
        return finish([], True)

    pk = partial_kind(partial_sample)
    use_partial = not extra_missing
    big = [e for e in candidates if use_partial and partial_is_useful(e.size, partial_sample)]
    small = [e for e in candidates if not (use_partial and partial_is_useful(e.size, partial_sample))]

    def partial_fn(e: FileEntry) -> str:
        hit = cache.get(pk, e)
        if hit is not None:
            stats.cache_hits += 1
            return hit
        d = partial_sha256(e.path, e.size, sample=partial_sample, meter=meter, cancel=cancel)
        stats.partial_hashed += 1
        cache.put(pk, e, d)
        return d

    partials = run_stage("partial", big, partial_fn)
    if cancel.cancelled:
        return finish([], True)
    narrowed = narrow_by_digest(big, partials)
    stats.partial_candidates = len(narrowed) + len(small)

    def full_fn(e: FileEntry) -> str:
        hit = cache.get(FULL_KIND, e)
        if hit is not None:
            stats.cache_hits += 1
            return hit
        d = full_sha256(e.path, meter=meter, cancel=cancel)
        stats.full_hashed += 1
        cache.put(FULL_KIND, e, d)
        return d

    to_full = small + narrowed
    fulls = run_stage("full", to_full, full_fn)
    if cancel.cancelled:
        return finish([], True)

    items: list[tuple[FileEntry, str]] = [(e, fulls[e.path]) for e in to_full if e.path in fulls]
    for path, digest in extra_missing.items():
        items.append((FileEntry(path, 0, 0), digest))
    return finish(group_by_full_sha256(items))
