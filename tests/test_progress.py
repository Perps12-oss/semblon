"""UI-agnostic process progress events. No InsightFace. No GUI."""

from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.cluster import ClusterError
from semblon.ingest import CancelledError, discover_stills, ingest
from semblon.process import ProcessCancelled, ProcessError, find_resumable_run, process_folder
from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_PROGRESS,
    KIND_QUEUED,
    KIND_STARTED,
    STAGE_CLUSTER,
    STAGE_DISCOVER,
    STAGE_EXPORT,
    STAGE_INGEST,
    STAGE_PROCESS,
    ProgressEvent,
    emit,
    estimate_eta_s,
    format_duration,
    format_progress_bar,
    format_progress_line,
    make_event,
    ratio_percent,
    stills_percent,
)


def _pairs(events: list[ProgressEvent]) -> list[tuple[str, str]]:
    return [e.as_tuple() for e in events]


def test_ratio_percent_is_none_without_denominator():
    assert ratio_percent(None, None) is None
    assert ratio_percent(3, None) is None
    assert ratio_percent(3, 0) is None
    assert ratio_percent(1, 4) == 25.0


def test_emit_none_and_broken_consumer_do_not_raise():
    emit(None, make_event(STAGE_PROCESS, KIND_STARTED))

    def boom(_event):
        raise RuntimeError("ui died")

    emit(boom, make_event(STAGE_PROCESS, KIND_STARTED))


