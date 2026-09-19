"""Production hardening: integrity, search, watchdog, provider. No InsightFace."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from semblon.cli import main
from semblon.progress import KIND_STALLED, STAGE_INGEST, make_event
from semblon.providers import FaceKitProvider, weights_status
from semblon.review import name_cluster
from semblon.search import search_face, search_people, search_person
from semblon.store import integrity_report, stamp_unfinished_runs
from semblon.watchdog import Watchdog
from tests.test_cluster import _seed
from tests.test_review import _clustered


def test_watchdog_stall_vs_progress():
    wd = Watchdog(stall_s=0.05)
    assert wd.classify() in {"queued", "running", "slow"}
    wd.note(make_event(STAGE_INGEST, "progress", current=1, total=2))
    stalled = wd.check(now=wd.last_monotonic + 1.0)
    assert stalled is not None
    assert stalled.kind == KIND_STALLED
    assert wd.classify(now=wd.last_monotonic + 1.0) == "stalled"


def test_facekit_provider_is_cpu_only():
    info = FaceKitProvider.info
    assert info.modality == "face"
    assert info.device == "cpu"
    assert info.execution_provider == "CPUExecutionProvider"
    w = weights_status()
    assert w["bundled"] is False
    assert w["redistributable"] is False


def test_integrity_and_interrupted_stamp(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    rec = integrity_report(store)
    assert rec["ok"] is True
    assert rec["pragma_integrity"] == "ok"
    assert rec["media_missing_path"] == 2
    assert "r1" in rec["unfinished_runs"]
    stamped = stamp_unfinished_runs(conn, except_run_id="live")
    conn.close()
    assert "r1" in stamped
    rec3 = integrity_report(store)
    assert rec3["unfinished_runs"] == []
    assert rec3["ok"] is True


def test_integrity_missing_original_does_not_fail_ok(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    real = tmp_path / "a.jpg"
    real.write_bytes(b"x")
    conn.execute("UPDATE media SET path=? WHERE media_id='m1'", (str(real),))
    conn.commit()
    conn.close()
    rec = integrity_report(store)
    assert rec["ok"] is True
    assert rec["media_missing_path"] == 1
    assert rec["pragma_integrity"] == "ok"


def test_search_person_lookup_is_readonly(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    from semblon.search import _open

    ro = _open(store)
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO schema_meta(key, value) VALUES ('probe', '1')")
    ro.close()
    rec = search_person(store, "Alice")
    assert rec["count"] == 1


def test_search_person_not_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    rec = search_person(store, "Alice")
    assert rec["count"] == 1
    assert rec["items"][0]["display_name"] == "Alice"
    assert rec["items"][0]["person_id"] != assigned["f1"]
    people = search_people(store)
    assert people["count"] == 1
    ident = search_face(store, "r1", "f2")
    assert ident["identify"]["decision"] in {"ACCEPT", "UNKNOWN"}
    assert ident["why"].startswith("identify vs named")


def test_cli_integrity_models_search(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    assert main(["lab", "integrity", "--store", str(store)]) == 0
    assert main(["lab", "models"]) == 0
    assert main(["search", "--people", "--store", str(store)]) == 0
    assert main(["search", "--person", "Alice", "--store", str(store)]) == 0
    assert main(["search", "--store", str(store)]) == 2


def test_bench_harness_not_executed_is_honest(tmp_path):
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "tools" / "bench_ingest.py"
    spec = importlib.util.spec_from_file_location("bench_ingest", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    out = tmp_path / "bench.json"
    assert mod.main(["--out", str(out)]) == 0
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["verified"] is False
    assert "not executed" in rec["status"]
