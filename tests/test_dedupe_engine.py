"""Dedupe engine unit tests: hashing, grouping, discovery, path policy, pipeline, resume."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from semblon.dedupe import (
    CancelToken,
    DiscoveryManifest,
    DuplicateGroup,
    DuplicateMember,
    FileEntry,
    MemoryHashCache,
    ScanOptions,
    discover_files,
    from_checkpoint,
    full_sha256,
    partial_sha256,
    scan_exact,
    to_checkpoint,
)
from semblon.dedupe.grouping import group_by_full_sha256, narrow_by_digest, size_candidates
from semblon.dedupe.hashing import FULL_KIND, partial_is_useful
from semblon.dedupe.path_policy import build_exclusion_keys, is_excluded, is_fs_root, path_key


def _w(p: Path, data: bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


# ── hashing ──────────────────────────────────────────────────────────────
def test_full_hash_is_sha256(tmp_path):
    p = _w(tmp_path / "a.bin", b"hello world" * 1000)
    assert full_sha256(str(p)) == hashlib.sha256(b"hello world" * 1000).hexdigest()


def test_partial_hash_differs_from_full_and_separates_tails(tmp_path):
    big = b"x" * (300 * 1024)
    a = _w(tmp_path / "a", big + b"A")
    b = _w(tmp_path / "b", big + b"B")
    pa = partial_sha256(str(a), a.stat().st_size)
    assert pa != full_sha256(str(a))
    assert pa != partial_sha256(str(b), b.stat().st_size)  # tail sample differs


def test_partial_collision_does_not_confirm(tmp_path):
    # Same size, identical first/middle/last samples, different bytes elsewhere:
    # partial digests collide, the full hash must still tell them apart.
    sample = 64 * 1024
    size = sample * 10
    a = bytearray(b"z" * size)
    b = bytearray(a)
    b[sample * 2] ^= 0xFF  # outside head / middle / tail samples
    pa = _w(tmp_path / "a.jpg", bytes(a))
    pb = _w(tmp_path / "b.jpg", bytes(b))
    assert partial_sha256(str(pa), size) == partial_sha256(str(pb), size)
    result = scan_exact([pa, pb])
    assert result.groups == []
    assert result.stats.full_hashed == 2


def test_partial_skipped_for_small_files():
    assert not partial_is_useful(1000)
    assert partial_is_useful(10 * 1024 * 1024)


# ── grouping ─────────────────────────────────────────────────────────────
def test_size_candidates_drop_unique_sizes():
    es = [FileEntry("a", 1, 0), FileEntry("b", 1, 0), FileEntry("c", 2, 0)]
    assert {e.path for e in size_candidates(es)} == {"a", "b"}


def test_narrow_by_digest():
    es = [FileEntry("a", 5, 0), FileEntry("b", 5, 0), FileEntry("c", 5, 0)]
    out = narrow_by_digest(es, {"a": "x", "b": "x", "c": "y"})
    assert {e.path for e in out} == {"a", "b"}


def test_group_requires_full_digest_and_two_members():
    with pytest.raises(ValueError):
        DuplicateGroup("abc", (DuplicateMember("a", 1, 0), DuplicateMember("b", 1, 0)))
    with pytest.raises(ValueError):
        DuplicateGroup("a" * 64, (DuplicateMember("a", 1, 0),))


def test_group_order_and_dedupe():
    d1, d2 = "1" * 64, "2" * 64
    items = [
        (FileEntry("Z", 1, 0), d1),
        (FileEntry("a", 1, 0), d1),
        (FileEntry("a", 1, 0), d1),
        (FileEntry("x", 1, 0), d2),
        (FileEntry("y", 1, 0), d2),
        (FileEntry("q", 1, 0), d2),
        (FileEntry("solo", 1, 0), "3" * 64),
    ]
    groups = group_by_full_sha256(items)
    assert [g.sha256 for g in groups] == [d2, d1]
    assert [m.path for m in groups[1].members] == ["a", "Z"]


# ── path policy ──────────────────────────────────────────────────────────
def test_path_policy(tmp_path):
    ex = build_exclusion_keys({str(tmp_path / "skip")})
    assert is_excluded(tmp_path / "skip", ex)
    assert is_excluded(tmp_path / "skip" / "deep" / "f.jpg", ex)
    assert not is_excluded(tmp_path / "skipper" / "f.jpg", ex)
    assert not is_excluded(tmp_path / "k", set())
    assert is_fs_root(Path(tmp_path.anchor))
    assert not is_fs_root(tmp_path)
    assert path_key("a//b") == path_key(os.path.join("a", "b"))


# ── discovery ────────────────────────────────────────────────────────────
def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "r"
    _w(root / "a.jpg", b"1")
    _w(root / "sub" / "b.PNG", b"22")
    _w(root / "sub" / "c.txt", b"333")
    _w(root / ".hidden" / "h.jpg", b"4444")
    _w(root / "skipme" / "s.jpg", b"55555")
    _w(root / "keep" / "x" / "d.jpg", b"666666")
    _w(root / "zero.jpg", b"")
    return root


def _names(entries) -> set[str]:
    return {Path(e.path).name for e in entries}


def test_discovery_filters(tmp_path):
    root = _tree(tmp_path)
    opts = ScanOptions(roots=[root], allowed_extensions={".jpg", ".png"})
    assert _names(discover_files(opts)) == {"a.jpg", "b.PNG", "s.jpg", "d.jpg", "zero.jpg"}
    opts.exclude_dirs = {"SkipMe"}
    assert "s.jpg" not in _names(discover_files(opts))
    opts.exclude_paths = {str(root / "keep")}
    assert "d.jpg" not in _names(discover_files(opts))
    opts.include_hidden = True
    assert "h.jpg" in _names(discover_files(opts))
    opts.min_size_bytes = 2
    assert "a.jpg" not in _names(discover_files(opts))
    opts.max_size_bytes = 3
    assert _names(discover_files(opts)) == {"b.PNG"}


def test_discovery_no_subfolders_and_sorted(tmp_path):
    root = _tree(tmp_path)
    got = discover_files(ScanOptions(roots=[root], scan_subfolders=False))
    assert _names(got) == {"a.jpg", "zero.jpg"}
    all_ = discover_files(ScanOptions(roots=[root]))
    paths = [e.path.lower() for e in all_]
    assert paths == sorted(paths)


def test_discovery_cancel(tmp_path):
    root = _tree(tmp_path)
    tok = CancelToken()
    tok.cancel()
    assert discover_files(ScanOptions(roots=[root]), tok) == []


def test_incremental_reuses_unchanged_dirs_and_sees_changes(tmp_path):
    root = _tree(tmp_path)
    opts = ScanOptions(roots=[root], allowed_extensions={".jpg", ".png"})
    manifest = DiscoveryManifest()
    first = discover_files(opts, manifest=manifest)
    from semblon.dedupe.models import ScanStats

    st = ScanStats()
    second = discover_files(opts, manifest=manifest, stats=st)
    assert [e.path for e in second] == [e.path for e in first]
    assert st.dirs_scanned == 0 and st.dirs_reused > 0

    # Content change inside an unchanged directory is still seen (reused files are re-stat'ed).
    (root / "a.jpg").write_bytes(b"changed-size")
    st = ScanStats()
    third = {Path(e.path).name: e for e in discover_files(opts, manifest=manifest, stats=st)}
    assert third["a.jpg"].size == len(b"changed-size")

    # New file => dir mtime changes => rescanned.
    _w(root / "sub" / "new.jpg", b"n")
    names = _names(discover_files(opts, manifest=manifest))
    assert "new.jpg" in names

    # Different options invalidate the manifest.
    st = ScanStats()
    discover_files(ScanOptions(roots=[root], min_size_bytes=2), manifest=manifest, stats=st)
    assert st.dirs_reused == 0


# ── pipeline ─────────────────────────────────────────────────────────────
def test_scan_exact_basic_and_stage_savings(tmp_path):
    big = b"b" * (400 * 1024)
    a = _w(tmp_path / "a.jpg", big)
    b = _w(tmp_path / "b.jpg", big)
    c = _w(tmp_path / "c.jpg", b"c" * (400 * 1024 + 1))  # unique size: never read
    d = _w(tmp_path / "d.jpg", b"tiny")
    events = []
    res = scan_exact([a, b, c, d], on_event=events.append)
    assert [sorted(Path(m.path).name for m in g.members) for g in res.groups] == [["a.jpg", "b.jpg"]]
    assert res.groups[0].sha256 == hashlib.sha256(big).hexdigest()
    assert res.stats.files_considered == 4
    assert res.stats.full_hashed == 2
    # 2 partials (3 samples each) + 2 full reads; far less than hashing all four files.
    assert res.stats.bytes_read < 2 * len(big) + 2 * 3 * 64 * 1024 + 1
    assert {e.stage for e in events} >= {"discover", "size", "partial", "full", "done"}


def test_scan_exact_unreadable_and_missing(tmp_path):
    a = _w(tmp_path / "a.jpg", b"same")
    b = _w(tmp_path / "b.jpg", b"same")
    res = scan_exact([a, b, tmp_path / "gone.jpg"])
    assert len(res.groups) == 1 and res.stats.unreadable == 1


def test_scan_exact_extra_digest_joins_group(tmp_path):
    a = _w(tmp_path / "a.jpg", b"payload")
    lone = _w(tmp_path / "lone.jpg", b"different-size-payload")
    digest = hashlib.sha256(b"payload").hexdigest()
    missing = str(tmp_path / "library_only.jpg")
    res = scan_exact([a, lone], extra_digests={missing: digest})
    assert len(res.groups) == 1
    assert {Path(m.path).name for m in res.groups[0].members} == {"a.jpg", "library_only.jpg"}


def test_scan_exact_cancel(tmp_path):
    files = [_w(tmp_path / f"{i}.jpg", b"dup") for i in range(5)]
    res = scan_exact(files, want_cancel=lambda: True)
    assert res.cancelled and res.groups == []
    events = []
    calls = {"n": 0}

    def cancel_after_some():
        calls["n"] += 1
        return calls["n"] > 12

    res = scan_exact(files, want_cancel=cancel_after_some, on_event=events.append, workers=1)
    assert res.cancelled and events[-1].stage == "cancelled"


def test_scan_roots_mode(tmp_path):
    root = _tree(tmp_path)
    _w(root / "sub" / "a_dup.jpg", b"1")
    res = scan_exact(options=ScanOptions(roots=[root], allowed_extensions={".jpg"}))
    names = [{Path(m.path).name for m in g.members} for g in res.groups]
    assert {"a.jpg", "a_dup.jpg"} in names


# ── resume / cache ───────────────────────────────────────────────────────
def test_resume_skips_hashing_then_detects_change(tmp_path):
    big = b"r" * (400 * 1024)
    a = _w(tmp_path / "a.jpg", big)
    b = _w(tmp_path / "b.jpg", big)
    cache = MemoryHashCache()
    r1 = scan_exact([a, b], cache=cache)
    assert r1.stats.full_hashed == 2

    restored, _ = from_checkpoint(to_checkpoint(cache))
    r2 = scan_exact([a, b], cache=restored)
    assert r2.stats.full_hashed == 0 and r2.stats.partial_hashed == 0
    assert r2.stats.bytes_read == 0
    assert [g.sha256 for g in r2.groups] == [g.sha256 for g in r1.groups]

    b.write_bytes(b"r" * (400 * 1024 - 7))
    r3 = scan_exact([a, b], cache=restored)
    assert r3.groups == []


def test_cache_is_keyed_on_size_and_mtime(tmp_path):
    p = _w(tmp_path / "a", b"1")
    e = FileEntry(str(p), 1, p.stat().st_mtime_ns)
    c = MemoryHashCache()
    c.put(FULL_KIND, e, "d")
    assert c.get(FULL_KIND, e) == "d"
    assert c.get(FULL_KIND, FileEntry(str(p), 1, e.mtime_ns + 1)) is None
    assert from_checkpoint({"version": 99})[0].get(FULL_KIND, e) is None
