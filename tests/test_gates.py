"""Central feature-gate defaults: all OFF unless env explicitly truthy."""

from __future__ import annotations

import pytest

from semblon import gates


@pytest.mark.parametrize("name", gates.KNOWN_FLAGS)
def test_enabled_defaults_false(monkeypatch, name: str):
    monkeypatch.delenv(name, raising=False)
    assert gates.enabled(name) is False


@pytest.mark.parametrize("name", gates.KNOWN_FLAGS)
@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "  "])
def test_enabled_falsy_values(monkeypatch, name: str, value: str):
    monkeypatch.setenv(name, value)
    assert gates.enabled(name) is False


@pytest.mark.parametrize("name", gates.KNOWN_FLAGS)
@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", " Yes "])
def test_enabled_truthy_values(monkeypatch, name: str, value: str):
    monkeypatch.setenv(name, value)
    assert gates.enabled(name) is True


def test_enabled_unknown_name_fail_closed(monkeypatch):
    monkeypatch.setenv("SEMBLON_NOT_A_REAL_GATE", "1")
    assert gates.enabled("SEMBLON_NOT_A_REAL_GATE") is False


@pytest.mark.parametrize("name", gates.KNOWN_FLAGS)
def test_require_human_note_nonempty(name: str):
    note = gates.require_human_note(name)
    assert isinstance(note, str)
    assert len(note.strip()) > 20
    assert name in note


def test_require_human_note_unknown_raises():
    with pytest.raises(KeyError):
        gates.require_human_note("SEMBLON_NOT_A_REAL_GATE")


def test_bakeoff_winner_human_only_note():
    """BAKEOFF_WINNER is read-only API; note forbids auto-set."""
    note = gates.require_human_note(gates.BAKEOFF_WINNER)
    assert "never auto-set" in note.lower()
    assert gates.BAKEOFF_WINNER == "SEMBLON_BAKEOFF_WINNER"


def test_canonical_flag_constants():
    assert gates.RULED_OUT == "SEMBLON_RULED_OUT"
    assert gates.LIVE_OVERLAY == "SEMBLON_LIVE_OVERLAY"
    assert gates.WIRE_HOME_LIVE == "SEMBLON_WIRE_HOME_LIVE"
    assert gates.MODALITY_PRODUCT == "SEMBLON_MODALITY_PRODUCT"
    assert set(gates.KNOWN_FLAGS) == {
        gates.RULED_OUT,
        gates.LIVE_OVERLAY,
        gates.WIRE_HOME_LIVE,
        gates.MODALITY_PRODUCT,
        gates.BAKEOFF_WINNER,
    }
