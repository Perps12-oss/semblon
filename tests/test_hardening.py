"""Hardening snapshot smoke."""

from __future__ import annotations

from semblon.cli import main
from semblon.hardening import hardening_snapshot


def test_hardening_snapshot_has_sections():
    rec = hardening_snapshot()
    assert "hardware_matrix" in rec
    assert "product_lifecycle" in rec
    assert "scripts" in rec["product_lifecycle"]


def test_cli_lab_hardening():
    assert main(["lab", "hardening"]) == 0
