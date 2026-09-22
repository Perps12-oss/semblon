"""Artifact 2 state triple — pure aggregator (no Tk)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from semblon.canvas import load_canvas, media_inspector_lines, media_state_triples
from semblon.home_ui import format_library_lines
from semblon.state_triple import (
    ANALYSIS_DONE,
    ANALYSIS_FAILED,
    ANALYSIS_PAUSED,
    ANALYSIS_QUEUED,
    ANALYSIS_RUNNING,
    ANALYSIS_STALE,
    ANALYSIS_VALUES,
    FACE_CONFIRMED,
    FACE_IGNORED,
    FACE_POSSIBLE,
    FACE_RULED_OUT,
    FACE_UNKNOWN,
    GLYPH_BROKEN,
    GLYPH_NONE,
    GLYPH_WARN,
    IDENTITY_CONFIRMED,
    IDENTITY_MIXED,
    IDENTITY_NONE,
    IDENTITY_POSSIBLE,
    IDENTITY_UNKNOWN,
    IDENTITY_VALUES,
    INGEST_FAILED,
    INGEST_MISSING,
    INGEST_OK,
    INGEST_VALUES,
    NOTCH_DASHED_3_2,
    NOTCH_DASHED_6_4,
    NOTCH_EMPTY_DIM,
    NOTCH_SOLID,
    NOTCH_SOLID_NEQ,
    RING_DOTTED,
    RING_GAP_BANG,
    RING_HOLLOW,
    RING_PARTIAL,
    RING_PARTIAL_PAUSED,
    RING_SOLID,
    aggregate_identity,
    build_triple,
    channel_markers,
    decision_action_sets,
    derive_analysis,
    derive_ingest,
    face_identity_state,
    format_media_card_label,
    glyph_for,
    library_include_media,
    media_inspector_triple_line,
    notch_for,
    ring_for,
    state_triple_for_media,
    triples_for_board,
)
from semblon.store import init_db


def test_vocabularies_match_artifact_2():
    assert INGEST_VALUES == {INGEST_OK, INGEST_FAILED, INGEST_MISSING}
    assert ANALYSIS_VALUES == {
        ANALYSIS_QUEUED,
        ANALYSIS_RUNNING,
        ANALYSIS_PAUSED,
        ANALYSIS_DONE,
        ANALYSIS_FAILED,
        ANALYSIS_STALE,
    }
    assert IDENTITY_VALUES == {
        IDENTITY_NONE,
        IDENTITY_UNKNOWN,
        IDENTITY_POSSIBLE,
        IDENTITY_CONFIRMED,
        IDENTITY_MIXED,
    }


@pytest.mark.parametrize(
    "states,expected",
    [
        ([], IDENTITY_NONE),
        ([FACE_IGNORED], IDENTITY_NONE),
        ([FACE_IGNORED, FACE_IGNORED], IDENTITY_NONE),
        ([FACE_UNKNOWN], IDENTITY_UNKNOWN),
        ([FACE_POSSIBLE], IDENTITY_POSSIBLE),
        ([FACE_CONFIRMED], IDENTITY_CONFIRMED),
        ([FACE_RULED_OUT], IDENTITY_NONE),
        ([FACE_CONFIRMED, FACE_RULED_OUT], IDENTITY_MIXED),
        ([FACE_UNKNOWN, FACE_POSSIBLE], IDENTITY_UNKNOWN),
        ([FACE_UNKNOWN, FACE_CONFIRMED], IDENTITY_UNKNOWN),
        ([FACE_POSSIBLE, FACE_CONFIRMED], IDENTITY_POSSIBLE),
        ([FACE_POSSIBLE, FACE_RULED_OUT], IDENTITY_POSSIBLE),
        ([FACE_IGNORED, FACE_UNKNOWN], IDENTITY_UNKNOWN),
        ([FACE_IGNORED, FACE_CONFIRMED, FACE_RULED_OUT], IDENTITY_MIXED),
        ([FACE_CONFIRMED, FACE_CONFIRMED], IDENTITY_CONFIRMED),
    ],
)
def test_aggregate_identity_worst_unresolved(states, expected):
    assert aggregate_identity(states) == expected


@pytest.mark.parametrize(
    "identity,style,neq",
    [
        (IDENTITY_NONE, NOTCH_EMPTY_DIM, False),
        (IDENTITY_UNKNOWN, NOTCH_DASHED_6_4, False),
        (IDENTITY_POSSIBLE, NOTCH_DASHED_3_2, False),
        (IDENTITY_CONFIRMED, NOTCH_SOLID, False),
        (IDENTITY_MIXED, NOTCH_SOLID_NEQ, True),
    ],
)
def test_notch_grammar(identity, style, neq):
    n = notch_for(identity)
    assert n.style == style
    assert n.neq is neq
    assert n.aggregate == identity


@pytest.mark.parametrize(
    "analysis,style,bang,pause",
    [
        (ANALYSIS_QUEUED, RING_HOLLOW, False, False),
        (ANALYSIS_RUNNING, RING_PARTIAL, False, False),
        (ANALYSIS_PAUSED, RING_PARTIAL_PAUSED, False, True),
        (ANALYSIS_DONE, RING_SOLID, False, False),
        (ANALYSIS_FAILED, RING_GAP_BANG, True, False),
        (ANALYSIS_STALE, RING_DOTTED, False, False),
    ],
)
def test_ring_grammar_shape_not_hue(analysis, style, bang, pause):
    r = ring_for(analysis)
    assert r.style == style
    assert r.bang is bang
    assert r.pause_mark is pause


@pytest.mark.parametrize(
    "ingest,style,mark",
    [
        (INGEST_OK, GLYPH_NONE, ""),
        (INGEST_FAILED, GLYPH_WARN, "⚠"),
        (INGEST_MISSING, GLYPH_BROKEN, "broken"),
    ],
)
def test_ingest_glyph_channel(ingest, style, mark):
    g = glyph_for(ingest)
    assert g.style == style
    assert g.mark == mark


def test_channels_do_not_collide_across_layers():
    """Spatial channels stay distinct even when style tokens share a word.

    Confirmed notch and done ring can both be "solid" — they live in different
    slots (corner vs border). Collision is sharing a *channel*, not a token.
    """
    t = build_triple(
        ingest=INGEST_FAILED, analysis=ANALYSIS_PAUSED, identity=IDENTITY_UNKNOWN
    )
    # Three distinct presentation objects / marks
    assert t.notch.style == NOTCH_DASHED_6_4
    assert t.ring.style == RING_PARTIAL_PAUSED
    assert t.glyph.style == GLYPH_WARN
    marks = channel_markers(t)
    # Identity dashed mark ≠ analysis pause ring ≠ ingest warn glyph
    assert marks.startswith("⬚")
    assert "◑" in marks
    assert "⚠" in marks
    # Ingest failed glyph must not be reused as analysis bang
    t2 = build_triple(
        ingest=INGEST_OK, analysis=ANALYSIS_FAILED, identity=IDENTITY_NONE
    )
    assert t2.glyph.mark == ""
    assert t2.ring.bang is True
    assert "○!" in channel_markers(t2)
    assert "⚠" not in channel_markers(t2)


def test_face_identity_from_evidence_and_decisions():
    assert face_identity_state({"face_id": "f1"}) == FACE_UNKNOWN
    assert face_identity_state({"face_id": "f1", "cluster_id": "c1"}) == FACE_POSSIBLE
    assert (
        face_identity_state({"face_id": "f1", "cluster_id": "c1", "person_id": "p1"})
        == FACE_CONFIRMED
    )
    assert (
        face_identity_state(
            {"face_id": "f1", "cluster_id": "c1"},
            ignored_faces={"f1"},
        )
        == FACE_IGNORED
    )
    assert (
        face_identity_state(
            {"face_id": "f1", "cluster_id": "c1"},
            ignored_clusters={"c1"},
        )
        == FACE_IGNORED
    )
    assert (
        face_identity_state(
            {"face_id": "f1", "cluster_id": "c1"},
            cluster_status={"c1": "ignored"},
        )
        == FACE_IGNORED
    )
    assert (
        face_identity_state(
            {"face_id": "f1", "cluster_id": "c1", "person_id": "p1"},
            ruled_out_faces={"f1"},
        )
        == FACE_RULED_OUT
    )
    assert (
        face_identity_state(
            {"face_id": "f2", "cluster_id": "c9"},
            ruled_out_clusters={"c9"},
        )
        == FACE_RULED_OUT
    )


def test_decision_action_sets_ignore_vs_rule_out():
    decisions = [
        {
            "kind": "reject",
            "face_id": "f1",
            "cluster_id": None,
            "policy_json": json.dumps({"action": "ignore"}),
        },
        {
            "kind": "reject",
            "face_id": None,
            "cluster_id": "c2",
            "policy_json": json.dumps({"action": "rule_out"}),
        },
        {
            "kind": "name",
            "face_id": "f3",
            "cluster_id": None,
            "policy_json": "{}",
        },
        {
            "kind": "reject",
            "face_id": "f4",
            "cluster_id": None,
            "policy": {"action": "ignore"},
        },
    ]
    ign_f, ign_c, rule_f, rule_c = decision_action_sets(decisions)
    assert ign_f == {"f1", "f4"}
    assert ign_c == set()
    assert rule_f == set()
    assert rule_c == {"c2"}


def test_derive_ingest_path_and_failed():
    assert derive_ingest(path_exists=True) == INGEST_OK
    assert derive_ingest(path_exists=False) == INGEST_MISSING
    assert derive_ingest(ingest_failed=True, path_exists=True) == INGEST_FAILED
    assert derive_ingest(path=None) == INGEST_MISSING
    assert derive_ingest(path="/nope.jpg", exists_fn=lambda _p: False) == INGEST_MISSING
    assert derive_ingest(path="/ok.jpg", exists_fn=lambda _p: True) == INGEST_OK


def test_library_excludes_failed_ingest():
    t_fail = build_triple(
        ingest=INGEST_FAILED, analysis=ANALYSIS_DONE, identity=IDENTITY_NONE
    )
    t_ok = build_triple(
        ingest=INGEST_OK, analysis=ANALYSIS_DONE, identity=IDENTITY_NONE
    )
    t_miss = build_triple(
        ingest=INGEST_MISSING, analysis=ANALYSIS_DONE, identity=IDENTITY_NONE
    )
    assert library_include_media(t_fail) is False
    assert library_include_media(t_ok) is True
    assert library_include_media(t_miss) is True


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"has_observation": True}, ANALYSIS_DONE),
        ({"has_observation": False, "run_finished": False}, ANALYSIS_QUEUED),
        ({"has_observation": False, "run_finished": True}, ANALYSIS_DONE),
        (
            {
                "has_observation": False,
                "job_state": "running",
                "is_current_media": True,
            },
            ANALYSIS_RUNNING,
        ),
        (
            {
                "has_observation": False,
                "job_state": "paused",
                "is_current_media": True,
            },
            ANALYSIS_PAUSED,
        ),
        (
            {
                "has_observation": False,
                "job_state": "failed",
                "is_current_media": True,
            },
            ANALYSIS_FAILED,
        ),
        ({"stale": True, "has_observation": True}, ANALYSIS_STALE),
        ({"job_state": "stalled", "has_observation": True}, ANALYSIS_STALE),
        ({"job_state": "queued", "has_observation": False}, ANALYSIS_QUEUED),
        (
            {
                "has_observation": True,
                "job_state": "running",
                "is_current_media": False,
            },
            ANALYSIS_DONE,
        ),
        (
            {
                "has_observation": False,
                "job_state": "cancelled",
                "is_current_media": True,
            },
            ANALYSIS_PAUSED,
        ),
        (
            {
                "has_observation": False,
                "job_state": "started",
                "is_current_media": True,
            },
            ANALYSIS_RUNNING,
        ),
    ],
)
def test_derive_analysis(kwargs, expected):
    assert derive_analysis(**kwargs) == expected


def test_state_triple_for_media_end_to_end():
    media = {"media_id": "m1", "path": "/a.jpg", "source_type": "folder"}
    faces = [
        {"face_id": "f1", "media_id": "m1", "cluster_id": None, "person_id": None},
        {"face_id": "f2", "media_id": "m1", "cluster_id": "c1", "person_id": None},
    ]
    t = state_triple_for_media(
        media,
        faces,
        path_exists=True,
        has_observation=True,
        run_finished=True,
    )
    assert t.ingest == INGEST_OK
    assert t.analysis == ANALYSIS_DONE
    assert t.identity == IDENTITY_UNKNOWN  # any unknown wins
    assert t.notch.style == NOTCH_DASHED_6_4
    assert t.ring.style == RING_SOLID
    assert t.glyph.style == GLYPH_NONE
    assert "⚠" not in channel_markers(t)


def test_mixed_confirmed_and_ruled_out():
    media = {"media_id": "m1", "path": "/a.jpg"}
    faces = [
        {"face_id": "f1", "person_id": "p1", "cluster_id": "c1"},
        {"face_id": "f2", "person_id": None, "cluster_id": "c2"},
    ]
    decisions = [
        {
            "kind": "reject",
            "face_id": "f2",
            "cluster_id": None,
            "policy_json": json.dumps({"action": "rule_out"}),
        }
    ]
    t = state_triple_for_media(
        media, faces, decisions=decisions, path_exists=True, has_observation=True
    )
    assert t.identity == IDENTITY_MIXED
    assert t.notch.neq is True
    assert "≠" in channel_markers(t)


def test_channel_markers_order_identity_analysis_ingest():
    t = build_triple(
        ingest=INGEST_MISSING,
        analysis=ANALYSIS_STALE,
        identity=IDENTITY_POSSIBLE,
    )
    marks = channel_markers(t).split()
    # identity, analysis, ingest — three tokens (missing glyph may be ◻/)
    assert marks[0] == "◧"
    assert marks[1] == "◌"
    assert "◻/" in channel_markers(t)


def test_format_media_card_label_includes_all_channels():
    t = build_triple(
        ingest=INGEST_OK, analysis=ANALYSIS_RUNNING, identity=IDENTITY_CONFIRMED
    )
    label = format_media_card_label(
        {"source_type": "folder", "path": "/x.jpg"},
        t,
        face_count=2,
        item_count=1,
    )
    assert "◆" in label
    assert "◐" in label
    assert "·" in label
    assert "faces=2" in label
    assert "items=1" in label
    assert "/x.jpg" in label


def test_build_triple_rejects_unknown_vocab():
    with pytest.raises(ValueError):
        build_triple(ingest="nope", analysis=ANALYSIS_DONE, identity=IDENTITY_NONE)
    with pytest.raises(ValueError):
        build_triple(ingest=INGEST_OK, analysis="nope", identity=IDENTITY_NONE)
    with pytest.raises(ValueError):
        build_triple(ingest=INGEST_OK, analysis=ANALYSIS_DONE, identity="nope")


def test_triples_for_board_and_overrides():
    board = {
        "media": [
            {"media_id": "m1", "path": "/a.jpg", "source_type": "folder"},
            {"media_id": "m2", "path": "/b.jpg", "source_type": "folder"},
        ],
        "faces": [
            {
                "face_id": "f1",
                "media_id": "m1",
                "cluster_id": "c1",
                "person_id": None,
            }
        ],
        "items": [],
        "decisions": [],
    }
    triples = triples_for_board(
        board,
        path_exists_by_id={"m1": True, "m2": False},
        run_finished=True,
        analysis_by_media={"m2": ANALYSIS_QUEUED},
        observed_media_ids={"m1"},
    )
    assert triples["m1"].identity == IDENTITY_POSSIBLE
    assert triples["m1"].ingest == INGEST_OK
    assert triples["m1"].analysis == ANALYSIS_DONE
    assert triples["m2"].ingest == INGEST_MISSING
    assert triples["m2"].analysis == ANALYSIS_QUEUED
    assert triples["m2"].identity == IDENTITY_NONE


def test_media_inspector_triple_line_names_channels():
    t = build_triple(
        ingest=INGEST_OK, analysis=ANALYSIS_DONE, identity=IDENTITY_UNKNOWN
    )
    line = media_inspector_triple_line(t)
    assert "state=(ok, done, unknown)" in line
    assert "notch=" in line
    assert "ring=" in line
    assert "glyph=" in line


def _seed_store(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "t2", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    # Existing files on disk for path checks.
    img_a = path.parent / "a.jpg"
    img_b = path.parent / "b.jpg"
    img_a.write_bytes(b"fake")
    img_b.write_bytes(b"fake")
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(img_a), "aaa", 100, 100, 0, 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m2", "folder", str(img_b), "bbb", 100, 100, 0, 1),
    )
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    conn.execute(
        """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, status)
           VALUES ('c1','r1','dbscan',1,'auto')"""
    )
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,cluster_id,person_id)
           VALUES ('f1','o1','r1',0,0,10,10,0.9,10,10,'80-119','ok','c1',NULL)"""
    )
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,cluster_id,person_id)
           VALUES ('f2','o2','r1',0,0,10,10,0.9,10,10,'80-119','ok',NULL,NULL)"""
    )
    conn.commit()
    conn.close()


def test_load_canvas_exposes_decisions_and_triples(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_store(store)
    board = load_canvas(store, "r1")
    assert "decisions" in board
    assert board.get("run_finished") is True
    triples = media_state_triples(board)
    assert triples["m1"].identity == IDENTITY_POSSIBLE
    assert triples["m2"].identity == IDENTITY_UNKNOWN
    lines = media_inspector_lines(board, "m1")
    assert any(line.startswith("state=(") for line in lines)


def test_format_library_lines_include_channel_markers(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_store(store)
    lines = format_library_lines(store)
    body = "\n".join(lines)
    assert "state=(Ingest, Analysis, Identity)" in body or "state triple" in body
    # possible + unknown notches appear
    assert "◧" in body or "⬚" in body
    assert "●" in body  # analysis done ring


def test_as_dict_roundtrip_shape():
    t = build_triple(
        ingest=INGEST_OK, analysis=ANALYSIS_FAILED, identity=IDENTITY_MIXED
    )
    d = t.as_dict()
    assert d["ingest"] == INGEST_OK
    assert d["analysis"] == ANALYSIS_FAILED
    assert d["identity"] == IDENTITY_MIXED
    assert d["notch"]["neq"] is True
    assert d["ring"]["bang"] is True
