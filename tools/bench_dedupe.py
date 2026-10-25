"""Benchmark: legacy exact path vs ``semblon.dedupe`` vs CEREBRO-style size->SHA-256.

Generates a synthetic photo-like folder in a temp directory (never touches a real library) and
compares scan time, bytes read, peak Python memory, group parity and cancellation latency.

    python tools/bench_dedupe.py --files 3000 --repeat 3
    python tools/bench_dedupe.py --files 500 --json out.json

Notes: files are freshly written, so the OS page cache is warm and wall-time understates what a
cold disk shows; ``bytes_read`` is the I/O-neutral number to trust. Peak memory is Python
allocations (tracemalloc), not RSS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import semblon.duplicates as dup  # noqa: E402
from semblon.dedupe import CancelToken, scan_exact  # noqa: E402
from semblon.store import connect, init_db  # noqa: E402

SAMPLE = 64 * 1024


PROFILES = {
    # cumulative thresholds: exact dup, same-size decoy, partial-sample collision; then size range
    "photos": (0.15, 0.25, 0.30, (30_000, 700_000)),
    "decoys": (0.05, 0.60, 0.70, (200_000, 900_000)),
    "small": (0.20, 0.30, 0.32, (4_000, 150_000)),
    "large": (0.10, 0.20, 0.25, (2_000_000, 6_000_000)),
}


def make_fixture(root: Path, n_files: int, seed: int, profile: str = "photos") -> dict:
    """Synthetic folder; ``profile`` picks the duplicate/decoy mix and file-size range."""
    p_dup, p_decoy, p_coll, sizes = PROFILES[profile]
    rnd = random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    folders = [root / f"album{i:02d}" for i in range(12)]
    for f in folders:
        f.mkdir()
    total_bytes = 0
    made = 0

    def blob(size: int) -> bytes:
        return rnd.randbytes(size)

    def put(data: bytes, ext: str = ".jpg") -> Path:
        nonlocal total_bytes, made
        p = rnd.choice(folders) / f"img_{made:05d}{ext}"
        p.write_bytes(data)
        total_bytes += len(data)
        made += 1
        return p

    originals: list[bytes] = []
    while made < n_files:
        r = rnd.random()
        size = rnd.randint(*sizes)
        if r < p_dup and originals:
            put(rnd.choice(originals), rnd.choice([".jpg", ".png"]))
        elif r < p_decoy and originals:
            base = rnd.choice(originals)
            put(blob(len(base)))  # same size, different content
        elif r < p_coll and originals:
            base = rnd.choice(originals)
            if len(base) > SAMPLE * 4:
                t = bytearray(base)
                t[SAMPLE * 2 - 1 + SAMPLE // 2] ^= 1  # between head and middle samples
                put(bytes(t))
            else:
                put(blob(size))
        else:
            data = blob(size)
            originals.append(data)
            put(data)
    return {"files": made, "bytes": total_bytes}


def seed_store(store: Path, folder: Path) -> None:
    """One library row per album folder, so ``candidate_files`` covers every album."""
    con = connect(store)
    try:
        init_db(con)
        seen: set[str] = set()
        for i, album in enumerate(sorted(p for p in folder.iterdir() if p.is_dir())):
            first = next(iter(sorted(album.glob("*.jpg"))), None)
            if first is None:
                continue
            data = first.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            con.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (f"m{i}", "folder", str(first), digest, 1, 1, 0, len(data)),
            )
        con.commit()
    finally:
        con.close()

def normalise(groups_by_hash: dict[str, list[str]]) -> list:
    return sorted((h, sorted(p.lower() for p in ps)) for h, ps in groups_by_hash.items() if len(ps) > 1)


def from_api(result: dict) -> list:
    return normalise({g["content_hash"]: [m["path"] for m in g["members"]] for g in result["groups"]})


class Counting:
    """Counts bytes read by the legacy path by wrapping its hash function."""

    def __init__(self) -> None:
        self.bytes = 0
        self._orig = dup._sha256_file

    def __enter__(self):
        def wrapped(path: Path) -> str:
            h = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    self.bytes += len(chunk)
                    h.update(chunk)
            return h.hexdigest()

        dup._sha256_file = wrapped
        return self

    def __exit__(self, *a) -> None:
        dup._sha256_file = self._orig


def run_legacy(store: Path, cancel=None):
    import os

    os.environ[dup.LEGACY_EXACT_ENV] = "1"
    try:
        with Counting() as c:
            res = dup.find_exact_duplicate_groups(store, want_cancel=cancel)
        return res, c.bytes
    finally:
        os.environ.pop(dup.LEGACY_EXACT_ENV, None)


def run_new(store: Path, cancel=None):
    import os

    from semblon.dedupe_sidecar import sidecar_path

    os.environ.pop(dup.LEGACY_EXACT_ENV, None)
    sidecar_path(store).unlink(missing_ok=True)  # cold: no cache from an earlier repeat
    res = dup.find_exact_duplicate_groups(store, want_cancel=cancel)
    return res, None


def run_new_warm(store: Path, cancel=None):
    import os

    os.environ.pop(dup.LEGACY_EXACT_ENV, None)
    res = dup.find_exact_duplicate_groups(store, want_cancel=cancel)
    return res, None


def run_engine(files: list[Path], cancel=None):
    r = scan_exact(files, cancel=CancelToken(cancel))
    return r, r.stats.bytes_read


def run_cerebro_style(files: list[Path], cancel=None):
    """size -> full SHA-256 of every size-collision (CEREBRO finder.py correctness reference)."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    for p in files:
        try:
            by_size[p.stat().st_size].append(p)
        except OSError:
            continue
    by_hash: dict[str, list[str]] = defaultdict(list)
    read = 0
    for ps in by_size.values():
        if len(ps) < 2:
            continue
        for p in ps:
            if cancel and cancel():
                return None, read
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    read += len(chunk)
                    h.update(chunk)
            by_hash[h.hexdigest()].append(str(p))
    return by_hash, read


