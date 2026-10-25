"""Capture date beats file date; Recycle-Bin removal takes a picture out of the Roll and its month."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from semblon.archive_session import ArchiveSession
from semblon.native_shell.sections import build_sections
from semblon.store import connect, init_db


def _jpeg(path: Path, taken: str | None = None, offset: str | None = None) -> Path:
    from PIL import Image

    img = Image.new("RGB", (64, 48), (120, 80, 40))
    exif = Image.Exif()
    if taken:
        ifd = exif.get_ifd(0x8769)
        ifd[0x9003] = taken
        if offset:
            ifd[0x9011] = offset
    img.save(path, "JPEG", exif=exif)
    return path


def _store(tmp_path: Path, files: list[Path]) -> Path:
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for i, f in enumerate(files):
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (f"m{i}", "folder", str(f), f"h{i}", 64, 48, int(f.stat().st_mtime_ns), 1),
        )
    conn.commit()
    conn.close()
    return store


def _set_saved_time(path: Path, year: int) -> None:
    stamp = time.mktime((year, 6, 15, 12, 0, 0, 0, 0, -1))
    os.utime(path, (stamp, stamp))


def test_camera_date_wins_over_the_files_saved_time(tmp_path):
    photo = _jpeg(tmp_path / "a.jpg", "2021:07:04 23:50:00")
    _set_saved_time(photo, 2030)
    session = ArchiveSession(_store(tmp_path, [photo]))
    item = session.media("m0")
    assert item.day == "2021-07-04"
    assert item.taken.hour == 23 and item.taken.minute == 50


def test_camera_offset_orders_by_the_real_moment_but_the_day_is_the_cameras_evening(tmp_path):
    # 23:50 in Tokyo (+09:00) is 14:50 UTC: later than a 20:00 UTC photo taken the same calendar date
    tokyo = _jpeg(tmp_path / "tokyo.jpg", "2021:07:04 23:50:00", "+09:00")
    london = _jpeg(tmp_path / "london.jpg", "2021:07:04 20:00:00", "+00:00")
    session = ArchiveSession(_store(tmp_path, [tokyo, london]))
    assert session.media("m0").day == "2021-07-04"
    assert [m.path for m in session.window(0, 2)] == [str(london), str(tokyo)]


def test_missing_camera_date_falls_back_to_saved_time(tmp_path):
    plain = _jpeg(tmp_path / "plain.jpg")
    png = tmp_path / "p.png"
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(QColor("#123456"))
    img.save(str(png))
    _set_saved_time(plain, 2019)
    _set_saved_time(png, 2018)
    session = ArchiveSession(_store(tmp_path, [plain, png]))
    assert session.media("m0").day == "2019-06-15"
    assert session.media("m1").day == "2018-06-15"
    assert session.days() == ["2019-06-15", "2018-06-15"]


def test_a_copied_file_lands_on_the_original_day(tmp_path):
    original = _jpeg(tmp_path / "orig.jpg", "2020:02:29 10:00:00")
    _set_saved_time(original, 2020)
    copy = tmp_path / "copy.jpg"
    shutil.copyfile(original, copy)  # a fresh saved time, as after a copy or download
    session = ArchiveSession(_store(tmp_path, [original, copy]))
    assert session.media("m1").day == "2020-02-29"
    assert set(session.days()) == {"2020-02-29"}


def test_binned_photo_leaves_the_roll_and_its_month_count(tmp_path):
    from semblon.forget import forget_files

    files = [
        _jpeg(tmp_path / "a.jpg", "2024:09:02 10:00:00"),
        _jpeg(tmp_path / "b.jpg", "2024:09:03 10:00:00"),
        _jpeg(tmp_path / "c.jpg", "2024:08:20 10:00:00"),
    ]
    store = _store(tmp_path, files)
    session = ArchiveSession(store)
    months = {m["key"]: m["count"] for m in build_sections(session.days(), 4)["months"]}
    assert months == {"2024-09": 2, "2024-08": 1}

    assert forget_files(store, [str(files[1])]) == 1
    session.invalidate_reads()
    assert session.count() == 2
    assert [m.path for m in session.window(0, 10)] == [str(files[0]), str(files[2])]
    months = {m["key"]: m["count"] for m in build_sections(session.days(), 4)["months"]}
    assert months == {"2024-09": 1, "2024-08": 1}
    assert files[1].exists()  # the file itself is never touched here


def test_forgetting_a_binned_photo_keeps_the_entry_of_the_copy_that_stays(tmp_path):
    from semblon.forget import forget_files

    keep = _jpeg(tmp_path / "keep.jpg", "2024:01:01 10:00:00")
    gone = _jpeg(tmp_path / "gone.jpg", "2024:01:01 10:00:00")
    store = _store(tmp_path, [gone])
    conn = connect(store)
    conn.execute("INSERT INTO work_items (path, mtime_ns, byte_size, media_id) VALUES (?,?,?,?)", (str(keep), 1, 1, "m0"))
    conn.execute("INSERT INTO work_items (path, mtime_ns, byte_size, media_id) VALUES (?,?,?,?)", (str(gone), 1, 1, "m0"))
    conn.commit()
    conn.close()
    # an exact copy shares one entry: it must now point at the file that stays
    assert forget_files(store, [str(gone)], keep=[str(keep)]) == 0
    session = ArchiveSession(store)
    assert session.media("m0").path == str(keep)
    conn = connect(store)
    paths = [r[0] for r in conn.execute("SELECT path FROM work_items")]
    conn.close()
    assert paths == [str(keep)]
