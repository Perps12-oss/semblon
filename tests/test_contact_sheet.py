"""Contact Sheet shell: the small backend pieces the Roll, loupe and first run rely on."""

import pytest

pytest.importorskip("PySide6")


def _seed(store, tmp_path, n=3):
    from semblon.store import connect, init_db

    conn = connect(store)
    init_db(conn)
    rows = []
    for i in range(n):
        day = 1_503_000_000_000_000_000 + i * 3_600_000_000_000
        rows.append((f"m{i}", "folder", str(tmp_path / f"{i}.jpg"), f"h{i}", 10, 10, day, 1))
    conn.executemany("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    QApplication.instance() or QApplication([])
    store = tmp_path / "s.sqlite"
    _seed(store, tmp_path)
    jobs = Application(store)
    made = ShellBridge(ArchiveModel(jobs), jobs)
    made._model.reload()
    yield made
    made.shutdown()


def test_day_detail_lists_a_days_photos_without_inventing_people(bridge, tmp_path):
    from semblon.native_shell.editorial import day_detail, scope_ids

    store = tmp_path / "s.sqlite"
    days = scope_ids(store).get("day", {})
    assert days
    label = next(iter(days))
    detail = day_detail(store, label)
    assert detail["count"] == len(days[label]) == 3
    assert detail["faceCount"] == 0
    assert detail["people"] == []
    assert day_detail(store, "no-such-day")["count"] == 0


def test_adding_something_that_is_not_a_folder_says_so_and_changes_nothing(bridge, tmp_path):
    before = bridge._jobs.archive_count()
    bridge.addFolderPath(str(tmp_path / "missing"))
    assert "folder" in bridge.noticeText.lower()
    assert bridge._jobs.archive_count() == before


def test_job_fraction_is_clamped(bridge):
    assert bridge.jobFraction == 0.0
    bridge._progress_total = 4
    bridge._progress_current = 1
    assert bridge.jobFraction == 0.25
    bridge._progress_current = 9
    assert bridge.jobFraction == 1.0


def test_matches_on_the_roll_replace_the_view_and_clear_restores_it(bridge):
    assert bridge._model.rowCount() == 3
    bridge._similar.set_rows([("m2", 0.9), ("m0", 0.5)])
    bridge.showMatchesOnRoll()
    assert bridge.matchesOnRoll is True
    assert bridge._model.rowCount() == 2
    bridge.clearMatches()
    assert bridge.matchesOnRoll is False
    assert bridge._model.rowCount() == 3


def test_bundled_fonts_register_so_windows_cannot_substitute_them(bridge):
    from semblon.native_shell.host import load_bundled_fonts

    families = " ".join(load_bundled_fonts())
    assert "Fraunces" in families
    assert "Inter" in families


def test_one_gui_remains(bridge):
    from pathlib import Path

    qml = Path("semblon/native_shell/qml")
    assert (qml / "Table.qml").is_file()
    assert not any((qml / name).exists() for name in ("Shell.qml", "HomeLaunchpad.qml"))
    for path in qml.glob("*.qml"):
        assert "QtQuick.Controls" not in path.read_text(encoding="utf-8"), path.name
