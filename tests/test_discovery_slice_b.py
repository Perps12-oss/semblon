"""Discovery slice B: hypothesis UX + Focus → People handoff. No auto-name."""

from __future__ import annotations

import pytest

from semblon.native_shell.presentation import (
    group_band_label,
    group_list_title,
    is_primary_safe_message,
)


def test_group_titles_keep_named_and_mark_hypotheses():
    assert group_list_title(named=True, names=["Ada"], kind="cluster", band="strong") == "Ada"
    assert group_list_title(named=False, names=[], kind="cluster", band="review") == "Candidate group"
    assert (
        group_list_title(named=False, names=[], kind="cluster", band="strong")
        == "Strong candidate group"
    )
    assert group_list_title(named=False, names=[], kind="unassigned", band="unassigned") == (
        "Unassigned face"
    )


def test_band_labels_say_name_to_confirm():
    assert "name to confirm" in group_band_label(
        named=False, kind="cluster", band="review"
    ).lower()
    assert group_band_label(named=True, kind="cluster", band="strong") == "Named person"


def test_slice_b_primary_messages_are_allowlisted():
    for line in (
        "Groups are hypotheses until you name them. A group is not a person.",
        "Opened the candidate group for this face.",
        "No candidate group for this face yet.",
    ):
        assert is_primary_safe_message(line)


def test_review_face_group_opens_people_on_cluster(tmp_path, monkeypatch):
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
                    "band": "review",
                    "face_count": 2,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {
                            "media_id": "m1",
                            "face_id": "f1",
                            "path": "/tmp/a.png",
                            "bbox": (10, 20, 40, 40),
                            "source_type": "folder",
                        },
                        {
                            "media_id": "m2",
                            "face_id": "f2",
                            "path": "/tmp/b.png",
                            "bbox": (5, 5, 20, 20),
                            "source_type": "folder",
                        },
                    ],
                }
            ],
            "counts": {
                "named_persons": 0,
                "review_required": 1,
                "strong": 0,
                "unassigned": 0,
                "clusters": 1,
            },
        }

    def fake_canvas(self, run_id=None):
        return {
            "faces": [
                {
                    "face_id": "f1",
                    "media_id": "m1",
                    "bbox_x1": 10,
                    "bbox_y1": 20,
                    "bbox_x2": 50,
                    "bbox_y2": 60,
                    "cluster_id": "c1",
                    "person_id": None,
                    "status": "ok",
                }
            ],
            "items": [],
            "track_lane_by_face": {},
            "track_lane_by_item": {},
        }

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr(Application, "canvas", fake_canvas)
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")

    photo = tmp_path / "a.png"
    photo.write_bytes(b"x")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h1", 200, 100, 1, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("m1")
    bridge.selectObservation("f1")
    assert bridge.canReviewFaceGroup is True
    bridge.reviewFaceGroup("f1")
    assert bridge.focusId == ""
    assert bridge.peopleOpen is True
    assert bridge.selectedSubject == "c1"
    assert bridge.selectedTitle == "Candidate group"
    assert bridge.peopleNote == "Opened the candidate group for this face."
    assert "need review" in bridge.reviewCountText
    shutdown_shell(engine)


def test_review_face_group_without_board_row_stays_honest(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    monkeypatch.setattr(
        Application,
        "board",
        lambda self, run_id=None: {"items": [], "counts": {}},
    )
    monkeypatch.setattr(
        Application,
        "canvas",
        lambda self, run_id=None: {
            "faces": [
                {
                    "face_id": "f1",
                    "media_id": "m1",
                    "bbox_x1": 10,
                    "bbox_y1": 20,
                    "bbox_x2": 50,
                    "bbox_y2": 60,
                    "cluster_id": None,
                    "person_id": None,
                    "status": "ok",
                }
            ],
            "items": [],
            "track_lane_by_face": {},
            "track_lane_by_item": {},
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
        ("m1", "folder", str(photo), "h1", 200, 100, 1, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("m1")
    bridge.selectObservation("f1")
    assert bridge.canReviewFaceGroup is False
    bridge.reviewFaceGroup("f1")
    assert bridge.peopleOpen is False
    assert bridge.resultText == "No candidate group for this face yet."
    shutdown_shell(engine)
