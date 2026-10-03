"""Structured Inspector sections — omit tags/ratings/map."""

from __future__ import annotations

from pathlib import Path

from semblon.engine import _sha256_file
from semblon.inspector_present import (
    inspector_section_lines,
    inspector_sections,
    media_detail_record,
)
from semblon.store import connect, init_db


def test_inspector_sections_wireable_only(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "lake"
    folder.mkdir()
    p = folder / "a.jpg"
    p.write_bytes(b"\xff\xd8\xff\xd9")  # minimal JPEG marker pair
    con = connect(store)
    try:
        init_db(con)
        con.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("m1", "folder", str(p), _sha256_file(p), 100, 80, 1_700_000_000_000_000_000, p.stat().st_size),
        )
        con.commit()
    finally:
        con.close()
    rec = media_detail_record(store, "m1")
    assert rec["width"] == 100
    sections = inspector_sections(rec)
    ids = {s["id"] for s in sections}
    assert "file" in ids
    assert "observations" in ids
    lines = inspector_section_lines(rec)
    blob = "\n".join(lines).lower()
    assert "tag" not in blob
    assert "rating" not in blob
    assert "map" not in blob
