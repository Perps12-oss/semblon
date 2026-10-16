"""Discovery slice C: named person → days → Time neighbours. No auto-name."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from semblon.native_shell.presentation import is_primary_safe_message


def _mtime_ns(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, 12, 0, tzinfo=timezone.utc).timestamp() * 1e9)


def test_slice_c_primary_messages_are_allowlisted():
    for line in (
        "No dated photos for this person yet.",
        "Opened this person in Time.",
    ):
        assert is_primary_safe_message(line)


def test_person_days_and_browse_in_time(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "kind": "cluster",
                    "cluster_id": "c1",
                    "band": "strong",
                    "face_count": 2,
                    "named": True,
                    "person_names": ["Ada"],
                    "members": [
                        {
                            "media_id": "m1",
                            "face_id": "f1",
                            "person_id": "p-ada",
                            "person_name": "Ada",
                            "source_type": "folder",
                        },
                        {
                            "media_id": "m2",
                            "face_id": "f2",
                            "person_id": "p-ada",
                            "person_name": "Ada",
                            "source_type": "folder",
                        },
                    ],
                }
            ],
            "counts": {
                "named_persons": 1,
                "review_required": 0,
                "strong": 1,
                "unassigned": 0,
                "clusters": 1,
            },
        }

    def fake_history(store, *, person, run_id=None):
        assert person == "p-ada"
        return {
            "person_id": "p-ada",
            "display_name": "Ada",
            "sightings": 3,
            "items": [
                {
                    "face_id": "f1",
                    "media_id": "m1",
                    "source_type": "folder",
                    "when": "2024-06-15T12:00:00",
                    "when_ns": 1,
                },
                {
                    "face_id": "f2",
                    "media_id": "m2",
                    "source_type": "folder",
                    "when": "2024-07-01T09:00:00",
                    "when_ns": 2,
                },
                {
                    "face_id": "f3",
                    "media_id": "m3",
                    "source_type": "folder",
                    "when": "2024-06-15T18:00:00",
                    "when_ns": 3,
                },
            ],
            "presence": [],
        }

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr("semblon.memory.history", fake_history)
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")

    photo1 = tmp_path / "a.png"
    photo2 = tmp_path / "b.png"
    photo1.write_bytes(b"x")
    photo2.write_bytes(b"y")
    mtime_july = _mtime_ns(2024, 7, 1)
    mtime_june = _mtime_ns(2024, 6, 15)
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo1), "h1", 32, 32, mtime_june, 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m2", "folder", str(photo2), "h2", 32, 32, mtime_july, 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m3", "folder", str(photo1), "h3", 32, 32, mtime_june, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openPeople()
    bridge.selectGroup("c1")
    assert bridge.selectedPersonId == "p-ada"
    assert bridge.canBrowsePersonTime is True
    days = bridge.personDays
    assert [d["day"] for d in days] == ["2024-07-01", "2024-06-15"]
    assert days[1]["count"] == 2
    assert days[1]["mediaId"] == "m3"
    bridge.browseSelectedPersonInTime()
    assert bridge.peopleOpen is False
    assert bridge.focusId == "m2"
    assert bridge.scopeKind == "day"
    assert bridge.scopeLabel == "2024-07-01"
    assert bridge.resultText == "Opened this person in Time."
    shutdown_shell(engine)


def test_unnamed_group_has_no_person_days(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    monkeypatch.setattr(
        Application,
        "board",
        lambda self, run_id=None: {
            "items": [
                {
                    "kind": "cluster",
                    "cluster_id": "c1",
                    "band": "review",
                    "face_count": 1,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {
                            "media_id": "m1",
                            "face_id": "f1",
                            "person_id": None,
                            "source_type": "folder",
                        }
                    ],
                }
            ],
            "counts": {},
        },
    )
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")

    photo = tmp_path / "a.png"
    photo.write_bytes(b"x")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h1", 32, 32, 1, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openPeople()
    bridge.selectGroup("c1")
    assert bridge.canBrowsePersonTime is False
    assert bridge.personDays == []
    bridge.browseSelectedPersonInTime()
    assert bridge.peopleNote == "No dated photos for this person yet."
    assert bridge.focusId == ""
    shutdown_shell(engine)