def test_process_without_on_event_matches_today(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"
    lines: list[str] = []

    with (
        patch(
            "semblon.process.ingest",
            return_value={
                "run_id": "RUN-ABC",
                "new_media": 2,
                "faces": 3,
                "ok": 3,
                "skipped_seen": 0,
                "files": 2,
            },
        ) as ing,
        patch(
            "semblon.process.cluster_run",
            return_value={"clusters": 1, "clustered": 3, "unassigned": 0, "cluster_s": 0.01},
        ),
    ):
        rec = process_folder(
            folder,
            store=store,
            out=out,
            open_review=False,
            progress=lines.append,
        )

    assert rec["run_id"] == "RUN-ABC"
    assert rec["out"] is None
    assert not out.is_file()
    assert ing.call_args.kwargs.get("on_event") is None
    assert any("Ingesting" in line for line in lines)
    assert any("Library ready" in line for line in lines)


def test_process_events_stage_order(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"aaaa")
    (folder / "b.jpg").write_bytes(b"bbbb")
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"
    events: list[ProgressEvent] = []

    def fake_ingest(folder_arg, store_arg, **kwargs):
        on_event = kwargs.get("on_event")
        from semblon.progress import emit as _emit, make_event as _ev

        files = discover_stills(folder_arg)
        _emit(on_event, _ev(STAGE_DISCOVER, KIND_STARTED, path=str(folder_arg)))
        _emit(
            on_event,
            _ev(STAGE_DISCOVER, KIND_COMPLETED, current=len(files), total=len(files), files_total=len(files)),
        )
        _emit(
            on_event,
            _ev(STAGE_INGEST, KIND_STARTED, current=0, total=len(files), files_total=len(files), faces_found=0),
        )
        faces = 0
        for i, path in enumerate(files, start=1):
            faces += 1 if path.name == "a.jpg" else 2
            _emit(
                on_event,
                _ev(
                    STAGE_INGEST,
                    KIND_PROGRESS,
                    current=i,
                    total=len(files),
                    files_processed=i,
                    files_total=len(files),
                    faces_found=faces,
                    path=str(path),
                    outcome="processed",
                ),
            )
        _emit(
            on_event,
            _ev(
                STAGE_INGEST,
                KIND_COMPLETED,
                current=len(files),
                total=len(files),
                files_processed=len(files),
                files_total=len(files),
                faces_found=faces,
            ),
        )
        return {
            "run_id": "RUN-SMOKE",
            "new_media": 2,
            "faces": faces,
            "ok": faces,
            "skipped_seen": 0,
            "files": len(files),
        }

    with (
        patch("semblon.process.ingest", side_effect=fake_ingest),
        patch(
            "semblon.process.cluster_run",
            return_value={"clusters": 1, "clustered": 3, "unassigned": 0, "cluster_s": 0.02},
        ),
    ):
        rec = process_folder(
            folder,
            store=store,
            out=out,
            open_review=False,
            progress=lambda *_: None,
            on_event=events.append,
        )

    assert rec["run_id"] == "RUN-SMOKE"
    pairs = _pairs(events)
    assert pairs[0] == (STAGE_PROCESS, KIND_QUEUED)
    assert pairs[1] == (STAGE_PROCESS, KIND_STARTED)
    assert (STAGE_DISCOVER, KIND_STARTED) in pairs
    assert (STAGE_DISCOVER, KIND_COMPLETED) in pairs
    assert (STAGE_INGEST, KIND_STARTED) in pairs
    assert (STAGE_INGEST, KIND_PROGRESS) in pairs
    assert (STAGE_INGEST, KIND_COMPLETED) in pairs
    assert (STAGE_CLUSTER, KIND_STARTED) in pairs
    assert (STAGE_CLUSTER, KIND_COMPLETED) in pairs
    assert (STAGE_EXPORT, KIND_STARTED) in pairs
    assert (STAGE_EXPORT, KIND_COMPLETED) in pairs
    assert pairs[-1] == (STAGE_PROCESS, KIND_COMPLETED)
    compact = []
    for p in pairs:
        if p == (STAGE_INGEST, KIND_PROGRESS) and compact and compact[-1] == p:
            continue
        compact.append(p)
    assert compact == [
        (STAGE_PROCESS, KIND_QUEUED),
        (STAGE_PROCESS, KIND_STARTED),
        (STAGE_DISCOVER, KIND_STARTED),
        (STAGE_DISCOVER, KIND_COMPLETED),
        (STAGE_INGEST, KIND_STARTED),
        (STAGE_INGEST, KIND_PROGRESS),
        (STAGE_INGEST, KIND_COMPLETED),
        (STAGE_CLUSTER, KIND_STARTED),
        (STAGE_CLUSTER, KIND_COMPLETED),
        (STAGE_EXPORT, KIND_STARTED),
        (STAGE_EXPORT, KIND_COMPLETED),
        (STAGE_PROCESS, KIND_COMPLETED),
    ]


def test_discover_and_ingest_counters_are_truthful(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"aaaa")
    (folder / "b.jpg").write_bytes(b"bbbb")
    (folder / "notes.txt").write_text("ignore")
    found = discover_stills(folder)
    assert [p.name for p in found] == ["a.jpg", "b.jpg"]

    events: list[ProgressEvent] = []
    vec = np.zeros(4, dtype=np.float32)

    def faces_for(path):
        n = 1 if path.name == "a.jpg" else 2
        return [
            {
                "bbox": (0.0, 0.0, 100.0, 100.0),
                "det_score": 0.9,
                "face_w": 100,
                "face_h": 100,
                "dim": 4,
                "embedding": vec,
            }
            for _ in range(n)
        ]

    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()

    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch(
            "semblon.ingest.embed_bgr",
            side_effect=lambda app, img, _n=iter((Path("a.jpg"), Path("b.jpg"))): faces_for(next(_n)),
        ),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        rec = ingest(folder, tmp_path / "store.sqlite", on_event=events.append)

    assert rec["files"] == 2
    assert rec["faces"] == 3
    assert rec["new_media"] == 2
    discover_done = [e for e in events if e.stage == STAGE_DISCOVER and e.kind == KIND_COMPLETED]
    assert len(discover_done) == 1
    assert discover_done[0].files_total == 2
    assert discover_done[0].total == 2
    ingest_prog = [e for e in events if e.stage == STAGE_INGEST and e.kind == KIND_PROGRESS]
    library = [e for e in ingest_prog if e.outcome == "library"]
    faces = [e for e in ingest_prog if e.outcome == "faces"]
    assert [e.current for e in library] == [1, 2]
    assert library[-1].total == 2
    assert faces[-1].current == 2
    assert faces[-1].total == 2
    assert faces[-1].faces_found == 3
    assert library[0].path.endswith("a.jpg")
    ingest_done = [e for e in events if e.stage == STAGE_INGEST and e.kind == KIND_COMPLETED][0]
    assert ingest_done.files_processed == 2
    assert ingest_done.files_total == 2
    assert ingest_done.faces_found == 3


def test_process_emits_queued_first(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    events: list[ProgressEvent] = []

    with (
        patch(
            "semblon.process.ingest",
            return_value={"run_id": "RUN-Q", "new_media": 0, "faces": 0, "ok": 0, "skipped_seen": 0, "files": 0},
        ),
        patch("semblon.process.cluster_run", side_effect=ClusterError("no ok faces")),
    ):
        with pytest.raises(ProcessError):
            process_folder(
                folder,
                store=tmp_path / "s.sqlite",
                out=tmp_path / "r.html",
                open_review=False,
                progress=lambda *_: None,
                on_event=events.append,
            )
    assert events
    assert events[0].kind == KIND_QUEUED
    assert events[0].stage == STAGE_PROCESS


def test_process_failed_is_emitted(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    events: list[ProgressEvent] = []

    with (
        patch(
            "semblon.process.ingest",
            return_value={"run_id": "RUN-FAIL", "faces": 0, "files": 0, "ok": 0, "skipped_seen": 0},
        ),
        patch("semblon.process.cluster_run", side_effect=ClusterError("no ok faces")),
    ):
        with pytest.raises(ProcessError, match="no ok faces"):
            process_folder(
                folder,
                store=tmp_path / "s.sqlite",
                out=tmp_path / "r.html",
                open_review=False,
                progress=lambda *_: None,
                on_event=events.append,
            )

    pairs = _pairs(events)
    assert pairs[0] == (STAGE_PROCESS, KIND_QUEUED)
    assert pairs[1] == (STAGE_PROCESS, KIND_STARTED)
    assert (STAGE_CLUSTER, KIND_STARTED) in pairs
    assert pairs[-1] == (STAGE_PROCESS, KIND_FAILED)
    assert events[-1].error == "no ok faces"
    assert (STAGE_PROCESS, KIND_COMPLETED) not in pairs


def test_missing_folder_emits_failed_without_started(tmp_path):
    events: list[ProgressEvent] = []
    with pytest.raises(ProcessError, match="folder not found"):
        process_folder(
            tmp_path / "nope",
            open_review=False,
            progress=lambda *_: None,
            on_event=events.append,
        )
    assert _pairs(events) == [(STAGE_PROCESS, KIND_FAILED)]
    assert events[0].error is not None


def _fake_embed_env(faces_for):
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    stack = ExitStack()
    stack.enter_context(patch("semblon.ingest.load_app", return_value=object()))
    stack.enter_context(patch("semblon.ingest.discover_weight_hashes", return_value={}))
    stack.enter_context(
        patch("semblon.ingest.embed_bgr", side_effect=lambda app, img: faces_for(Path("a.jpg")))
    )
    stack.enter_context(
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8))
    )
    stack.enter_context(patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}))
    return stack


