"""Track-state UX semantics."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from semblon.observers import persist_derived_tracks
from semblon.track_state import derive_track_states
from tests.test_tracks import _seed


def _seed_track_state_store(path: Path) -> None:
    _seed(path)
    persist_derived_tracks(path, "rt")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status, created_run) VALUES ('p1','Alice','active','rt')"
    )
    # find one track member face from a 2-face track for ACCEPT
    row_accept = conn.execute(
        """
        SELECT oi.face_id, t.track_id
        FROM tracks t
        JOIN track_members tm ON tm.track_id = t.track_id
        JOIN observation_items oi ON oi.item_id = tm.item_id
        WHERE t.run_id='rt'
        ORDER BY t.track_id, oi.face_id
        LIMIT 1
        """
    ).fetchone()
    # find a face from a different track for UNKNOWN decision.
    row_unknown = conn.execute(
        """
        SELECT oi.face_id, t.track_id
        FROM tracks t
        JOIN track_members tm ON tm.track_id = t.track_id
        JOIN observation_items oi ON oi.item_id = tm.item_id
        WHERE t.run_id='rt' AND t.track_id != ?
        ORDER BY t.track_id, oi.face_id
        LIMIT 1
        """,
        (row_accept["track_id"],),
    ).fetchone()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO decisions(
          decision_id, kind, face_id, person_id, cluster_id, pack_id,
          score_top1, score_top2, margin, policy_json, run_id, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            uuid.uuid4().hex,
            "identify",
            row_accept["face_id"],
            "p1",
            None,
            "pack-a",
            0.91,
            0.22,
            0.69,
            "{}",
            "rt",
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO decisions(
          decision_id, kind, face_id, person_id, cluster_id, pack_id,
          score_top1, score_top2, margin, policy_json, run_id, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            uuid.uuid4().hex,
            "identify",
            row_unknown["face_id"],
            None,
            None,
            "pack-a",
            0.49,
            0.45,
            0.04,
            "{}",
            "rt",
            now,
        ),
    )
    conn.commit()
    conn.close()


def test_track_state_classification(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_track_state_store(store)
    rec = derive_track_states(store, "rt")
    assert rec["counts"]["total"] >= 2
    assert rec["counts"]["identified"] >= 1
    assert rec["counts"]["unknown"] >= 1
    assert rec["counts"]["hypothesis"] >= 0
    labels = [t["label"] for t in rec["tracks"]]
    assert any("✓ identified" in s for s in labels)
    assert any("? unresolved" in s for s in labels)
