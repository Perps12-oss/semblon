"""Gate registry defaults OFF; env enables one gate at a time."""

from __future__ import annotations

import os

import pytest

from semblon import gates


def test_all_gates_default_off(monkeypatch):
    for key, gate in gates.GATES.items():
        monkeypatch.delenv(gate.env_var, raising=False)
        assert gate.default is False
        assert gates.is_enabled(key) is False


def test_env_enables_single_gate(monkeypatch):
    for gate in gates.GATES.values():
        monkeypatch.delenv(gate.env_var, raising=False)
    monkeypatch.setenv("SEMBLON_GATE_R3_BAKEOFF", "1")
    assert gates.is_enabled("r3_bakeoff") is True
    assert gates.is_enabled("ruled_out") is False


def test_require_enabled_raises_while_off(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_LIVE_OVERLAY", raising=False)
    with pytest.raises(RuntimeError, match="is OFF"):
        gates.require_enabled("live_overlay")


def test_status_report_read_only_shape():
    report = gates.status_report()
    assert report["policy"].startswith("all defaults OFF")
    assert report["any_enabled"] is False
    keys = {g["key"] for g in report["gates"]}
    assert keys == set(gates.GATES)
