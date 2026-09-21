"""R3 frames catalog — collision ledger, state-triple, hierarchy (§8.6 last)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.r3_frames.catalog import FRAME_SETS, generate_catalog  # noqa: E402


def test_catalog_non_empty():
    cat = generate_catalog()
    assert len(cat) >= 15
    assert set(FRAME_SETS) == {"collision_ledger", "state_triple", "hierarchy"}


def test_collision_includes_disabled_unknown_processing():
    cat = generate_catalog()
    collisions = [f for f in cat if f["set"] == "collision_ledger"]
    pairs = {(f["left"], f["right"]) for f in collisions}
    assert ("Disabled", "Unknown") in pairs
    assert ("Unknown", "Processing") in pairs
    assert ("Disabled", "Processing") in pairs


def test_collision_includes_ruled_out_vs_ignored():
    cat = generate_catalog()
    pairs = {(f["left"], f["right"]) for f in cat if f["set"] == "collision_ledger"}
    assert ("Ruled out", "Ignored") in pairs


def test_state_triple_has_thirty_cards():
    triples = [f for f in generate_catalog() if f["set"] == "state_triple"]
    assert len(triples) == 30
    notches = {f["notch"] for f in triples}
    assert notches == {"Unknown", "Possible", "Confirmed", "Ruled out", "Ignored"}


def test_hierarchy_frames_marked_last():
    hier = [f for f in generate_catalog() if f["set"] == "hierarchy"]
    assert len(hier) >= 1
    assert all("§8.6" in (f.get("note") or "") for f in hier)
