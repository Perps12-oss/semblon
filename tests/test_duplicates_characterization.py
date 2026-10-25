"""Characterization: pins today's ``find_integrity_groups`` output on a fixture folder.

Any engine swap behind ``semblon.duplicates`` must keep this green.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from semblon.duplicates import candidate_files, find_integrity_groups
from semblon.store import connect, init_db


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_fixture(tmp_path: Path) -> tuple[Path, Path]:
    folder = tmp_path / "photos"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "deeper").mkdir()
    (folder / "a.jpg").write_bytes(b"alpha-bytes")
    (folder / "a_copy.JPG").write_bytes(b"alpha-bytes")
    (folder / "sub" / "a_again.png").write_bytes(b"alpha-bytes")
    (folder / "sub" / "deeper" / "b1.webp").write_bytes(b"beta" * 5000)
    (folder / "sub" / "deeper" / "b2.webp").write_bytes(b"beta" * 5000)
    # Same size as b1/b2 but different content: must not group.
    (folder / "sub" / "deeper" / "b3.webp").write_bytes(b"gamm" * 5000)
    (folder / "unique.bmp").write_bytes(b"only-one")
    (folder / "empty1.png").write_bytes(b"")
    (folder / "empty2.png").write_bytes(b"")
    # Not a candidate extension: ignored even though it duplicates a.jpg.
    (folder / "notes.txt").write_bytes(b"alpha-bytes")
    store = tmp_path / "s.sqlite"
    con = connect(store)
    try:
        init_db(con)
        for mid, name in (("m1", "a.jpg"), ("m2", "unique.bmp")):
            p = folder / name
            con.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (mid, "folder", str(p), _sha(p.read_bytes()), 1, 1, 0, p.stat().st_size),
            )
        con.commit()
    finally:
        con.close()
    return store, folder


def _shape(result: dict) -> list[tuple]:
    return [
        (
            g["content_hash"],
            g["count"],
            [(Path(m["path"]).name, m["in_library"], m["media_id"]) for m in g["members"]],
        )
        for g in result["groups"]
    ]


def test_integrity_exact_output_pinned(tmp_path):
    store, folder = build_fixture(tmp_path)
    result = find_integrity_groups(store)
    exact = result["exact"]

    assert exact["status"] == "SUCCESS"
    assert exact["hash_algorithm"] == "sha256"
    assert exact["scanned_files"] == 9  # every still under folder, notes.txt excluded
    assert exact["group_count"] == 3

    alpha = (_sha(b"alpha-bytes"), 3, [("a.jpg", True, "m1"), ("a_copy.JPG", False, None), ("a_again.png", False, None)])
    pairs = sorted(
        [
            (_sha(b""), 2, [("empty1.png", False, None), ("empty2.png", False, None)]),
            (_sha(b"beta" * 5000), 2, [("b1.webp", False, None), ("b2.webp", False, None)]),
        ]
    )
    assert _shape(exact) == [alpha, *pairs]
    assert exact["groups"][0]["media_ids"] == ["m1"]
    assert result["exact_group_count"] == 3
    assert result["hash_algorithm"] == "sha256"
    assert result["kind"] == "integrity"


def test_candidate_files_scope_pinned(tmp_path):
    store, folder = build_fixture(tmp_path)
    rows = [{"path": str(folder / "a.jpg")}, {"path": str(folder / "missing.jpg")}]
    got = [p.name for p in candidate_files(rows, [folder])]
    assert set(got) == {
        "a.jpg", "a_copy.JPG", "a_again.png", "b1.webp", "b2.webp", "b3.webp",
        "unique.bmp", "empty1.png", "empty2.png",
    }
    assert "notes.txt" not in got


def test_cancel_pinned(tmp_path):
    store, _ = build_fixture(tmp_path)
    result = find_integrity_groups(store, want_cancel=lambda: True)
    assert result["exact"]["status"] == "CANCELLED"
    assert result["exact"]["groups"] == []


# ── parity: dedupe engine vs legacy path ────────────────────────────────
def _both(monkeypatch, store, **kw):
    from semblon.duplicates import LEGACY_EXACT_ENV, find_exact_duplicate_groups

    monkeypatch.setenv(LEGACY_EXACT_ENV, "1")
    legacy = find_exact_duplicate_groups(store, **kw)
    monkeypatch.delenv(LEGACY_EXACT_ENV)
    new = find_exact_duplicate_groups(store, **kw)
    return legacy, new


def test_dedupe_engine_matches_legacy_on_fixture(tmp_path, monkeypatch):
    store, _ = build_fixture(tmp_path)
    legacy, new = _both(monkeypatch, store)
    assert new == legacy
    assert new["group_count"] == 3


def test_dedupe_engine_matches_legacy_on_hard_fixture(tmp_path, monkeypatch):
    import random

    store, folder = build_fixture(tmp_path)
    rnd = random.Random(7)
    sample = 64 * 1024
    base = bytes(rnd.getrandbits(8) for _ in range(sample * 6))
    tweaked = bytearray(base)
    tweaked[sample * 2] ^= 1  # same size + same partial samples, different bytes
    big = folder / "big"
    big.mkdir()
    (big / "p1.jpg").write_bytes(base)
    (big / "p2.jpg").write_bytes(base)
    (big / "p3.jpg").write_bytes(bytes(tweaked))
    (big / "p4.png").write_bytes(base + b"!")
    legacy, new = _both(monkeypatch, store)
    assert new == legacy
    sizes = sorted(g["count"] for g in new["groups"])
    assert sizes == [2, 2, 2, 3]


def test_dedupe_engine_cancel_and_progress_match_contract(tmp_path, monkeypatch):
    store, _ = build_fixture(tmp_path)
    legacy, new = _both(monkeypatch, store, want_cancel=lambda: True)
    assert new["status"] == legacy["status"] == "CANCELLED" and new["groups"] == []
    seen = []
    from semblon.duplicates import find_exact_duplicate_groups

    find_exact_duplicate_groups(store, on_progress=lambda i, n: seen.append((i, n)))
    assert seen and all(0 <= i <= n == 9 for i, n in seen)


def test_legacy_flag_forces_old_path(tmp_path, monkeypatch):
    import semblon.duplicates as dup

    store, _ = build_fixture(tmp_path)
    monkeypatch.setenv(dup.LEGACY_EXACT_ENV, "1")
    monkeypatch.setattr(dup, "scan_exact", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert dup.find_exact_duplicate_groups(store)["group_count"] == 3