def test_ingest_cancel_emits_cancelled_not_completed(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"aaaa")
    (folder / "b.jpg").write_bytes(b"bbbb")
    events: list[ProgressEvent] = []
    processed = {"n": 0}

    def faces_for(path):
        processed["n"] += 1
        vec = np.zeros(4, dtype=np.float32)
        return [
            {
                "bbox": (0.0, 0.0, 100.0, 100.0),
                "det_score": 0.9,
                "face_w": 100,
                "face_h": 100,
                "dim": 4,
                "embedding": vec,
            }
        ]

    def cancel():
        return processed["n"] >= 1

    with _fake_embed_env(faces_for):
        with pytest.raises(CancelledError, match="cancelled"):
            ingest(folder, tmp_path / "store.sqlite", on_event=events.append, cancel=cancel)

    pairs = _pairs(events)
    assert (STAGE_INGEST, KIND_CANCELLED) in pairs
    assert (STAGE_INGEST, KIND_COMPLETED) not in pairs
    assert events[-1].kind == KIND_CANCELLED
    assert events[-1].outcome == "cancelled"
    conn = __import__("sqlite3").connect(str(tmp_path / "store.sqlite"))
    row = conn.execute("SELECT notes, timings_json FROM runs").fetchone()
    n_faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    conn.close()
    assert row[0] == "cancelled"
    assert '"cancelled": true' in row[1]
    assert n_media == 2
    assert n_faces == 1


