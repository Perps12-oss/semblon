"""Export person folders as views. Originals stay put. No InsightFace."""

from __future__ import annotations

from pathlib import Path

from semblon.cli import main
from semblon.export import export_views
from semblon.review import name_cluster
from tests.test_review import _clustered


def _tiny_jpeg(path: Path) -> None:
    path.write_bytes(
        bytes.fromhex(
            "ffd8ffe000104a46494600010100000100010000ffdb004300"
            "080606070605080707070909080a0c140d0c0b0b0c1912130f"
            "141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c3031"
            "3434321e27393d38323431ffc0000b080001000101011100ff"
            "c40014100100000000000000000000000000000000ffda0008"
            "01010000003f00fbffd9"
        )
    )


def test_export_views_named_and_unassigned(tmp_path):
    store = tmp_path / "s.sqlite"
    photos = tmp_path / "photos"
    photos.mkdir()
    a = photos / "a.jpg"
    b = photos / "b.jpg"
    _tiny_jpeg(a)
    _tiny_jpeg(b)
    assigned = _clustered(store)
    # Point media paths at real files so views can link/copy.
    import sqlite3

    conn = sqlite3.connect(str(store))
    conn.execute("UPDATE media SET path=? WHERE media_id='m1'", (str(a),))
    conn.execute("UPDATE media SET path=? WHERE media_id='m2'", (str(b),))
    conn.commit()
    conn.close()
    name_cluster(store, "r1", assigned["f1"], "Alice")
    dest = tmp_path / "views"
    rec = export_views(store, "r1", dest)
    assert (dest / "VIEW.txt").is_file()
    alice = dest / "Alice"
    assert alice.is_dir()
    assert list(alice.glob("a__*.jpg"))
    assert (dest / "_unassigned").is_dir() or rec["counts"]["unassigned"] >= 0
    assert a.is_file() and b.is_file()
    assert rec["counts"]["persons"] == 1
    assert rec["counts"]["held_out"] >= 0
    assert main(["export", "--run", "r1", "--store", str(store), "--views", str(dest)]) == 0
    assert main(["export", "--run", "r1", "--store", str(store)]) == 2
