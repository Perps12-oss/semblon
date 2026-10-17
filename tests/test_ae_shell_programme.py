"""A–E shell programme: OCR Field, person-only filter, inbox, tracks. Offscreen."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pytest

from semblon.native_shell.presentation import is_primary_safe_message


def _mtime_ns(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, 12, 0, tzinfo=timezone.utc).timestamp() * 1e9)


def test_programme_primary_messages_allowlisted():
    for line in (
        "Showing only Ada.",
        "Showing the full archive again.",
        "Opened overlooked faces for review.",
        "No overlooked faces right now.",
        "Opened this person.",
        "Text search: 1 photos with matching text.",
    ):
        assert is_primary_safe_message(line), line


def test_text_search_sets_field_media_ids(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.observers import observe_bgr
    from semblon.store import connect, init_db

    photo = tmp_path / "a.png"
    photo.write_bytes(b"x")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h1", 32, 32, _mtime_ns(2024, 1, 1), 1),
    )
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','0.0.1','pack-a',2,'l2','{}','{}','x64','native')"""
    )
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    with patch("semblon.observers.ocr_image", return_value={"text": "SEMBLON GATE", "score": 1.0}):
        observe_bgr(
            conn,
            observation_id="o1",
            run_id="r1",
            img=np.zeros((8, 8, 3), dtype=np.uint8),
            observers=("text",),
        )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.setSearchMode("text")
    bridge.submitCommand("gate")
    assert bridge.similarBasis == "text"
    assert "text" in bridge.similarBasisLabel.lower()
    assert bridge._model.media_ids() == ["m1"]
    shutdown_shell(engine)


def test_person_only_filter_tracks_and_clear(tmp_path, monkeypatch):
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
                    "face_count": 1,
                    "named": True,
                    "person_names": ["Ada"],
                    "members": [
                        {
                            "media_id": "m1",
                            "face_id": "f1",
                            "person_id": "p-ada",
                            "source_type": "folder",
                        }
                    ],
                },
                {
                    "kind": "track",
                    "track_id": "t1",
                    "face_count": 1,
                    "members": [
                        {"media_id": "m2", "face_id": "f2", "source_type": "folder"}
                    ],
                },
            ],
            "counts": {"named_persons": 1, "review_required": 0, "strong": 1, "unassigned": 0},
        }

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr(
        "semblon.memory.history",
        lambda store, *, person, run_id=None: {
            "items": [
                {
                    "media_id": "m1",
                    "source_type": "folder",
                    "when": "2024-06-15T12:00:00",
                }
            ]
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
        ("m1", "folder", str(photo), "h1", 32, 32, _mtime_ns(2024, 6, 15), 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m2", "folder", str(photo), "h2", 32, 32, _mtime_ns(2024, 6, 16), 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openPeople()
    rows = list(bridge._people._rows)
    kinds = {r["kind"] for r in rows}
    assert "track" in kinds
    assert any(r["title"] == "Track (not a person)" for r in rows)
    bridge.selectGroup("c1")
    bridge.showSelectedPersonOnly()
    assert bridge.personFieldFilterActive is True
    assert bridge._model.media_ids() == ["m1"]
    assert "Ada" in bridge.resultText
    bridge.clearPersonFieldFilter()
    assert bridge.personFieldFilterActive is False
    shutdown_shell(engine)


def test_open_unresolved_inbox(tmp_path, monkeypatch):
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
                    "kind": "unassigned",
                    "face_id": "f-u1",
                    "band": "unassigned",
                    "face_count": 1,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {
                            "media_id": "m1",
                            "face_id": "f-u1",
                            "source_type": "folder",
                        }
                    ],
                }
            ],
            "counts": {"unassigned": 1, "review_required": 1, "named_persons": 0, "strong": 0},
        },
    )
    monkeypatch.setattr(
        Application,
        "inbox",
        lambda self, **kwargs: {
            "counts": {"UNKNOWN": 0, "REVIEW_REQUIRED": 1, "REJECTED": 0},
            "items": [{"face_id": "f-u1", "bucket": "REVIEW_REQUIRED"}],
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
    bridge.openUnresolvedInbox()
    assert bridge.peopleOpen is True
    assert bridge.selectedSubject == "f-u1"
    assert "overlooked" in bridge.peopleNote.lower()
    shutdown_shell(engine)