def test_process_cancel_is_not_success(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    events: list[ProgressEvent] = []

    with patch(
        "semblon.process.ingest",
        side_effect=CancelledError("ingest cancelled", run_id="RUN-C"),
    ):
        with pytest.raises(ProcessCancelled, match="cancelled"):
            process_folder(
                folder,
                store=tmp_path / "s.sqlite",
                out=tmp_path / "r.html",
                open_review=False,
                progress=lambda *_: None,
                on_event=events.append,
            )

    pairs = _pairs(events)
    assert pairs[0] == (STAGE_PROCESS, KIND_QUEUED)
    assert pairs[1] == (STAGE_PROCESS, KIND_STARTED)
    assert pairs[-1] == (STAGE_PROCESS, KIND_CANCELLED)
    assert (STAGE_PROCESS, KIND_COMPLETED) not in pairs
    assert (STAGE_PROCESS, KIND_FAILED) not in pairs


def test_eta_and_bar_need_real_counts():
    assert estimate_eta_s(10.0, 2, 6) == 20.0
    assert estimate_eta_s(10.0, 0, 6) is None
    assert estimate_eta_s(10.0, 6, 6) is None
    assert format_duration(65) == "1:05"
    assert format_duration(None) is None
    assert format_progress_bar(0, width=10) == "[----------]"
    assert format_progress_bar(100, width=10) == "[##########]"
    ev = make_event(
        STAGE_INGEST,
        KIND_PROGRESS,
        files_processed=2,
        files_total=4,
        elapsed_s=10.0,
        clock="12:00:00",
    )
    assert stills_percent(ev) == 50.0
    line = format_progress_line(ev)
    assert "50%" in line
    assert "elapsed 0:10" in line
    assert "eta 0:10" in line
    assert "12:00:00" in line
    assert "#" in line
    bare = make_event(STAGE_INGEST, KIND_STARTED, message="reading stills", clock="12:00:01")
    assert stills_percent(bare) is None
    assert "%" not in format_progress_line(bare)


def test_process_resume_skips_finished_stages(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"
    from semblon.store import connect, init_db

    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "r-resume",
            "t0",
            "t1",
            "0.0.1",
            "pack-a",
            2,
            "l2",
            json.dumps({"folder": str(folder.resolve())}),
            "{}",
            "x64",
            "native",
            None,
        ),
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder',?,?,100,100,0,1)",
        (str(folder / "a.jpg"), "aaa"),
    )
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r-resume')")
    conn.execute(
        """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, centroid, min_intra, status)
           VALUES ('c1','r-resume','dbscan',1,NULL,1.0,'auto')"""
    )
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim,cluster_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("f1", "o1", "r-resume", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", b"xxxxxxxx", "pack-a", 2, "c1"),
    )
    conn.commit()
    conn.close()
    # Clustered runs are complete. review.html is not a remaining stage.
    assert find_resumable_run(store, folder) is None
    assert not out.exists()


def test_resume_ingests_when_cluster_is_unfinished(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"
    from semblon.store import connect, init_db

    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "r-resume",
            "t0",
            "t1",
            "0.0.1",
            "pack-a",
            2,
            "l2",
            json.dumps({"folder": str(folder.resolve())}),
            "{}",
            "x64",
            "native",
            None,
        ),
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder',?,?,100,100,0,1)",
        (str(folder / "a.jpg"), "aaa"),
    )
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r-resume')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim,cluster_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("f1", "o1", "r-resume", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", b"xxxxxxxx", "pack-a", 2, None),
    )
    conn.commit()
    conn.close()
    assert find_resumable_run(store, folder) == "r-resume"

    with (
        patch(
            "semblon.process.ingest",
            return_value={
                "run_id": "r-resume",
                "faces": 1,
                "ok": 1,
                "new_media": 0,
                "skipped_seen": 0,
                "files": 1,
            },
        ) as ing,
        patch(
            "semblon.process.cluster_run",
            return_value={"clusters": 1, "clustered": 1, "unassigned": 0, "cluster_s": 0.01},
        ) as clu,
    ):
        rec = process_folder(
            folder,
            store=store,
            out=out,
            resume=True,
            progress=lambda *_: None,
        )

    ing.assert_called_once()
    assert ing.call_args.kwargs["resume_run_id"] == "r-resume"
    clu.assert_called_once()
    assert rec["run_id"] == "r-resume"
    assert rec["out"] is None
    assert rec["ingest"]["run_id"] == "r-resume"
    assert not out.is_file()


def test_ingest_resume_reuses_run_id(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"aaaa")
    (folder / "b.jpg").write_bytes(b"bbbb")
    processed = {"n": 0}

    def faces_for(path):
        processed["n"] += 1
        vec = np.zeros(4, dtype=np.float32)
        return [
            {
                "bbox": (0.0, 0.0, 100.0, 100.0),
                "det_score": 0.9,
                "face_w": 100,
                "face_h": 100,
                "dim": 4,
                "embedding": vec,
            }
        ]

    def cancel_first():
        return processed["n"] >= 1

    with _fake_embed_env(faces_for):
        with pytest.raises(CancelledError) as ei:
            ingest(folder, tmp_path / "store.sqlite", cancel=cancel_first)
    run_id = ei.value.run_id
    assert run_id
    processed["n"] = 0
    with _fake_embed_env(faces_for):
        rec = ingest(folder, tmp_path / "store.sqlite", resume_run_id=run_id)
    assert rec["run_id"] == run_id
    conn = __import__("sqlite3").connect(str(tmp_path / "store.sqlite"))
    n_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    notes = conn.execute("SELECT notes FROM runs WHERE run_id=?", (run_id,)).fetchone()[0]
    conn.close()
    assert n_runs == 1
    assert n_media == 2
    assert notes is None
