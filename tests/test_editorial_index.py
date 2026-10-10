"""Editorial index reads store rows. It does not invent relationships."""

from semblon.native_shell.editorial import (
    SAVED_VIEWS_NOTE,
    SPATIAL_NOTE,
    folder_rows,
    month_heading,
    source_counts,
    year_rows,
)
from semblon.store import connect, init_db


def test_month_heading_uses_a_real_day():
    assert month_heading("2017-08-12") == "August, 2017"
    assert month_heading("") == ""
    assert month_heading("not-a-day") == ""


def test_index_counts_come_from_media_rows(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.executemany(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            [
                ("p1", "folder", str(tmp_path / "2017" / "a.jpg"), "h1", 10, 10, 1_503_000_000_000_000_000, 1),
                ("p2", "folder", str(tmp_path / "2018" / "b.jpg"), "h2", 10, 10, 1_530_000_000_000_000_000, 1),
                ("v1", "video", str(tmp_path / "2017" / "c.mp4"), "h3", 10, 10, 1_503_100_000_000_000_000, 1),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    counts = source_counts(store)
    assert counts["folder"] == 2
    assert counts["video"] == 1
    years = {row["label"]: row["count"] for row in year_rows(store)}
    assert years["2017"] == 2
    assert years["2018"] == 1
    folders = {row["label"]: row["count"] for row in folder_rows(store)}
    assert folders["2017"] == 2
    assert folders["2018"] == 1
    assert "not stored" in SAVED_VIEWS_NOTE.lower() or "not" in SAVED_VIEWS_NOTE.lower()
    assert "no relationship" in SPATIAL_NOTE.lower()
    assert "line" in SPATIAL_NOTE.lower()
