"""Multi-person live overlays and identity firewall regressions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.engine import pack_id
from semblon.ingest import CancelledError
from semblon.live import LiveError, build_frame_overlays, live_capture
from semblon.review import name_cluster
from tests.test_live import _FakeCapture, _live_model_env, _seed_named_alice
from tests.test_review import _clustered


class _MultiDetModel:
    """Returns N boxes every frame (deterministic multi-person fixture)."""

    def __init__(self, per_frame: list[list[tuple[float, float, float, float, float]]]):
        self.per_frame = per_frame
        self.i = 0
        self.last_boxes = per_frame[0] if per_frame else []

    def detect(self, _frame, max_num=0, metric="default"):  # noqa: ARG002
        if self.i < len(self.per_frame):
            self.last_boxes = self.per_frame[self.i]
        else:
            self.last_boxes = self.per_frame[-1] if self.per_frame else []
        self.i += 1
        if not self.last_boxes:
            return np.zeros((0, 5), dtype=np.float32), None
        return np.array(self.last_boxes, dtype=np.float32), None


def test_build_frame_overlays_unknown_and_named():
    dets = [
        {"det_id": "det-aaaa1111-0", "bbox": (1, 2, 3, 4)},
        {"det_id": "det-aaaa1111-1", "bbox": (10, 20, 30, 40)},
    ]
    mapping = {"det-aaaa1111-0": "det-aaaa1111-0", "det-aaaa1111-1": "det-aaaa1111-1"}
    state = {
        "det-aaaa1111-0": {
            "decision": "ACCEPT",
            "display_name": "Alice",
            "evidence_person_id": "p1",
        },
        "det-aaaa1111-1": {"decision": "UNKNOWN", "display_name": None, "evidence_person_id": None},
    }
    rows = build_frame_overlays(dets, mapping, state)
    assert len(rows) == 2
    assert rows[0]["label"] == "Alice"
    assert rows[1]["label"] == "UNKNOWN"
    assert rows[0]["track_id"] != rows[1]["track_id"]
    assert rows[0]["track_id"].endswith("-0")
    assert rows[1]["track_id"].endswith("-1")
    assert rows[0]["track_id"] != rows[0].get("evidence_person_id")


def test_live_zero_faces_emits_empty_overlays(tmp_path):
    store = tmp_path / "s.sqlite"
    det = _MultiDetModel([[] for _ in range(8)])
    frames = []

    def embed_ok(app, _frame):  # noqa: ARG001
        return []

    with _live_model_env(det, embed_side_effect=embed_ok):
        try:
            rec = live_capture(
                store,
                source=0,
                seconds=0.0,
                sample_hz=500.0,
                reembed_s=0.0,
                on_frame=frames.append,
                cancel=lambda: len(frames) >= 4,
                capture_factory=lambda _src: _FakeCapture(max_reads=16),
            )
        except CancelledError as e:
            rec = {"frames": (e.timings or {}).get("frames") or len(frames)}
    assert (rec.get("frames") or 0) >= 1 or len(frames) >= 1
    assert frames
    assert all(len(f["overlays"]) == 0 for f in frames)


def test_live_multi_face_independent_boxes_and_no_person_stamp(tmp_path):
    store = tmp_path / "s.sqlite"
    live_pack = pack_id("0.test", {})
    vec_alice = _seed_named_alice(store, target_pack=live_pack)
    # Separated boxes ≥80px side so status=ok (CLUSTER_MIN_SIDE).
    left = (10.0, 10.0, 100.0, 100.0, 0.95)
    right = (160.0, 10.0, 250.0, 100.0, 0.95)
    far = (10.0, 140.0, 100.0, 230.0, 0.9)
    schedule = [
        [],
        [left],
        [left, right],
        [left, right, far],
        [left, right, far],
        [right, far],
        [far],
        [],
    ]
    det = _MultiDetModel(schedule)
    snaps = []

    def embed_ok(app, _frame):
        out = []
        for box in app.det_model.last_boxes:
            x1, y1, x2, y2, score = box
            # Left box matches Alice; others are UNKNOWN vectors.
            if abs(x1 - 10.0) < 1.0 and abs(y1 - 10.0) < 1.0:
                emb = vec_alice
            else:
                emb = np.array([0.0, 1.0], dtype=np.float32)
            out.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "det_score": score,
                    "face_w": int(x2 - x1),
                    "face_h": int(y2 - y1),
                    "dim": 2,
                    "embedding": emb,
                }
            )
        return out

    with _live_model_env(det, embed_side_effect=embed_ok):
        # Frame-driven (not wall-clock): Windows CI is too slow for seconds=0.08.
        cap = _FakeCapture(max_reads=32)
        try:
            rec = live_capture(
                store,
                source=0,
                seconds=0.0,
                sample_hz=500.0,
                reembed_s=0.0,
                on_frame=snaps.append,
                cancel=lambda: len(snaps) >= len(schedule),
                capture_factory=lambda _src: cap,
            )
        except CancelledError as e:
            rec = {
                "run_id": e.run_id,
                "tracks": (e.timings or {}).get("tracks") or 0,
            }

    counts = [len(s["overlays"]) for s in snaps]
    multi = [s for s in snaps if len(s["overlays"]) >= 2]
    assert multi, f"expected simultaneous multi-face frames; overlay counts={counts}"
    for s in multi:
        boxes = [tuple(o["bbox"]) for o in s["overlays"]]
        assert len(boxes) == len(set(boxes))
        track_ids = [o["track_id"] for o in s["overlays"]]
        assert len(track_ids) == len(set(track_ids))

    three = next((s for s in snaps if len(s["overlays"]) >= 3), None)
    assert three is not None, f"expected a 3-face frame; overlay counts={counts}"
    labels = {o["label"] for o in three["overlays"]}
    assert "UNKNOWN" in labels
    # Alice may appear once identity evidence exists; never invent other names.
    assert labels <= {"Alice", "UNKNOWN"}

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
    # Ensure Alice's named person exists from stills naming, but live faces stay unassigned.
    n_persons = conn.execute("SELECT COUNT(*) FROM persons WHERE status='active'").fetchone()[0]
    n_tracks = conn.execute(
        "SELECT COUNT(*) FROM tracks WHERE run_id=?", (rec["run_id"],)
    ).fetchone()[0]
    conn.close()
    assert n_live_person == 0
    assert n_persons >= 1
    assert max(n_tracks, int(rec.get("tracks") or 0)) >= 2


def test_live_identity_does_not_leak_across_boxes(tmp_path):
    store = tmp_path / "s.sqlite"
    live_pack = pack_id("0.test", {})
    vec_alice = _seed_named_alice(store, target_pack=live_pack)
    left = (10.0, 10.0, 100.0, 100.0, 0.95)
    right = (180.0, 10.0, 270.0, 100.0, 0.95)
    det = _MultiDetModel([[left, right] for _ in range(10)])
    snaps = []

    def embed_ok(app, _frame):
        out = []
        for box in app.det_model.last_boxes:
            x1, y1, x2, y2, score = box
            emb = vec_alice if x1 < 100 else np.array([0.0, 1.0], dtype=np.float32)
            out.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "det_score": score,
                    "face_w": int(x2 - x1),
                    "face_h": int(y2 - y1),
                    "dim": 2,
                    "embedding": emb,
                }
            )
        return out

    with _live_model_env(det, embed_side_effect=embed_ok):
        cap = _FakeCapture(max_reads=24)
        try:
            live_capture(
                store,
                source=0,
                seconds=0.0,
                sample_hz=500.0,
                reembed_s=0.0,
                on_frame=snaps.append,
                cancel=lambda: len(snaps) >= 6,
                capture_factory=lambda _src: cap,
            )
        except CancelledError:
            pass

    labeled = [s for s in snaps if any(o.get("decision") for o in s["overlays"])]
    assert labeled, f"expected identify decisions; frames={len(snaps)}"
    for s in labeled:
        by_x = sorted(s["overlays"], key=lambda o: o["bbox"][0])
        if len(by_x) < 2:
            continue
        # Right face must not inherit Alice merely because left matched.
        if by_x[0]["label"] == "Alice":
            assert by_x[1]["label"] == "UNKNOWN"
