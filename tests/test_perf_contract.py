"""A+B no-regression semantic contract."""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

from semblon.cli import main
from semblon.cluster import cluster_run
from semblon.perf_contract import (
    build_semantic_snapshot,
    compare_semantic_snapshots,
    read_snapshot,
    write_snapshot,
)
from tests.test_cluster import _seed


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _seed_contract_store(path: Path) -> None:
    conn = _seed(path)
    runtime = {
        "workers": 1,
        "provider": "facekit",
        "execution_provider": "CPUExecutionProvider",
        "onnx_providers": ["CPUExecutionProvider"],
        "gpu": False,
        "device": "cpu",
        "arch": "x64",
        "execution": "native",
    }
    timings = {
        "files": 2,
        "new_media": 2,
        "skipped_seen": 0,
        "skipped_same_run": 0,
        "failed": 0,
        "faces": 7,
        "ok": 5,
        "low_quality": 1,
        "rejected": 1,
        "workers": 1,
        "model_load_s": 0.1,
        "ingest_s": 1.0,
        "images_per_second": 2.0,
        "faces_per_second": 7.0,
    }
    conn.execute(
        "UPDATE runs SET runtime_json=?, timings_json=? WHERE run_id='r1'",
        (json.dumps(runtime), json.dumps(timings)),
    )
    conn.execute(
        """
        INSERT INTO observation_items(
            item_id, observation_id, run_id, kind, provider, payload_json
        ) VALUES ('it1','o1','r1','appearance','color-hist','{}')
        """
    )
    conn.execute(
        """
        INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
        VALUES ('emb1','it1','appearance','appearance/rgb8@1',2,?)
        """,
        (_vec(0.6, 0.8),),
    )
    conn.commit()
    conn.close()
    cluster_run(path, "r1", eps=0.15, min_samples=2)


def test_snapshot_build_and_roundtrip(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_contract_store(store)
    snap = build_semantic_snapshot(store, "r1", embedding_tol=1e-5)
    assert snap["contract_version"] == "1"
    assert snap["counts"]["faces"] == 7
    assert snap["isolation"]["ok"] is True
    assert snap["guards"]["observation_track_person_ok"] is True
    assert snap["runtime_evidence"]["complete"] is True

    out = tmp_path / "snap.json"
    write_snapshot(out, snap)
    loaded = read_snapshot(out)
    assert loaded["run_id"] == "r1"
    assert loaded["embedding_tolerance"] == 1e-05


def test_compare_same_snapshot_is_ok(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_contract_store(store)
    before = build_semantic_snapshot(store, "r1", embedding_tol=1e-6)
    after = build_semantic_snapshot(store, "r1", embedding_tol=1e-6)
    rec = compare_semantic_snapshots(before, after)
    assert rec["ok"] is True
    assert rec["diffs"] == []


def test_compare_detects_embedding_drift(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_contract_store(store)
    before = build_semantic_snapshot(store, "r1", embedding_tol=1e-6)
    conn = sqlite3.connect(str(store))
    conn.execute("UPDATE faces SET embedding=? WHERE face_id='f1'", (_vec(0.0, 1.0),))
    conn.commit()
    conn.close()
    after = build_semantic_snapshot(store, "r1", embedding_tol=1e-6)
    rec = compare_semantic_snapshots(before, after)
    assert rec["ok"] is False
    assert any("face embedding changed beyond tolerance" in d for d in rec["diffs"])


def test_cli_contract_snapshot_and_compare(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_contract_store(store)
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    assert (
        main(
            [
                "lab",
                "contract",
                "snapshot",
                "--store",
                str(store),
                "--run",
                "r1",
                "--out",
                str(before),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "lab",
                "contract",
                "snapshot",
                "--store",
                str(store),
                "--run",
                "r1",
                "--out",
                str(after),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "lab",
                "contract",
                "compare",
                "--before",
                str(before),
                "--after",
                str(after),
            ]
        )
        == 0
    )