def measure(fn):
    tracemalloc.start()
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return out, dt, peak


def cancel_latency(fn, files_total: int, delay: float) -> dict:
    """Request cancel ``delay`` seconds after start; report how long the call takes to return."""
    flag = threading.Event()
    t_req = {}

    def trigger() -> None:
        time.sleep(delay)
        t_req["t"] = time.perf_counter()
        flag.set()

    threading.Thread(target=trigger, daemon=True).start()
    t0 = time.perf_counter()
    res = fn(flag.is_set)
    t1 = time.perf_counter()
    requested = "t" in t_req
    return {
        "returned_after_s": round(t1 - t0, 3),
        "latency_after_request_s": round(t1 - t_req["t"], 3) if requested else None,
        "cancelled": requested and _was_cancelled(res),
    }


def _was_cancelled(res) -> bool:
    obj = res[0]
    if obj is None:
        return True
    if isinstance(obj, dict):
        return obj.get("status") == "CANCELLED"
    return bool(getattr(obj, "cancelled", False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=2000)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--seed", type=int, default=12)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="photos")
    ap.add_argument("--cancel-after", type=float, default=0.05)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="semblon-bench-dedupe-"))
    try:
        folder = tmp / "photos"
        info = make_fixture(folder, args.files, args.seed, args.profile)
        store = tmp / "s.sqlite"
        seed_store(store, folder)
        rows = dup.library_media_rows(store)
        files = dup.candidate_files(rows, dup.scan_dirs_from_media(rows))
        print(f"fixture: {info['files']} files, {info['bytes'] / 1e6:.1f} MB at {folder}")

        variants = {
            "legacy (duplicates.py old path)": lambda c=None: run_legacy(store, c),
            "dedupe via duplicates.py": lambda c=None: run_new(store, c),
            "dedupe via duplicates.py (warm sidecar)": lambda c=None: run_new_warm(store, c),
            "dedupe engine (scan_exact)": lambda c=None: run_engine(files, c),
            "cerebro-style size->sha256": lambda c=None: run_cerebro_style(files, c),
        }
        results: dict[str, dict] = {}
        canon: dict[str, list] = {}
        for name, fn in variants.items():
            times, peaks, reads = [], [], []
            out = None
            for _ in range(args.repeat):
                (out, nbytes), dt, peak = measure(fn)
                times.append(dt)
                peaks.append(peak)
                reads.append(nbytes)
            if isinstance(out, dict) and "status" in out:
                canon[name] = from_api(out)
            elif hasattr(out, "groups"):
                canon[name] = normalise({g.sha256: [m.path for m in g.members] for g in out.groups})
            else:
                canon[name] = normalise(out)
            results[name] = {
                "median_s": round(statistics.median(times), 3),
                "min_s": round(min(times), 3),
                "bytes_read": reads[-1],
                "peak_py_mem_mb": round(max(peaks) / 1e6, 2),
                "groups": len(canon[name]),
            }
            c = cancel_latency(lambda cc, _f=fn: _f(cc), info["files"], args.cancel_after)
            results[name]["cancel"] = c

        ref = canon["legacy (duplicates.py old path)"]
        for name in results:
            results[name]["parity_with_legacy"] = canon[name] == ref
        results["_fixture"] = info

        print(f"\n{'variant':36} {'median s':>9} {'bytes read':>13} {'peak MB':>8} {'groups':>7} parity  cancel-latency")
        for name, r in results.items():
            if name.startswith("_"):
                continue
            br = r["bytes_read"]
            print(
                f"{name:36} {r['median_s']:>9} {br if br is not None else 'n/a':>13} "
                f"{r['peak_py_mem_mb']:>8} {r['groups']:>7} {str(r['parity_with_legacy']):6}  "
                f"{r['cancel']['latency_after_request_s']}s"
            )
        if args.json:
            args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        return 0 if all(r["parity_with_legacy"] for n, r in results.items() if not n.startswith("_")) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
