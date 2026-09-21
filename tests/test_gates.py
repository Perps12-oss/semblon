"""Gate registry defaults ON after VERIFY; env=0 disables."""

from __future__ import annotations

import pytest

from semblon import gates


def test_all_gates_default_on(monkeypatch):
    for key, gate in gates.GATES.items():
        monkeypatch.delenv(gate.env_var, raising=False)
        assert gate.default is True
        assert gates.is_enabled(key) is True


def test_env_zero_disables_single_gate(monkeypatch):
    for gate in gates.GATES.values():
        monkeypatch.delenv(gate.env_var, raising=False)
    monkeypatch.setenv("SEMBLON_GATE_RULED_OUT", "0")
    assert gates.is_enabled("ruled_out") is False
    assert gates.is_enabled("r3_bakeoff") is True


def test_require_enabled_raises_while_off(monkeypatch):
    monkeypatch.setenv("SEMBLON_GATE_LIVE_OVERLAY", "0")
    with pytest.raises(RuntimeError, match="is OFF"):
        gates.require_enabled("live_overlay")


def test_status_report_read_only_shape(monkeypatch):
    for gate in gates.GATES.values():
        monkeypatch.delenv(gate.env_var, raising=False)
    report = gates.status_report()
    assert "defaults ON" in report["policy"]
    assert report["verified_wired"] is True
    assert report["any_enabled"] is True
    keys = {g["key"] for g in report["gates"]}
    assert keys == set(gates.GATES)
