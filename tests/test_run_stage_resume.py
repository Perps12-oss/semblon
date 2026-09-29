"""Items 04–05 — durable run stage tokens and honest ingest_done."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.ingest import _mark_video_sampling_complete
from semblon.process import (
    find_resumable_run,
    inspect_run_stages,
    persist_run_stage,
)
from semblon.store import init_db


def _seed_run(store: Path, folder: Path, *, notes=None, finished=True, timings=None) -> None:
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    cfg = json.dumps({"folder": str(folder)})
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution,
           timings_json, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "r-resume",
            "t0",
            "t1" if finished else None,
            "0.0.1",
            "pack-a",
            2,
            "l2",
            cfg,
            "{}",
            "x64",
            "native",
            json.dumps(timings or {}),
            notes,
        ),
    )
    conn.commit()
    conn.close()


def test_persist_run_stage_writes_closed_tokens(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    _seed_run(store, folder)
    persist_run_stage(store, "r-resume", stage="cluster", job="running")
    persist_run_stage(store, "r-resume", stage="not-a-stage", job="running")
    conn = sqlite3.connect(str(store))
    raw = conn.execute("SELECT timings_json FROM runs WHERE run_id='r-resume'").fetchone()[0]
    conn.close()
    timings = json.loads(raw)
    assert timings["stage"] == "cluster"
    assert timings["job"] == "running"


def test_inspect_run_stages_reads_tokens(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    _seed_run(store, folder, timings={"stage": "ingest", "job": "running"})
    stages = inspect_run_stages(store, "r-resume", folder=folder)
    assert stages["stage"] == "ingest"
    assert stages["job"] == "running"


def test_hollow_media_makes_ingest_not_done(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    photo = folder / "a.jpg"
    photo.write_bytes(b"x")
    _seed_run(store, folder, finished=True)
    conn = sqlite3.connect(str(store))
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "aaa", 10, 10, 0, 1),
    )
    conn.commit()
    conn.close()
    stages = inspect_run_stages(store, "r-resume", folder=folder)
    assert stages["ingest_done"] is False
    assert find_resumable_run(store, folder) == "r-resume"


def test_complete_still_is_ingest_done(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    photo = folder / "a.jpg"
    photo.write_bytes(b"x")
    _seed_run(store, folder, finished=True)
    conn = sqlite3.connect(str(store))
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "aaa", 10, 10, 0, 1),
    )
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r-resume')")
    conn.commit()
    conn.close()
    stages = inspect_run_stages(store, "r-resume", folder=folder)
    assert stages["ingest_done"] is True


def test_partial_video_makes_ingest_not_done(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    clip = folder / "c.mp4"
    clip.write_bytes(b"x")
    _seed_run(store, folder, finished=True)
    conn = sqlite3.connect(str(store))
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("mv", "video", str(clip), "vid", 10, 10, 0, 1),
    )
    conn.execute("INSERT INTO observations VALUES ('o1','mv',0,0,'r-resume')")
    conn.commit()
    conn.close()
    stages = inspect_run_stages(store, "r-resume", folder=folder)
    assert stages["ingest_done"] is False


def test_complete_video_is_ingest_done(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    clip = folder / "c.mp4"
    clip.write_bytes(b"x")
    _seed_run(store, folder, finished=True)
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("mv", "video", str(clip), "vid", 10, 10, 0, 1),
    )
    conn.execute("INSERT INTO observations VALUES ('o1','mv',0,0,'r-resume')")
    _mark_video_sampling_complete(conn, media_id="mv", run_id="r-resume", frames=4)
    conn.commit()
    conn.close()
    stages = inspect_run_stages(store, "r-resume", folder=folder)
    assert stages["ingest_done"] is True
