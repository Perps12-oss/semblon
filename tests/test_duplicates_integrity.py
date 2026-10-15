"""Exact duplicate integrity + navigation into Compare (no delete / no identity)."""

from __future__ import annotations

import inspect
import threading
from pathlib import Path

from semblon.duplicates import (
    HASH_ALGORITHM,
    NEAR_STATUS,
    candidate_files,
    find_exact_duplicate_groups,
    group_lines,
    scan_dirs_from_media,
)
from semblon.engine import _sha256_file
from semblon.product_features import build_product_registry
from semblon.store import connect, init_db


class _FakeStatus:
    def __init__(self) -> None:
        self.value = ""

    def set(self, text: str) -> None:
        self.value = str(text)


class _FakeRoot:
    """Collects ``after`` callbacks so tests can flush the UI marshal path."""

    def __init__(self) -> None:
        self.callbacks: list = []

    def after(self, _ms, fn):
        self.callbacks.append(fn)
        return None

    def update_idletasks(self) -> None:
        return None

    def flush(self) -> None:
        pending = list(self.callbacks)
        self.callbacks.clear()
        for fn in pending:
            fn()


def _seed_media(store: Path, items: list[tuple[str, Path]]) -> None:
    con = connect(store)
    try:
        init_db(con)
        for mid, path in items:
            digest = _sha256_file(path)
            con.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (
                    mid,
                    "folder",
                    str(path),
                    digest,
                    1,
                    1,
                    0,
                    path.stat().st_size,
                ),
            )
        con.commit()
    finally:
        con.close()


def test_hash_algorithm_is_sha256():
    assert HASH_ALGORITHM == "sha256"
    assert "sha256" in _sha256_file.__code__.co_names


def test_exact_duplicate_groups_from_sibling_files(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    a = folder / "a.jpg"
    b = folder / "b.jpg"
    c = folder / "c.jpg"
    payload = b"identical-bytes-for-dupe-test"
    a.write_bytes(payload)
    b.write_bytes(payload)
    c.write_bytes(b"different-content-xyz")
    # Only one media row can hold this sha256 (UNIQUE) — sibling b is on disk only.
    _seed_media(store, [("m1", a), ("m2", c)])

    result = find_exact_duplicate_groups(store)
    assert result["status"] == "SUCCESS"
    assert result["hash_algorithm"] == "sha256"
    assert result["near_status"] == NEAR_STATUS
    assert result["group_count"] == 1
    group = result["groups"][0]
    assert group["count"] == 2
    paths = {Path(m["path"]).name for m in group["members"]}
    assert paths == {"a.jpg", "b.jpg"}
    assert "m1" in group["media_ids"]
    assert group["kind"] == "exact"


def test_unique_files_do_not_group(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    a = folder / "a.jpg"
    b = folder / "b.jpg"
    a.write_bytes(b"one")
    b.write_bytes(b"two")
    _seed_media(store, [("m1", a), ("m2", b)])
    result = find_exact_duplicate_groups(store)
    assert result["status"] == "EMPTY"
    assert result["groups"] == []


def test_deterministic_grouping_order(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    files = []
    for name in ("z.jpg", "a.jpg", "m.jpg"):
        p = folder / name
        p.write_bytes(b"same")
        files.append(p)
    # One library row for the shared hash.
    _seed_media(store, [("m1", files[0])])
    r1 = find_exact_duplicate_groups(store)
    r2 = find_exact_duplicate_groups(store)
    assert [g["content_hash"] for g in r1["groups"]] == [
        g["content_hash"] for g in r2["groups"]
    ]
    assert [m["path"] for m in r1["groups"][0]["members"]] == [
        m["path"] for m in r2["groups"][0]["members"]
    ]


def test_missing_store_is_error(tmp_path):
    result = find_exact_duplicate_groups(tmp_path / "missing.sqlite")
    assert result["status"] == "ERROR"
    assert "unavailable" in (result.get("reason") or "").lower()


def test_group_lines_empty_and_success():
    empty = group_lines({"status": "EMPTY", "reason": "No exact duplicate candidates were found.", "scanned_files": 3})
    assert "No exact duplicate" in empty[0]
    ok = group_lines(
        {
            "status": "SUCCESS",
            "kind": "exact",
            "groups": [{"count": 2, "media_ids": ["a"], "content_hash": "x"}],
            "near_status": NEAR_STATUS,
        }
    )
    assert "exact duplicate" in ok[0].lower()
    assert any("SHA-256" in ln for ln in ok)
    # Near is a separate integrity path (AVAILABLE) — exact lines state Exact basis.
    assert any("Exact" in ln or "SHA-256" in ln for ln in ok)


def test_scan_dirs_and_candidates(tmp_path):
    folder = tmp_path / "lib"
    folder.mkdir()
    p = folder / "x.jpg"
    p.write_bytes(b"x")
    (folder / "y.png").write_bytes(b"y")
    (folder / "notes.txt").write_bytes(b"nope")
    rows = [{"path": str(p), "media_id": "m", "sha256": "h"}]
    dirs = scan_dirs_from_media(rows)
    assert folder.resolve() in {d.resolve() for d in dirs}
    files = candidate_files(rows, dirs)
    names = {f.name for f in files}
    assert "x.jpg" in names and "y.png" in names
    assert "notes.txt" not in names


def test_registry_duplicate_commands():
    reg = build_product_registry()
    ids = {c.id: c.label for c in reg.commands()}
    assert ids["library.duplicates"] == "Find Duplicates"
    assert "duplicates.open_group" in ids


def test_duplicates_module_safety():
    import semblon.duplicates as mod

    src = inspect.getsource(mod)
    assert "faces.person_id" not in src
    assert "os.remove" not in src
    assert "unlink(" not in src
    assert "DELETE FROM" not in src

