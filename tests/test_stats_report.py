"""Read-only stats and report. No InsightFace. Report must not write the store."""

from __future__ import annotations

from pathlib import Path

from semblon.cli import main
from semblon.report import write_report
from semblon.review import name_cluster
from semblon.stats import stats
from tests.test_review import _clustered


def test_stats_and_report_are_readonly(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    before = store.stat().st_mtime_ns
    rec = stats(store, "r1")
    assert rec["run_id"] == "r1"
    assert rec["detection"]["ok"] >= 1
    assert rec["persons_active"] == 1
    assert rec["faces_named"] >= 1
    assert rec["accuracy"]["far"] is None
    out = tmp_path / "report.md"
    wrote = write_report(store, "r1", out)
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "Alice" not in text or "persons" in text
    assert "Semblon report" in text
    assert rec["accuracy"]["status"] in ("not_measurable", "underpowered", "measurable")
    assert "not_measurable" in text or "underpowered" in text or "measurable" in text
    after = store.stat().st_mtime_ns
    assert after == before
    assert wrote["note"] == "report did not write the store"
    assert main(["stats", "--run", "r1", "--store", str(store)]) == 0
    assert main(["report", "--run", "r1", "--store", str(store), "--out", str(out)]) == 0
    assert main(["stats", "--run", "missing", "--store", str(store)]) == 2
