"""R3 bake-off harness — no fake PASS; aggregate only from verified input."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.r3_bakeoff.criteria import (  # noqa: E402
    CRITERIA,
    REJECTED_TOOLKITS,
    criterion_ids,
)
from tools.r3_bakeoff.harness import main, run_bakeoff  # noqa: E402


def _verified_pass(criterion_id: str, label: str = "") -> dict:
    return {
        "id": criterion_id,
        "label": label,
        "status": "pass",
        "verified": True,
        "pass": True,
        "detail": "injected test measurement",
    }


def test_six_criteria_match_brief_section_6():
    ids = criterion_ids()
    assert ids == [
        "accent_suppress",
        "mica_opaque",
        "frame_time_4k60",
        "wcag_aa",
        "virtualized_grid_10k",
        "a11y_tree",
    ]
    assert len(CRITERIA) == 6
    labels = {c.id: c.label for c in CRITERIA}
    assert "accent" in labels["accent_suppress"].lower()
    assert "Mica" in labels["mica_opaque"]
    assert "16 ms" in labels["frame_time_4k60"]
    assert "WCAG AA" in labels["wcag_aa"]
    assert "10k" in labels["virtualized_grid_10k"]
    assert "accessibility" in labels["a11y_tree"].lower()


def test_rejected_toolkits_listed():
    assert REJECTED_TOOLKITS == (
        "Electron",
        "Tauri",
        "permanent Tk AppShell",
        "CustomTkinter",
    )


def test_stub_measure_fns_return_unverified():
    for c in CRITERIA:
        result = c.measure_fn()
        assert result["verified"] is False
        assert result["pass"] is False
        assert result["status"] in {"unverified", "not_executed"}


def test_default_report_has_no_fake_pass(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_R3_BAKEOFF", raising=False)
    report = run_bakeoff()
    assert report["gate_enabled"] is True
    assert report["overall"] != "PASS"
    assert report["overall"] in {"incomplete", "FAIL"}
    assert all(not r["pass"] for r in report["criteria"])
    assert all(not r["verified"] for r in report["criteria"])
    assert "PASS" not in json.dumps({k: v for k, v in report.items() if k == "overall"})


def test_from_measure_still_unverified_without_host(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_R3_BAKEOFF", raising=False)
    monkeypatch.delenv("SEMBLON_GATE_R3_MEASURE", raising=False)
    report = run_bakeoff(from_measure=True)
    assert report["results_from"] == "r3_measure"
    assert report["overall"] != "PASS"
    assert all(not r["verified"] for r in report["criteria"])


def test_all_six_verified_passes_yields_pass(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_R3_BAKEOFF", raising=False)
    injected = [_verified_pass(i) for i in criterion_ids()]
    report = run_bakeoff(injected)
    assert report["overall"] == "PASS"
    assert report["missing_criteria"] == []
    assert all(r["verified"] and r["pass"] for r in report["criteria"])


def test_missing_one_stays_incomplete_or_fail(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_R3_BAKEOFF", raising=False)
    ids = criterion_ids()
    injected = [_verified_pass(i) for i in ids[:-1]]
    report = run_bakeoff(injected)
    assert report["overall"] != "PASS"
    assert report["overall"] in {"incomplete", "FAIL"}
    assert ids[-1] in report["missing_criteria"]


def test_one_verified_fail_among_complete_set_is_fail(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_R3_BAKEOFF", raising=False)
    injected = [_verified_pass(i) for i in criterion_ids()]
    injected[-1] = {
        "id": injected[-1]["id"],
        "status": "fail",
        "verified": True,
        "pass": False,
        "detail": "measured fail",
    }
    report = run_bakeoff(injected)
    assert report["overall"] == "FAIL"


def test_main_records_gate_enabled_false_when_off(monkeypatch, capsys):
    monkeypatch.setenv("SEMBLON_GATE_R3_BAKEOFF", "0")
    rc = main(["--json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["gate_enabled"] is False
    assert data["overall"] != "PASS"


def test_main_records_gate_enabled_true_when_on(monkeypatch, capsys):
    monkeypatch.delenv("SEMBLON_GATE_R3_BAKEOFF", raising=False)
    rc = main(["--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["gate_enabled"] is True
    # Enabling the gate does not invent measurement PASS.
    assert data["overall"] != "PASS"


def test_unverified_status_cannot_pass_even_if_flags_lie(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_R3_BAKEOFF", raising=False)
    lying = [
        {
            "id": i,
            "status": "unverified",
            "verified": True,
            "pass": True,
            "detail": "should be stripped",
        }
        for i in criterion_ids()
    ]
    report = run_bakeoff(lying)
    assert report["overall"] != "PASS"
    assert all(r["verified"] is False and r["pass"] is False for r in report["criteria"])
