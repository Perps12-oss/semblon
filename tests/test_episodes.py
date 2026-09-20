"""Derived episode hypotheses from tracks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.cli import main
from semblon.episodes import derive_episodes
from semblon.observers import persist_derived_tracks
from tests.test_tracks import _seed


def _seed_episode_store(path: Path) -> None:
    _seed(path)
    persist_derived_tracks(path, "rt")
    conn = sqlite3.connect(str(path))
    conn.execute("INSERT INTO persons(person_id, display_name, status, created_run) VALUES ('p1','Ada','active','rt')")
    conn.execute("UPDATE faces SET person_id='p1' WHERE face_id IN ('fa','fb')")
    conn.commit()
    conn.close()


def test_derive_episodes_from_tracks(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_episode_store(store)
    rec = derive_episodes(store, run_id="rt", max_gap_ms=2500)
    assert rec["counts"]["tracks"] >= 1
    assert rec["counts"]["episodes"] >= 1
    assert "track != person" in rec["note"]
    assert any("p1" in (ep.get("person_ids") or []) for ep in rec["episodes"])


def test_cli_episodes(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_episode_store(store)
    assert main(["episodes", "--store", str(store), "--run", "rt"]) == 0
