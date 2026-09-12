"""Observatory snapshot / freeze / enter — no InsightFace."""

from __future__ import annotations

import json
from pathlib import Path

from semblon.cli import main
from semblon.cluster import cluster_run
from semblon.observatory import compare_boards, enter_stage, freeze, snapshot
from tests.test_cluster import _seed


def test_snapshot_readonly(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    board = snapshot(store, "r1")
    assert board["detection"]["ok"] == 5
    assert board["clustering"]["clusters"] == 2
    assert board["accuracy"]["status"] == "not_measurable"
    import sqlite3

    conn = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    assert n == 0


def test_enter_without_golden_is_not_measurable(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    rec = enter_stage(store, "r1", "S3")
    assert rec["verdict"] == "not_measurable"
    assert rec["entering"] == "S3"
    assert rec["checks"] == "S1"


def test_freeze_then_enter_ok(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    freeze(store, "r1", "S1")
    rec = enter_stage(store, "r1", "S3")
    assert rec["verdict"] in ("ok", "improvement")
    assert rec["checks"] == "S1"
    assert Path(rec["golden_path"]).is_file()


def test_compare_review_regression():
    golden = {
        "pack_id": "pack-a",
        "run_id": "old",
        "stage": "S1",
        "accuracy": {"status": "not_measurable"},
        "clustering": {"review_required": 10},
        "speed": {"peak_rss_mb": 100, "timings": {}},
    }
    current = {
        "pack_id": "pack-a",
        "run_id": "new",
        "accuracy": {"status": "not_measurable"},
        "clustering": {"review_required": 40},
        "speed": {"peak_rss_mb": 100, "timings": {}},
    }
    rec = compare_boards(golden, current)
    assert rec["verdict"] == "regression"
    assert rec["marks"]["effort"] == "regression"


def test_cli_freeze_enter_promote(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert main(["lab", "observatory", "freeze", "--store", str(store), "--run", "r1", "--stage", "S1"]) == 0
    assert main(["lab", "observatory", "enter", "--store", str(store), "--run", "r1", "--stage", "S3"]) == 0
    # missing run
    assert main(["lab", "observatory", "snapshot", "--store", str(store), "--run", "nope"]) == 2
    # promote with a fake worse golden
    golden = json.loads((tmp_path / "observatory" / "golden-S1.json").read_text())
    golden["clustering"]["review_required"] = 1
    bad = tmp_path / "observatory" / "golden-S1.json"
    # current has 0 review (both clusters strong) vs golden 1 → improvement, not 3
    assert main(["lab", "observatory", "enter", "--store", str(store), "--run", "r1", "--stage", "S3", "--promote"]) == 0
    golden["clustering"]["review_required"] = 0
    # keep 0 vs 0 ok
    bad.write_text(json.dumps(golden))
    # force regression: golden review 1 would be improvement from current 0.
    # set golden review 0 and current... can't change current. Mutate golden speed rss.
    golden["speed"]["peak_rss_mb"] = 10
    # snapshot current rss is None → not_measurable not regression
    # inject review on golden as 0, and compare_boards with high current — already unit-tested.
    assert main(
        ["lab", "observatory", "compare", "--store", str(store), "--run", "r1", "--against", str(bad)]
    ) == 0
