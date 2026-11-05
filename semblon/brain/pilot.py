"""BRAIN pilot. Tag photos, then the Inc 6–10 graph passes.

Loop per chunk: NanoDet C1 observe, then ``sync_tags_from_observations`` for
that photo. ``rebuild_object_clusters`` runs only when region embeddings have
grown, and only if ``--no-cluster`` is off. This pilot does not write region
crops. Inc 5 bounds workers, checkpoints the chunk, and records a live status
line. One photo failure is logged and skipped. The markdown report is
rewritten after every chunk.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import logging
import os
import platform
import random
import statistics
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from semblon.brain.evidence import record_observations
from semblon.brain.graph import sync_tags_from_observations
from semblon.brain.nanodet_observer import NanoDetObserver
from semblon.brain.object_cluster import rebuild_object_clusters
from semblon.brain.observation import Observation, PhotoRef
from semblon.brain.resources import (
    InputPriority,
    ThroughputMeter,
    checkpoint_path,
    choose_execution_provider,
    classify_pressure,
    read_checkpoint,
    status_line,
    worker_cap,
    write_checkpoint,
)
from semblon.erasure_intent import ErasureIntent, erasure_authorized
from semblon.store import connect, init_db

log = logging.getLogger("semblon.brain.pilot")

RUN_ID = "brain-pilot"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
RSS_ABORT_MB = 14 * 1024
SLOW_CHUNK_FACTOR = 3.0
MIN_CHUNKS_BEFORE_SLOW_ABORT = 3

_MB = 1024 * 1024


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class _PerformanceInformation(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("CommitTotal", ctypes.c_size_t),
        ("CommitLimit", ctypes.c_size_t),
        ("CommitPeak", ctypes.c_size_t),
        ("PhysicalTotal", ctypes.c_size_t),
        ("PhysicalAvailable", ctypes.c_size_t),
        ("SystemCache", ctypes.c_size_t),
        ("KernelTotal", ctypes.c_size_t),
        ("KernelPaged", ctypes.c_size_t),
        ("KernelNonpaged", ctypes.c_size_t),
        ("PageSize", ctypes.c_size_t),
        ("HandleCount", wintypes.DWORD),
        ("ProcessCount", wintypes.DWORD),
        ("ThreadCount", wintypes.DWORD),
    ]


@dataclass
class ChunkMeasurement:
    index: int
    photos: int
    elapsed_s: float
    rss_peak_mb: float
    rss_delta_mb: float
    cluster_s: float | None
    throughput_per_min: float
    provider: str
    errors: list[str] = field(default_factory=list)


@dataclass
class PilotResult:
    code: int
    photos: int
    chunks: list[ChunkMeasurement]
    out: Path
    aborted: str | None = None


def _runtime_labels() -> tuple[str, str]:
    from semblon.engine import process_arch, process_execution

    arch = process_arch()
    reported = process_execution()
    execution = reported if reported in {"native", "emulated"} else "emulated"
    return arch, execution


def _kernel32():
    lib = ctypes.WinDLL("kernel32", use_last_error=True)
    lib.GetCurrentProcess.restype = wintypes.HANDLE
    lib.K32GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    lib.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    lib.K32GetPerformanceInfo.argtypes = [
        ctypes.POINTER(_PerformanceInformation),
        wintypes.DWORD,
    ]
    lib.K32GetPerformanceInfo.restype = wintypes.BOOL
    return lib


def peak_rss_mb() -> tuple[float, float]:
    """Return (current working set MB, peak working set MB)."""
    if sys.platform != "win32":
        raise OSError("RSS probe is Windows-only")
    lib = _kernel32()
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    ok = lib.K32GetProcessMemoryInfo(
        lib.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    if not ok:
        raise OSError("GetProcessMemoryInfo failed")
    return counters.WorkingSetSize / _MB, counters.PeakWorkingSetSize / _MB


def swap_sample() -> dict:
    """Free physical RAM via GetPerformanceInfo.

    A swap event is a sample with under 256 MB physical RAM free. Commit
    charge above installed RAM is normal on Windows and is not a swap event.
    The result is ``unmeasured`` when the API is absent.
    """
    if sys.platform != "win32":
        return {"status": "unmeasured"}
    lib = _kernel32()
    info = _PerformanceInformation()
    info.cb = ctypes.sizeof(info)
    ok = lib.K32GetPerformanceInfo(ctypes.byref(info), info.cb)
    if not ok:
        return {"status": "unmeasured"}
    page = int(info.PageSize) or 4096
    physical = int(info.PhysicalTotal) * page
    available = int(info.PhysicalAvailable) * page
    commit = int(info.CommitTotal) * page
    available_mb = available / _MB
    return {
        "status": "measured",
        "physical_mb": physical / _MB,
        "available_mb": available_mb,
        "commit_mb": commit / _MB,
        "low_memory": available_mb < 256,
    }


def _iter_paths(corpus: Path):
    if corpus.is_file() and corpus.suffix.lower() == ".txt":
        for line in corpus.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                yield Path(text)
        return
    if corpus.is_file() and corpus.suffix.lower() in {".sqlite", ".db"}:
        import sqlite3

        conn = sqlite3.connect(str(corpus))
        try:
            rows = conn.execute(
                "SELECT path FROM media WHERE source_type='folder' ORDER BY path"
            )
            for row in rows:
                yield Path(str(row[0]))
        finally:
            conn.close()
        return
    for dirpath, dirnames, filenames in os.walk(corpus):
        dirnames.sort()
        parent = Path(dirpath)
        # Owner holdout. Not a date filter and not deduplication.
        if parent.name == "DCIMaw" and parent.parent.name == "Yandex.Disk" and "me" in dirnames:
            dirnames.remove("me")
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() in IMAGE_SUFFIXES:
                yield path


def select_paths(corpus: Path, limit: int | None) -> tuple[list[Path], str]:
    """Whole corpus, or a seeded reservoir sample when ``limit`` is smaller."""
    seed_hex = hashlib.sha256(str(corpus.resolve()).encode()).hexdigest()[:8]
    rng = random.Random(int(seed_hex, 16))
    chosen: list[Path] = []
    seen = 0
    for path in _iter_paths(corpus):
        seen += 1
        if limit is None or len(chosen) < limit:
            chosen.append(path)
            continue
        pick = rng.randrange(seen)
        if pick < limit:
            chosen[pick] = path
    if limit is None or seen <= limit:
        note = f"entire corpus, {seen} photos, sorted directory walk"
    else:
        note = (
            f"reservoir sample of {limit} from {seen} photos, "
            f"seed sha256(corpus)[:8]={seed_hex}"
        )
    return chosen, note


def _photo_ref(path: Path) -> PhotoRef:
    digest = hashlib.sha256(str(path.resolve()).encode()).hexdigest()
    return PhotoRef(photo_id=digest, path=str(path), content_hash=digest)


def _ensure_run(conn, arch: str, execution: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT OR IGNORE INTO runs(
             run_id, started_at, software_version, pack_id, embedding_dim,
             embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,0,'l2','{}','{}',?,?)""",
        (RUN_ID, now, "brain-pilot", "pilot-c1", arch, execution),
    )
    conn.commit()


