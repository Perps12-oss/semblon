"""FACE-002 confirmatory eval — no InsightFace."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest

from semblon.cli import main
from semblon.cluster import cluster_run
from semblon.eval import (
    DEFAULT_THRESHOLD,
    EvalError,
    MIN_DIFFERENT,
    MIN_SAME,
    add_pair,
    create_set,
    freeze_set,
    mine_discovery,
    score_set,
)
from semblon.observatory import snapshot
from semblon.store import init_db
from tests.test_cluster import _seed


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _face(conn, fid, oid, blob, status="ok"):
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (fid, oid, "r1", 0, 0, 20, 20, 0.9, 20, 20, "80-119", status, blob, "pack-a", 2),
    )


def _seed_eval(path: Path, n_a: int = 5, n_b: int = 5) -> None:
    """Two orthogonal groups. Enough pairs for a powered confirmatory set."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    for i in range(n_a):
        _face(conn, f"a{i}", "o1", _vec(1.0, 0.0))
    for i in range(n_b):
        _face(conn, f"b{i}", "o1", _vec(0.0, 1.0))
    # Near-boundary impostor (sim = 0.8) — challenges the 0.60 threshold.
    _face(conn, "h1", "o1", _vec(0.8, 0.6))
    _face(conn, "h2", "o1", _vec(0.6, 0.8))
    conn.commit()
    conn.close()


def _pairs_same(n: int, prefix: str) -> list[tuple[str, str]]:
    ids = [f"{prefix}{i}" for i in range(n)]
    out = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            out.append((a, b))
    return out


