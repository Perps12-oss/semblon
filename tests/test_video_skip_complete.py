"""Item 02 — video is 'seen' only with a sampling-complete marker."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.ingest import (
    VIDEO_COMPLETE_PROVIDER,
    _mark_video_sampling_complete,
    media_skip_reason,
    video_sampling_complete,
)
from semblon.store import init_db


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "s.sqlite"))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r0", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute(
        "INSERT INTO media VALUES ('mv','video','/clip.mp4','videodigest',640,480,0,1)"
    )
    return conn


def test_partial_video_is_not_seen(tmp_path):
    conn = _conn(tmp_path)
    conn.execute("INSERT INTO observations VALUES ('o1','mv',0,0,'r0')")
    conn.commit()
    reason, media_id = media_skip_reason(conn, "videodigest", "r1", reprocess=False)
    assert media_id == "mv"
    assert reason is None
    assert video_sampling_complete(conn, "mv") is False
    conn.close()


def test_complete_video_is_seen(tmp_path):
    conn = _conn(tmp_path)
    conn.execute("INSERT INTO observations VALUES ('o1','mv',0,0,'r0')")
    _mark_video_sampling_complete(conn, media_id="mv", run_id="r0", frames=12)
    conn.commit()
    assert video_sampling_complete(conn, "mv") is True
    reason, media_id = media_skip_reason(conn, "videodigest", "r1", reprocess=False)
    assert media_id == "mv"
    assert reason == "seen"
    row = conn.execute(
        "SELECT provider, payload_json FROM observation_items WHERE provider=?",
        (VIDEO_COMPLETE_PROVIDER,),
    ).fetchone()
    payload = json.loads(row["payload_json"])
    assert payload["sampling_complete"] is True
    assert payload["frames"] == 12
    conn.close()


def test_reprocess_ignores_complete_marker(tmp_path):
    conn = _conn(tmp_path)
    conn.execute("INSERT INTO observations VALUES ('o1','mv',0,0,'r0')")
    _mark_video_sampling_complete(conn, media_id="mv", run_id="r0", frames=3)
    conn.commit()
    reason, _media_id = media_skip_reason(conn, "videodigest", "r1", reprocess=True)
    assert reason is None
    conn.close()