def _ensure_media(conn, photo: PhotoRef, path: Path) -> None:
    st = path.stat()
    conn.execute(
        """INSERT OR IGNORE INTO media(
             media_id, source_type, path, sha256, mtime_ns, byte_size)
           VALUES (?,'folder',?,?,?,?)""",
        (photo.photo_id, str(path), photo.content_hash, int(st.st_mtime_ns), int(st.st_size)),
    )


def _delete_c1(conn, media_id: str) -> None:
    intent = ErasureIntent(
        requestor="system",
        scope="media",
        media_id=media_id,
        reason="pilot force re-observe",
        authorized_by="brain.pilot",
    )
    with erasure_authorized(intent):
        conn.execute(
            "DELETE FROM brain_observations WHERE media_id=? AND capability_id='C1'",
            (media_id,),
        )
    conn.commit()


def _provider_of(obs: Observation) -> str:
    payload = obs.payload if isinstance(obs.payload, dict) else {}
    return str(payload.get("provider") or obs.provider_name or "unknown")


def observe_c1(conn, photo: PhotoRef, observer, *, force: bool) -> str:
    """NanoDet wrap. Existing C1 rows are kept unless ``force`` deletes them."""
    row = conn.execute(
        """SELECT provider_name FROM brain_observations
           WHERE media_id=? AND capability_id='C1' LIMIT 1""",
        (photo.photo_id,),
    ).fetchone()
    if row is not None and not force:
        return str(row[0] or "unknown")
    if row is not None and force:
        _delete_c1(conn, photo.photo_id)
    observations = list(observer.observe(photo) or [])
    if not observations:
        return "unknown"
    record_observations(conn, observations, run_id=RUN_ID, write_tagged=True)
    return _provider_of(observations[0])


