"""Live capture engine tests. Portable seams only (capture/model I/O)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.cluster import cluster_run
from semblon.engine import pack_id
from semblon.ingest import CancelledError
from semblon.live import LiveError, live_capture
from semblon.progress import KIND_COMPLETED, KIND_FAILED
from semblon.review import name_cluster
from tests.test_review import _clustered


class _FakeCapture:
    def __init__(self, *, max_reads: int = 64, fail_reads: set[int] | None = None):
        self.max_reads = max_reads
        self.fail_reads = fail_reads or set()
        self.reads = 0

    def read(self):
        i = self.reads
        self.reads += 1
        if i in self.fail_reads or i >= self.max_reads:
            return False, None
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, :, 0] = i % 255
        return True, frame

    def release(self):
        return None


class _DetModel:
    def __init__(self, boxes: list[tuple[float, float, float, float, float]]):
        self.boxes = boxes or [(10.0, 10.0, 130.0, 130.0, 0.95)]
        self.i = 0
        self.last_box = self.boxes[0]

    def detect(self, _frame, max_num=0, metric="default"):  # noqa: ARG002
        if self.i < len(self.boxes):
            self.last_box = self.boxes[self.i]
        else:
            self.last_box = self.boxes[-1]
        self.i += 1
        x1, y1, x2, y2, score = self.last_box
        return np.array([[x1, y1, x2, y2, score]], dtype=np.float32), None


@contextmanager
def _live_model_env(det_model: _DetModel, *, embed_side_effect):
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    app = type("App", (), {"det_model": det_model})()
    loaded = type("Loaded", (), {"app": app})()
    with ExitStack() as stack:
        stack.enter_context(patch("semblon.providers.FaceKitProvider.load", return_value=loaded))
        stack.enter_context(patch("semblon.live.embed_bgr", side_effect=embed_side_effect))
        stack.enter_context(patch("semblon.engine.discover_weight_hashes", return_value={}))
        stack.enter_context(patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}))
        yield


def _seed_named_alice(store: Path, *, target_pack: str) -> np.ndarray:
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    conn = sqlite3.connect(str(store))
    vec = conn.execute(
        """
        SELECT f.embedding
        FROM faces f
        JOIN persons p ON p.person_id = f.person_id
        WHERE p.display_name='Alice'
        ORDER BY f.face_id
        LIMIT 1
        """
    ).fetchone()[0]
    conn.execute("UPDATE faces SET embedding_pack=? WHERE run_id='r1'", (target_pack,))
    conn.commit()
    conn.close()
    return np.frombuffer(vec, dtype=np.float32).copy()


def test_live_identifies_vs_named_person(tmp_path):
    store = tmp_path / "s.sqlite"
    live_pack = pack_id("0.test", {})
    vec_alice = _seed_named_alice(store, target_pack=live_pack)
    boxes = [(10.0 + i, 10.0, 130.0 + i, 130.0, 0.95) for i in range(20)]
    det = _DetModel(boxes)

    def embed_ok(app, _frame):
        x1, y1, x2, y2, score = app.det_model.last_box
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

    with _live_model_env(det, embed_side_effect=embed_ok):
        rec = live_capture(
            store,
            source=0,
            seconds=0.08,
            sample_hz=250.0,
            reembed_s=0.0,
            capture_factory=lambda _src: _FakeCapture(max_reads=24),
        )

    assert rec["source_type"] == "live"
    assert rec["tracks"] >= 1
    assert rec["identified_accept"] >= 1
    assert rec["failed_embeds"] >= 0

    conn = sqlite3.connect(str(store))
    src = conn.execute("SELECT source_type FROM media WHERE media_id=?", (rec["media_id"],)).fetchone()[0]
    n_tracks = conn.execute("SELECT COUNT(*) FROM tracks WHERE run_id=?", (rec["run_id"],)).fetchone()[0]
    n_members = conn.execute(
        """
        SELECT COUNT(*)
        FROM track_members tm
        JOIN tracks t ON t.track_id = tm.track_id
        WHERE t.run_id=?
        """,
        (rec["run_id"],),
    ).fetchone()[0]
    decision_rows = conn.execute(
        """
        SELECT d.policy_json, p.display_name
        FROM decisions d
        LEFT JOIN persons p ON p.person_id = d.person_id
        WHERE d.run_id=? AND d.kind='identify'
        """,
        (rec["run_id"],),
    ).fetchall()
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
    n_live_cluster = conn.execute(
        """
        SELECT COUNT(*)
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.run_id=? AND m.source_type='live' AND f.cluster_id IS NOT NULL
        """,
        (rec["run_id"],),
    ).fetchone()[0]
    conn.close()
    n_ident = 0
    for pol, display_name in decision_rows:
        policy = json.loads(pol or "{}")
        if policy.get("decision") == "ACCEPT" and display_name == "Alice":
            n_ident += 1

    assert src == "live"
    assert n_tracks >= 1
    assert n_members >= 2
    assert n_ident >= 1
    assert n_live_person == 0
    assert n_live_cluster == 0
    clu = cluster_run(store, rec["run_id"], eps=0.15, min_samples=2)
    assert clu["clusters"] == 0


def test_live_unknown_when_gallery_empty_or_mismatch(tmp_path):
    store = tmp_path / "s.sqlite"
    det = _DetModel([(10.0, 10.0, 130.0, 130.0, 0.9)] * 8)

    def embed_unknown(app, _frame):
        x1, y1, x2, y2, score = app.det_model.last_box
        return [
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": score,
                "face_w": int(x2 - x1),
                "face_h": int(y2 - y1),
                "dim": 2,
                "embedding": np.array([1.0, 0.0], dtype=np.float32),
            }
        ]

    with _live_model_env(det, embed_side_effect=embed_unknown):
        rec = live_capture(
            store,
            source=0,
            seconds=0.05,
            sample_hz=200.0,
            reembed_s=0.0,
            capture_factory=lambda _src: _FakeCapture(max_reads=16),
        )

    assert rec["identified_accept"] == 0
    assert rec["identified_unknown"] >= 1
    conn = sqlite3.connect(str(store))
    rows = conn.execute(
        "SELECT policy_json FROM decisions WHERE run_id=? AND kind='identify'",
        (rec["run_id"],),
    ).fetchall()
    conn.close()
    unknown = 0
    accept = 0
    for (pol,) in rows:
        decision = json.loads(pol or "{}").get("decision")
        if decision == "UNKNOWN":
            unknown += 1
        if decision == "ACCEPT":
            accept += 1
    assert unknown >= 1
    assert accept == 0


def test_live_embed_failure_is_not_success(tmp_path):
    store = tmp_path / "s.sqlite"
    events = []
    det = _DetModel([(10.0, 10.0, 130.0, 130.0, 0.95)] * 12)
    calls = {"n": 0}

    def embed_fail_then_ok(app, _frame):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        x1, y1, x2, y2, score = app.det_model.last_box
        return [
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": score,
                "face_w": int(x2 - x1),
                "face_h": int(y2 - y1),
                "dim": 2,
                "embedding": np.array([1.0, 0.0], dtype=np.float32),
            }
        ]

    with _live_model_env(det, embed_side_effect=embed_fail_then_ok):
        rec = live_capture(
            store,
            source=0,
            seconds=0.06,
            sample_hz=250.0,
            reembed_s=0.0,
            on_event=events.append,
            capture_factory=lambda _src: _FakeCapture(max_reads=18),
        )

    assert rec["frames"] >= 1
    assert rec["failed_embeds"] >= 1
    assert rec["timings"]["failed_embeds"] >= 1
    assert any(ev.kind == KIND_FAILED for ev in events)


def test_live_cannot_open_is_error(tmp_path):
    store = tmp_path / "s.sqlite"

    def broken_factory(_src):
        raise LiveError("cannot open live source: 0")

    with pytest.raises(LiveError):
        live_capture(store, source=0, seconds=0.01, sample_hz=100.0, capture_factory=broken_factory)

    if store.exists():
        conn = sqlite3.connect(str(store))
        completed = conn.execute("SELECT COUNT(*) FROM runs WHERE finished_at IS NOT NULL").fetchone()[0]
        conn.close()
        assert completed == 0


def test_live_seconds_zero_stops_on_cancel(tmp_path):
    store = tmp_path / "s.sqlite"
    events = []
    cap = _FakeCapture(max_reads=128)
    det = _DetModel([(10.0, 10.0, 130.0, 130.0, 0.95)] * 64)

    def embed_ok(app, _frame):
        x1, y1, x2, y2, score = app.det_model.last_box
        return [
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": score,
                "face_w": int(x2 - x1),
                "face_h": int(y2 - y1),
                "dim": 2,
                "embedding": np.array([1.0, 0.0], dtype=np.float32),
            }
        ]

    with _live_model_env(det, embed_side_effect=embed_ok):
        with pytest.raises(CancelledError):
            live_capture(
                store,
                source=0,
                seconds=0.0,
                sample_hz=300.0,
                reembed_s=0.0,
                cancel=lambda: cap.reads >= 2,
                on_event=events.append,
                capture_factory=lambda _src: cap,
            )
    assert events
    assert not any(ev.kind == KIND_COMPLETED for ev in events)


def test_live_retention_deletes_old_samples(tmp_path):
    store = tmp_path / "s.sqlite"
    det = _DetModel([(12.0, 10.0, 132.0, 130.0, 0.95)] * 48)

    def embed_ok(app, _frame):
        x1, y1, x2, y2, score = app.det_model.last_box
        return [
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": score,
                "face_w": int(x2 - x1),
                "face_h": int(y2 - y1),
                "dim": 2,
                "embedding": np.array([1.0, 0.0], dtype=np.float32),
            }
        ]

    with _live_model_env(det, embed_side_effect=embed_ok):
        rec = live_capture(
            store,
            source=0,
            seconds=0.10,
            sample_hz=250.0,
            reembed_s=0.0,
            retain_s=0.02,
            capture_factory=lambda _src: _FakeCapture(max_reads=64),
        )

    conn = sqlite3.connect(str(store))
    row = conn.execute(
        "SELECT MIN(t_ms), MAX(t_ms), COUNT(*) FROM observations WHERE run_id=? AND media_id=?",
        (rec["run_id"], rec["media_id"]),
    ).fetchone()
    conn.close()
    t_min, t_max, n_obs = row
    assert n_obs >= 1
    assert t_min is not None and t_max is not None
    assert (t_max - t_min) <= 30
    assert n_obs < rec["frames"]
