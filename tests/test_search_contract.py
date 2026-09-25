"""Similar search must not report an empty match when nothing was embedded."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.empty_states import search_result_lines
from semblon.observers import observe_bgr
from semblon.search import SearchError, search_similar
from semblon.store import connect, init_db


def _seed(path: Path):
    conn = connect(path)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    return conn


def test_one_embedding_is_a_scan_with_no_neighbour(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("color",))
    conn.commit()
    item = conn.execute("SELECT item_id FROM observation_items WHERE kind='appearance'").fetchone()[0]
    conn.close()
    rec = search_similar(store, item)
    assert rec["status"] == "NO_RESULT"
    assert rec["provider_state"] == "DEGRADED"
    assert rec["fallback"] == "LIBRARY_SCAN"
    assert rec["count"] == 0
    assert "nothing matched" in rec["reason"]
    lines = search_result_lines(rec)
    assert "No matches nearby." not in lines
    assert any("nothing matched" in line for line in lines)


def test_two_embeddings_are_a_degraded_hit(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("color",))
    observe_bgr(conn, observation_id="o2", run_id="r1", img=img, observers=("color",))
    conn.commit()
    item = conn.execute(
        "SELECT item_id FROM observation_items WHERE kind='appearance' ORDER BY item_id"
    ).fetchone()[0]
    conn.close()
    rec = search_similar(store, item)
    assert rec["status"] == "SUCCESS"
    assert rec["count"] == 1
    assert rec["fallback"] == "LIBRARY_SCAN"
    assert rec["provider_state"] == "DEGRADED"
    assert "library" in rec["reason"]


def test_failed_clip_is_not_an_empty_neighbourhood(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    with patch("semblon.observers.clip_embed", return_value=None):
        observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("clip",))
    conn.commit()
    item = conn.execute("SELECT item_id FROM observation_items WHERE kind='clip'").fetchone()[0]
    conn.close()
    rec = search_similar(store, item)
    assert rec["status"] == "UNAVAILABLE"
    assert rec["provider_state"] == "FAILED"
    assert rec["count"] == 0
    assert rec["fallback"] is None
    assert rec["status"] != "NO_RESULT"
    lines = search_result_lines(rec)
    assert lines == [rec["reason"]]
    assert "No matches nearby." not in lines


def test_demanding_the_missing_index_does_not_scan(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("color",))
    observe_bgr(conn, observation_id="o2", run_id="r1", img=img, observers=("color",))
    conn.commit()
    item = conn.execute("SELECT item_id FROM observation_items WHERE kind='appearance'").fetchone()[0]
    conn.close()
    rec = search_similar(store, item, require_index=True)
    assert rec["status"] == "UNAVAILABLE"
    assert rec["error_id"] == "ann_index.INDEX_REQUIRED"
    assert rec["items"] == []
    assert rec["provider_state"] == "FAILED"


def test_unknown_item_is_still_an_error(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    conn.commit()
    conn.close()
    with pytest.raises(SearchError):
        search_similar(store, "missing")
