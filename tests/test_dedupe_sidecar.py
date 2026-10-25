"""Sidecar hash cache (P3) and confirm-time verification (P4)."""

from __future__ import annotations

import os
from pathlib import Path

import semblon.duplicates as dup
from semblon.dedupe import verify_against_keeper
from semblon.dedupe_sidecar import load_cache, save_cache, sidecar_path
from semblon.dedupe import MemoryHashCache
from tests.test_duplicates_characterization import build_fixture


def test_sidecar_path_and_roundtrip(tmp_path):
    store = tmp_path / "lib.sqlite"
    assert sidecar_path(store).name == "lib.dedupe.sqlite"
    assert len(load_cache(store)) == 0
    c = MemoryHashCache.load([["p", 1, 2, "full-sha256", "d"]])
    assert save_cache(store, c)
    assert load_cache(store).export() == c.export()


def test_second_scan_reads_nothing_and_same_groups(tmp_path):
    store, folder = build_fixture(tmp_path)
    big = b"q" * (400 * 1024)
    (folder / "x1.jpg").write_bytes(big)
    (folder / "x2.jpg").write_bytes(big)
    first = dup.find_exact_duplicate_groups(store)
    assert sidecar_path(store).is_file()
    calls = []
    import semblon.dedupe.pipeline as pl

    orig = pl.full_sha256

    def spy(path, **k):
        calls.append(path)
        return orig(path, **k)

    pl.full_sha256 = spy
    try:
        second = dup.find_exact_duplicate_groups(store)
    finally:
        pl.full_sha256 = orig
    assert second == first
    assert calls == []


def test_changed_file_invalidates_cache(tmp_path):
    store, folder = build_fixture(tmp_path)
    first = dup.find_exact_duplicate_groups(store)
    (folder / "a_copy.JPG").write_bytes(b"now-different")
    second = dup.find_exact_duplicate_groups(store)
    first_n = {g["count"] for g in first["groups"]}
    assert 3 in first_n and 3 not in {g["count"] for g in second["groups"]}


def test_corrupt_sidecar_is_ignored(tmp_path):
    store, _ = build_fixture(tmp_path)
    sidecar_path(store).write_bytes(b"not a database")
    assert dup.find_exact_duplicate_groups(store)["group_count"] == 3


def test_verify_against_keeper(tmp_path):
    import hashlib

    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    sha = hashlib.sha256(b"same").hexdigest()
    assert verify_against_keeper(sha, str(a), str(b)).ok
    assert not verify_against_keeper(sha, str(a), str(a)).ok  # keeper is never a target
    b.write_bytes(b"edited")
    assert verify_against_keeper(sha, str(a), str(b)).reason == "target content differs"
    b.unlink()
    assert not verify_against_keeper(sha, str(a), str(b)).ok
