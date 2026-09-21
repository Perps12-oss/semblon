"""Live multi-person overlay scaffold tests. Fake camera / mocked frames only."""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from semblon.engine import pack_id
from semblon.live import live_capture
from tests.test_live import _FakeCapture, _live_model_env, _seed_named_alice


class _MultiDetModel:
    """Detector that returns every box on every frame (multi-person)."""

    def __init__(self, boxes: list[tuple[float, float, float, float, float]]):
        self.boxes = list(boxes)

    def detect(self, _frame, max_num=0, metric="default"):  # noqa: ARG002
        arr = np.array(self.boxes, dtype=np.float32)
        return arr, None


def test_overlay_gate_default_on(monkeypatch):
    from semblon.live_overlay import overlay_launch_allowed

    monkeypatch.delenv("SEMBLON_LIVE_OVERLAY", raising=False)
    monkeypatch.delenv("SEMBLON_WIRE_HOME_LIVE", raising=False)
    assert overlay_launch_allowed() is True
    assert overlay_launch_allowed(from_home=True) is True


def test_overlay_gate_opt_out_and_lab_explicit(monkeypatch):
    from semblon.live_overlay import overlay_launch_allowed

    monkeypatch.setenv("SEMBLON_LIVE_OVERLAY", "0")
    monkeypatch.setenv("SEMBLON_WIRE_HOME_LIVE", "0")
    assert overlay_launch_allowed() is False
    assert overlay_launch_allowed(from_home=True) is False
    assert overlay_launch_allowed(explicit_flag=True) is True
    monkeypatch.setenv("SEMBLON_WIRE_HOME_LIVE", "1")
    assert overlay_launch_allowed(from_home=True) is True


def test_format_overlay_label():
    from semblon.live_overlay import format_overlay_label

    assert format_overlay_label({"track_id": "det-aaaa-0", "decision": "UNKNOWN"}) == "det-aaaa-0 UNKNOWN"
    assert (
        format_overlay_label(
            {"track_id": "det-bbbb-1", "decision": "ACCEPT", "display_name": "Alice"}
        )
        == "det-bbbb-1 ACCEPT Alice"
    )
    assert format_overlay_label({"track_id": "det-cccc-2", "decision": None}) == "det-cccc-2"


def test_draw_overlay_on_fake_frame():
    from semblon.live_overlay import draw_overlay_bgr

    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    anns = [
        {
            "bbox": (10.0, 20.0, 60.0, 80.0),
            "track_id": "t-a",
            "decision": "ACCEPT",
            "display_name": "Alice",
        },
        {
            "bbox": (90.0, 30.0, 140.0, 90.0),
            "track_id": "t-b",
            "decision": "UNKNOWN",
            "display_name": None,
        },
    ]
    out = draw_overlay_bgr(frame, anns)
    assert out.shape == frame.shape
    assert out is not frame
    # Boxes leave non-black pixels where rectangles/text were drawn.
    assert int(out.sum()) > 0


def test_live_on_frame_emits_boxes_track_and_labels(tmp_path):
    store = tmp_path / "s.sqlite"
    live_pack = pack_id("0.test", {})
    vec_alice = _seed_named_alice(store, target_pack=live_pack)
    # Two simultaneous faces (large enough to pass quality gate).
    boxes = [
        (10.0, 10.0, 130.0, 130.0, 0.95),
        (150.0, 10.0, 270.0, 130.0, 0.94),
    ]
    det = _MultiDetModel(boxes)
    frames: list[tuple] = []

    def embed_two(app, _frame):  # noqa: ARG001
        return [
            {
                "bbox": (10.0, 10.0, 130.0, 130.0),
                "det_score": 0.95,
                "face_w": 120,
                "face_h": 120,
                "dim": 2,
                "embedding": vec_alice,
            },
            {
                "bbox": (150.0, 10.0, 270.0, 130.0),
                "det_score": 0.94,
                "face_w": 120,
                "face_h": 120,
                "dim": 2,
                "embedding": np.array([0.0, 1.0], dtype=np.float32),
            },
        ]

    def on_frame(frame, annotations):
        frames.append((frame.copy(), list(annotations)))

    with _live_model_env(det, embed_side_effect=embed_two):
        rec = live_capture(
            store,
            source=0,
            seconds=0.08,
            sample_hz=250.0,
            reembed_s=0.0,
            capture_factory=lambda _src: _FakeCapture(max_reads=24),
            on_frame=on_frame,
        )

    assert frames, "on_frame must receive frames"
    # At least one callback carries two boxes.
    multi = [anns for _fr, anns in frames if len(anns) >= 2]
    assert multi, "multi-person detections must reach overlay"
    sample = multi[-1]
    assert all("bbox" in a and "track_id" in a for a in sample)
    decisions = {a.get("decision") for a in sample if a.get("decision")}
    assert "ACCEPT" in decisions or "UNKNOWN" in decisions

    conn = sqlite3.connect(str(store))
    n_live_person = conn.execute(
        """
        SELECT COUNT(*)
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.run_id=? AND m.source_type='live' AND f.person_id IS NOT NULL
        """,
        (rec["run_id"],),
    ).fetchone()[0]
    conn.close()
    assert n_live_person == 0


def test_run_live_overlay_headless_does_not_assign_person(tmp_path, monkeypatch):
    from semblon.live_overlay import run_live_overlay

    store = tmp_path / "s.sqlite"
    live_pack = pack_id("0.test", {})
    vec_alice = _seed_named_alice(store, target_pack=live_pack)
    boxes = [(10.0, 10.0, 130.0, 130.0, 0.95)]
    det = _MultiDetModel(boxes)

    def embed_ok(app, _frame):  # noqa: ARG001
        x1, y1, x2, y2, score = boxes[0]
        return [
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": score,
                "face_w": int(x2 - x1),
                "face_h": int(y2 - y1),
                "dim": 2,
                "embedding": vec_alice,
            }
        ]

    recorded: list[list] = []

    monkeypatch.setenv("SEMBLON_LIVE_OVERLAY", "1")
    with _live_model_env(det, embed_side_effect=embed_ok):
        rec = run_live_overlay(
            store,
            source=0,
            seconds=0.06,
            sample_hz=250.0,
            reembed_s=0.0,
            show=False,
            explicit_flag=True,
            capture_factory=lambda _src: _FakeCapture(max_reads=20),
            on_overlay=lambda _fr, anns: recorded.append(list(anns)),
        )

    assert rec["frames"] >= 1
    assert recorded
    assert any(a.get("decision") in ("ACCEPT", "UNKNOWN") for anns in recorded for a in anns)

    conn = sqlite3.connect(str(store))
    n_live_person = conn.execute(
        """
        SELECT COUNT(*)
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.run_id=? AND m.source_type='live' AND f.person_id IS NOT NULL
        """,
        (rec["run_id"],),
    ).fetchone()[0]
    conn.close()
    assert n_live_person == 0


def test_run_live_overlay_refuses_home_when_opted_out(tmp_path, monkeypatch):
    from semblon.live_overlay import LiveOverlayError, run_live_overlay

    monkeypatch.setenv("SEMBLON_WIRE_HOME_LIVE", "0")
    with pytest.raises(LiveOverlayError, match="disabled"):
        run_live_overlay(
            tmp_path / "missing.sqlite",
            show=False,
            from_home=True,
            explicit_flag=False,
        )
