"""Item 06 — 15k DBSCAN ceiling is an explicit contract, not a silent drop."""

from __future__ import annotations

import json
import sqlite3

import pytest

from semblon import cluster as cluster_mod
from semblon.cluster import ClusterError, MAX_DBSCAN_FACES, cluster_run
from tests.test_cluster import _seed


def test_max_dbscan_faces_constant_is_15000():
    assert MAX_DBSCAN_FACES == 15000


def test_over_cap_raises_and_records_ok_faces_active(tmp_path, monkeypatch):
    monkeypatch.setattr(cluster_mod, "MAX_DBSCAN_FACES", 1)
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    with pytest.raises(ClusterError, match="too many active still faces"):
        cluster_run(store, "r1")
    conn = sqlite3.connect(str(store))
    raw = conn.execute("SELECT timings_json FROM runs WHERE run_id='r1'").fetchone()[0]
    conn.close()
    timings = json.loads(raw)
    assert timings["ok_faces_active"] > 1
    assert timings["max_dbscan_faces"] == 1
    assert "DBSCAN" in timings["cluster_error"]