def test_score_refuses_precision_unless_frozen_confirmatory(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    create_set(store, "mine1", "mined_discovery", pack_id="pack-a")
    add_pair(store, "mine1", "f1", "f3", "different", "lookalike")
    rec = score_set(store, "mine1")
    assert rec["status"] == "not_confirmatory"
    assert rec["far"] is None
    assert rec["frr"] is None
    assert rec["fnmr"] is None

    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    add_pair(store, "c1", "f1", "f2", "same", "easy")
    add_pair(store, "c1", "f1", "f3", "different", "lookalike")
    rec = score_set(store, "c1")
    assert rec["status"] == "underpowered"
    assert rec["far"] is None
    assert rec["frozen"] == 0


def test_frozen_set_is_immutable_and_remine_skips_confirmatory(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    add_pair(store, "c1", "f1", "f2", "same", "easy")
    freeze_set(store, "c1")
    with pytest.raises(EvalError, match="frozen"):
        add_pair(store, "c1", "f3", "f4", "same", "easy")
    with pytest.raises(EvalError, match="confirmatory"):
        mine_discovery(store, "r1", "c1")


def test_underpowered_frozen_confirmatory_prints_no_rates(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    add_pair(store, "c1", "f1", "f2", "same", "easy")
    add_pair(store, "c1", "f1", "f5", "different", "lookalike")
    add_pair(store, "c1", "f5", "f7", "different", "low_quality_skip")
    freeze_set(store, "c1")
    rec = score_set(store, "c1")
    assert rec["status"] == "underpowered"
    assert rec["far"] is None
    assert rec["frr"] is None
    assert rec["counts"]["same"] == 1
    assert rec["counts"]["different"] == 2
    assert rec["counts"]["hard_negatives"] >= 1
    board = snapshot(store, "r1")
    assert board["accuracy"]["status"] == "underpowered"
    assert board["accuracy"]["far"] is None


def test_powered_confirmatory_prints_far_frr(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_eval(store)
    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    same = _pairs_same(5, "a")[:MIN_SAME]
    assert len(same) == MIN_SAME
    for a, b in same:
        add_pair(store, "c1", a, b, "same", "easy")
    # 9 easy impostors (sim 0) + 1 hard (sim 0.8 ≥ threshold)
    easy = [(f"a{i}", f"b{j}") for i in range(5) for j in range(5)][: MIN_DIFFERENT - 1]
    for a, b in easy:
        add_pair(store, "c1", a, b, "different", "easy")
    add_pair(store, "c1", "h1", "h2", "different", "lookalike")
    freeze_set(store, "c1")
    rec = score_set(store, "c1")
    assert rec["status"] == "measurable"
    assert rec["threshold"] == DEFAULT_THRESHOLD
    assert rec["counts"]["same"] == MIN_SAME
    assert rec["counts"]["different"] == MIN_DIFFERENT
    assert rec["counts"]["false_accept"] == 1
    assert rec["counts"]["false_reject"] == 0
    assert rec["counts"]["hard_negatives"] == 1
    assert rec["far"] == pytest.approx(0.1)
    assert rec["frr"] == pytest.approx(0.0)
    assert rec["fnmr"] == rec["frr"]
    board = snapshot(store, "r1")
    assert board["accuracy"]["status"] == "measurable"
    assert board["accuracy"]["far"] == pytest.approx(0.1)


def test_cluster_impurity_does_not_change_identity_rules(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    add_pair(store, "c1", "f1", "f2", "different", "should_not_share")
    freeze_set(store, "c1")
    rec = score_set(store, "c1")
    assert rec["counts"]["cluster_impurity"] == 1
    assert rec["status"] == "underpowered"
    assert rec["far"] is None


def test_mine_writes_discovery_only_and_can_remine(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    create_set(store, "d1", "mined_discovery", pack_id="pack-a")
    rec = mine_discovery(store, "r1", "d1", min_sim=0.0, max_pairs=20)
    assert rec["kind"] == "mined_discovery"
    assert rec["pairs"] >= 1
    conn = sqlite3.connect(str(store))
    labels = {r[0] for r in conn.execute("SELECT label FROM eval_pairs WHERE eval_set_id='d1'")}
    kinds = conn.execute("SELECT kind FROM eval_sets WHERE eval_set_id='d1'").fetchone()[0]
    n1 = conn.execute("SELECT COUNT(*) FROM eval_pairs WHERE eval_set_id='d1'").fetchone()[0]
    conn.close()
    assert labels == {"different"}
    assert kinds == "mined_discovery"
    mine_discovery(store, "r1", "d1", min_sim=0.0, max_pairs=20)
    conn = sqlite3.connect(str(store))
    n2 = conn.execute("SELECT COUNT(*) FROM eval_pairs WHERE eval_set_id='d1'").fetchone()[0]
    n_conf = conn.execute(
        "SELECT COUNT(*) FROM eval_sets WHERE kind='confirmatory_hard'"
    ).fetchone()[0]
    conn.close()
    assert n2 == n1
    assert n_conf == 0


def test_score_alias_confirmatory(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    add_pair(store, "c1", "f1", "f2", "same", "easy")
    freeze_set(store, "c1")
    rec = score_set(store, "confirmatory")
    assert rec["eval_set_id"] == "c1"
    assert rec["status"] == "underpowered"


def test_cli_eval_create_pair_freeze_score(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    assert (
        main(
            [
                "lab",
                "eval",
                "create",
                "--store",
                str(store),
                "--eval-set",
                "c1",
                "--kind",
                "confirmatory_hard",
                "--pack",
                "pack-a",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "lab",
                "eval",
                "pair",
                "--store",
                str(store),
                "--eval-set",
                "c1",
                "--faces",
                "f1",
                "f3",
                "--label",
                "different",
                "--stratum",
                "lookalike",
            ]
        )
        == 0
    )
    assert main(["lab", "eval", "freeze", "--store", str(store), "--eval-set", "c1"]) == 0
    assert main(["lab", "eval", "pair", "--store", str(store), "--eval-set", "c1", "--faces", "f2", "f4", "--label", "same", "--stratum", "easy"]) == 2
    assert main(["lab", "eval", "score", "--store", str(store), "--eval-set", "confirmatory"]) == 0