def _default_workers(workers: int | None, *, injected_observer: bool) -> int:
    """Real runs use a few threads. An injected observer stays single-threaded."""
    if injected_observer:
        return 1
    if workers is not None:
        return max(1, int(workers))
    return max(1, min(4, os.cpu_count() or 1))


def _note_photo_error(
    notes: list[str],
    errors: list[str],
    path: Path,
    exc: BaseException | None = None,
    *,
    detail: str | None = None,
) -> None:
    if detail is None:
        detail = f"{type(exc).__name__}: {exc}"
    message = f"{path}: {detail}"
    log.warning("%s", message)
    errors.append(message)
    if sum(1 for note in notes if note.startswith("photo:")) < 30:
        notes.append("photo: " + message)


def _infer_photo(path: Path) -> tuple[Path, PhotoRef, list, str | None]:
    """Decode and run NanoDet. SQLite stays on the calling thread."""
    photo = _photo_ref(path)
    try:
        observations = list(NanoDetObserver().observe(photo) or [])
        return path, photo, observations, None
    except Exception as exc:
        return path, photo, [], f"{type(exc).__name__}: {exc}"


def _region_embedding_count(conn) -> int:
    row = conn.execute(
        """SELECT COUNT(*) FROM embeddings
           WHERE modality IN ('region', 'region_patch')"""
    ).fetchone()
    return int(row[0] or 0)


def _chunks(items: list[Path], size: int):
    step = max(1, int(size))
    for start in range(0, len(items), step):
        yield items[start : start + step]


def _fmt_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _render(
    *,
    out: Path,
    started: datetime,
    machine: str,
    corpus: Path,
    selection: str,
    command: str,
    arch: str,
    execution: str,
    ram_mb: float | None,
    cpu: str,
    chunks: list[ChunkMeasurement],
    wall_s: float,
    swap_events: int | str,
    notes: list[str],
    status: str,
    live: str = "",
    rates: dict | None = None,
) -> None:
    photos = sum(c.photos for c in chunks)
    tag_s = sum(c.elapsed_s for c in chunks)
    cluster_runs = [c.cluster_s for c in chunks if c.cluster_s is not None]
    cluster_s = sum(cluster_runs)
    peak = max((c.rss_peak_mb for c in chunks), default=0.0)
    rate = (photos / tag_s * 60.0) if tag_s > 0 else 0.0
    per_s = (photos / tag_s) if tag_s > 0 else 0.0
    ram_line = f"{ram_mb:.0f} MB" if ram_mb is not None else "unmeasured"
    lines = [
        f"# 100k Pilot — {started.date().isoformat()} — {machine}",
        "",
        "## Environment",
        f"- OS / arch / CPU / RAM / execution: {platform.platform()} / {arch} / {cpu} / {ram_line} / {execution}",
        f"- Corpus: `{corpus}` — {selection}",
        f"- Command: `{command}`",
        f"- Status: {status}",
        f"- Live: {live or 'n/a'}",
        "",
        "## Aggregate",
        f"- Total photos: {photos}",
        f"- Tag-window elapsed: {_fmt_duration(tag_s)}",
        f"- Wall elapsed: {_fmt_duration(wall_s)}",
        f"- Throughput: {rate:.1f} photos/min ({per_s:.2f}/s)",
        f"- Peak RSS: {peak:.1f} MB",
        f"- Cluster runs: {len(cluster_runs)} totalling {_fmt_duration(cluster_s)}",
        f"- Swap events: {swap_events}",
    ]
    if rates:
        rate_text = ", ".join(f"{name}={value:.1f}/min" for name, value in sorted(rates.items()))
        lines.append(f"- Per-model throughput: {rate_text}")
    lines.extend([
        "",
        "## Per-chunk",
        "| Chunk | Photos | Elapsed (s) | RSS peak (MB) | Cluster (s) | Throughput (ph/min) |",
        "|---|---|---|---|---|---|",
    ])
    for chunk in chunks:
        cluster = "" if chunk.cluster_s is None else f"{chunk.cluster_s:.1f}"
        lines.append(
            f"| {chunk.index} | {chunk.photos} | {chunk.elapsed_s:.1f} | "
            f"{chunk.rss_peak_mb:.1f} | {cluster} | {chunk.throughput_per_min:.1f} |"
        )
    lines.extend(["", "## Notes / anomalies"])
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- None")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def _close_graph(conn, notes: list[str]) -> None:
    """Inc 6–10 once, after tags. Failures are notes. No region crops."""
    from semblon.brain.cooccur import rebuild_cooccurs
    from semblon.brain.face_link import link_faces
    from semblon.brain.same_as import link_same_as
    from semblon.brain.scene_link import brain_gaps, link_scenes
    from semblon.brain.temporal import rebuild_temporal_next

    steps = (
        ("temporal", rebuild_temporal_next),
        ("cooccur", rebuild_cooccurs),
        ("same_as", link_same_as),
        ("faces", link_faces),
        ("scenes", link_scenes),
    )
    for name, fn in steps:
        try:
            notes.append(f"{name}: {fn(conn)}")
        except Exception as exc:
            notes.append(f"{name} failed: {type(exc).__name__}: {exc}")
    try:
        gaps = brain_gaps(conn)
        notes.append(
            "gaps: "
            f"tag={gaps['tag']} scene={gaps['scene']} "
            f"face={gaps['face']} face_unclustered={gaps['face_unclustered']}"
        )
    except Exception as exc:
        notes.append(f"gaps failed: {type(exc).__name__}: {exc}")


def _pressure_sample(pressure_fn, rss_fn, swap_fn) -> tuple[float, float]:
    if pressure_fn is not None:
        rss, available = pressure_fn()
        return float(rss), float(available)
    try:
        rss, _peak = rss_fn()
    except Exception:
        rss = 0.0
    sample = swap_fn()
    available = sample.get("available_mb")
    if not isinstance(available, (int, float)):
        available = 10_000.0
    return float(rss), float(available)


def run_pilot(
    *,
    corpus: Path,
    out: Path,
    store: Path | None = None,
    limit: int | None = None,
    chunk: int = 1000,
    no_cluster: bool = False,
    force: bool = False,
    workers: int | None = None,
    command: str = "",
    observer=None,
    cluster_fn=None,
    rss_fn=None,
    swap_fn=None,
    ep_probe=None,
    pressure_fn=None,
    priority: InputPriority | None = None,
    wait_fn=None,
) -> PilotResult:
    corpus = Path(corpus)
    out = Path(out)
    store_path = Path(store) if store is not None else out.with_suffix(".sqlite")
    injected_observer = observer is not None
    workers = _default_workers(workers, injected_observer=injected_observer)
    observer = observer if injected_observer else NanoDetObserver()
    cluster_fn = cluster_fn if cluster_fn is not None else rebuild_object_clusters
    rss_fn = rss_fn if rss_fn is not None else peak_rss_mb
    swap_fn = swap_fn if swap_fn is not None else swap_sample

    paths, selection = select_paths(corpus, limit)
    arch, execution = _runtime_labels()
    machine = os.environ.get("COMPUTERNAME") or platform.node() or "unknown"
    cpu = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER") or "unknown"
    started = datetime.now(timezone.utc)
    wall0 = time.perf_counter()
    swap_info = swap_fn()
    ram_mb = swap_info.get("physical_mb") if swap_info.get("status") == "measured" else None
    swap_events: int | str = 0 if swap_info.get("status") == "measured" else "unmeasured"
    notes: list[str] = [
        selection,
        "No provider fallback. A failed photo is logged and skipped.",
        f"Workers: {workers}",
    ]
    if force:
        notes.append("force: existing C1 observations were replaced")
    choice = choose_execution_provider(ep_probe)
    notes.append(
        f"EP: {choice.chosen} gpu={choice.gpu} identity={choice.identity_path}"
    )
    notes.append(
        "Tag-only floor from the completed 10k run is 506.7 photos/min. "
        "This run measures its own rate."
    )
    priority = priority if priority is not None else InputPriority()
    meter = ThroughputMeter()
    wait = wait_fn if wait_fn is not None else time.sleep
    corpus_key = str(corpus.resolve())
    ck_path = checkpoint_path(store_path)
    prior = read_checkpoint(ck_path)
    skipped = 0
    skipped_chunks = 0
    if (
        prior is not None
        and prior.get("corpus") == corpus_key
        and prior.get("limit") == limit
        and prior.get("selection") == selection
    ):
        skipped = min(int(prior["photos_done"]), len(paths))
        skipped_chunks = int(prior["chunk_index"])
        paths = paths[skipped:]
        if skipped:
            notes.append(f"Resumed at photo {skipped}")

    conn = connect(store_path)
    init_db(conn)
    _ensure_run(conn, arch, execution)
    chunks: list[ChunkMeasurement] = []
    last_regions = _region_embedding_count(conn)
    did_cluster = False
    aborted: str | None = None
    code = 0
    executor: ThreadPoolExecutor | None = None
    live = ""
    done = skipped
    groups = list(_chunks(paths, chunk))

    def _save(photos_done: int, chunk_index: int) -> None:
        write_checkpoint(
            ck_path,
            {
                "chunk_index": int(chunk_index),
                "photos_done": int(photos_done),
                "corpus": corpus_key,
                "limit": limit,
                "selection": selection,
            },
        )

    def _paint(status: str) -> None:
        _render(
            out=out,
            started=started,
            machine=machine,
            corpus=corpus,
            selection=selection,
            command=command or f"python -m semblon.brain.pilot --corpus {corpus} --out {out}",
            arch=arch,
            execution=execution,
            ram_mb=ram_mb,
            cpu=cpu,
            chunks=chunks,
            wall_s=time.perf_counter() - wall0,
            swap_events=swap_events,
            notes=notes,
            status=status,
            live=live,
            rates=meter.snapshot(),
        )

    try:
        cursor = 0
        pauses = 0
        while cursor < len(groups):
            group = groups[cursor]
            index = skipped_chunks + cursor + 1
            rss_now, available = _pressure_sample(pressure_fn, rss_fn, swap_fn)
            pressure = classify_pressure(rss_now, available)
            yielding = priority.should_yield()
            if pressure == "pause" and pauses < 3:
                pauses += 1
                notes.append(f"pause {pauses}: available RAM under 256 MB")
                _save(done, skipped_chunks + cursor)
                wait(0.05)
                continue
            if pressure == "pause" or yielding:
                active = 1
                if pressure == "pause":
                    notes.append("pause held; chunk ran at 1 worker")
            else:
                active = worker_cap(workers, pressure)
            pauses = 0
            rss0, _peak0 = rss_fn()
            t0 = time.perf_counter()
            providers: list[str] = []
            errors: list[str] = []
            if active <= 1:
                for path in group:
                    photo = _photo_ref(path)
                    try:
                        _ensure_media(conn, photo, path)
                        conn.commit()
                        provider = observe_c1(conn, photo, observer, force=force)
                        sync_tags_from_observations(conn, photo.photo_id)
                        providers.append(provider)
                    except Exception as exc:
                        _note_photo_error(notes, errors, path, exc)
            else:
                if executor is None:
                    import cv2

                    # One DNN forward already uses more than one core.
                    cv2.setNumThreads(1)
                    executor = ThreadPoolExecutor(
                        max_workers=workers, thread_name_prefix="pilot-c1"
                    )
                pending: list[Path] = []
                for path in group:
                    photo = _photo_ref(path)
                    try:
                        _ensure_media(conn, photo, path)
                        row = conn.execute(
                            """SELECT provider_name FROM brain_observations
                               WHERE media_id=? AND capability_id='C1' LIMIT 1""",
                            (photo.photo_id,),
                        ).fetchone()
                        if row is not None and not force:
                            providers.append(str(row[0] or "unknown"))
                            continue
                        if row is not None and force:
                            _delete_c1(conn, photo.photo_id)
                        pending.append(path)
                    except Exception as exc:
                        _note_photo_error(notes, errors, path, exc)
                conn.commit()
                for path, photo, observations, err in executor.map(_infer_photo, pending):
                    if err:
                        _note_photo_error(notes, errors, path, detail=err)
                        continue
                    try:
                        if observations:
                            record_observations(
                                conn, observations, run_id=RUN_ID, write_tagged=True
                            )
                            providers.append(_provider_of(observations[0]))
                        else:
                            providers.append("unknown")
                        sync_tags_from_observations(conn, photo.photo_id)
                    except Exception as exc:
                        _note_photo_error(notes, errors, path, exc)
            elapsed = time.perf_counter() - t0
            try:
                rss1, peak1 = rss_fn()
            except Exception as exc:
                rss1, peak1 = 0.0, 0.0
                notes.append(f"RSS probe failed: {exc}")
            cluster_s: float | None = None
            regions_now = _region_embedding_count(conn)
            enough_new = regions_now > last_regions or (regions_now > 0 and not did_cluster)
            if not no_cluster and enough_new:
                try:
                    t2 = time.perf_counter()
                    cluster_fn(conn)
                    cluster_s = time.perf_counter() - t2
                    did_cluster = True
                    last_regions = max(last_regions, regions_now)
                except Exception as exc:
                    message = f"cluster chunk {index}: {type(exc).__name__}: {exc}"
                    log.warning("%s", message)
                    notes.append(message + " — continued tags-only")
                    did_cluster = True
                    last_regions = max(last_regions, regions_now)
            provider = Counter(providers).most_common(1)
            provider_name = provider[0][0] if provider else "unknown"
            rate = (len(group) / elapsed * 60.0) if elapsed > 0 else 0.0
            measured = ChunkMeasurement(
                index=index,
                photos=len(group),
                elapsed_s=elapsed,
                rss_peak_mb=max(peak1, rss1),
                rss_delta_mb=rss1 - rss0,
                cluster_s=cluster_s,
                throughput_per_min=rate,
                provider=provider_name,
                errors=errors,
            )
            chunks.append(measured)
            meter.add("c1", len(group), elapsed)
            if cluster_s:
                meter.add("object_cluster", 1.0, cluster_s)
            done += len(group)
            cursor += 1
            _save(done, skipped_chunks + cursor)
            live = status_line(
                photos=done,
                rss_mb=measured.rss_peak_mb,
                pressure=pressure,
                ep=choice.chosen,
                yielding=yielding,
                rates=meter.snapshot(),
                execution=execution,
            )
            sample = swap_fn()
            if sample.get("status") != "measured":
                swap_events = "unmeasured"
            elif sample.get("low_memory") and isinstance(swap_events, int):
                swap_events += 1
            _paint("running")
            if measured.rss_peak_mb > RSS_ABORT_MB:
                aborted = f"peak RSS {measured.rss_peak_mb:.0f} MB exceeded {RSS_ABORT_MB} MB"
                code = 2
                break
            if len(chunks) > MIN_CHUNKS_BEFORE_SLOW_ABORT:
                prior_elapsed = [c.elapsed_s for c in chunks[:-1]]
                median = statistics.median(prior_elapsed)
                if median > 0 and elapsed > SLOW_CHUNK_FACTOR * median:
                    aborted = (
                        f"chunk {index} took {elapsed:.1f}s, "
                        f"> {SLOW_CHUNK_FACTOR:.0f}× median {median:.1f}s"
                    )
                    code = 2
                    break
        if aborted is None:
            _close_graph(conn, notes)
        tag_rows = conn.execute(
            """SELECT label, member_count, status FROM brain_nodes
               WHERE node_type='Tag' ORDER BY member_count DESC LIMIT 8"""
        ).fetchall()
        if tag_rows:
            summary = ", ".join(
                f"{row[0]}={row[1]}:{row[2]}" for row in tag_rows
            )
            notes.append(f"Top tags: {summary}")
        providers_seen = sorted({c.provider for c in chunks})
        notes.append("Providers seen: " + (", ".join(providers_seen) or "none"))
        error_total = sum(len(c.errors) for c in chunks)
        if error_total:
            notes.append(f"Photo errors: {error_total} (first 30 listed)")
    except KeyboardInterrupt:
        aborted = "interrupted"
        code = 130
        log.warning("pilot interrupted")
    except Exception:
        aborted = traceback.format_exc().strip()
        log.exception("pilot failed")
        code = 1
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)
        status = "complete" if aborted is None else f"aborted: {aborted}"
        if aborted:
            notes.append(aborted)
        _paint(status)
        conn.close()
    return PilotResult(
        code=code,
        photos=sum(c.photos for c in chunks),
        chunks=chunks,
        out=out,
        aborted=aborted,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m semblon.brain.pilot")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--chunk", type=int, default=1000)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--no-cluster", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="NanoDet threads. Default is up to 4 on a real run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    command = "python -m semblon.brain.pilot " + " ".join(argv if argv is not None else sys.argv[1:])
    try:
        result = run_pilot(
            corpus=args.corpus,
            out=args.out,
            store=args.store,
            limit=args.limit,
            chunk=args.chunk,
            no_cluster=args.no_cluster,
            force=args.force,
            workers=args.workers,
            command=command,
        )
    except Exception:
        log.exception("pilot failed before the loop")
        return 1
    return result.code


if __name__ == "__main__":
    raise SystemExit(main())
