"""Labelled Lens eval: ranks and hard negatives. No precision on synthetic."""

from __future__ import annotations

import json

from semblon.lens_eval import (
    EVAL_SET_CONFIRMATORY,
    EVAL_SET_SYNTHETIC,
    FAMILY_BRAND_TEXT,
    FAMILY_HARD_NEG_COLOUR,
    FAMILY_PART_VS_WHOLE,
    FAMILY_SAME_KIND,
    FAMILY_SAME_LOOK,
    LensEvalError,
    build_synthetic_store,
    identity_clean,
    labelled_cases,
    normalize_eval_set,
    precision_allowed,
    precision_refusal,
    relevant_above_hard_neg,
    run_case,
    run_eval,
    score_report,
)
from semblon.store import connect


def _by_family(family: str):
    for case in labelled_cases():
        if case.family == family:
            return case
    raise AssertionError(family)


def test_eval_set_aliases():
    assert normalize_eval_set("synthetic") == EVAL_SET_SYNTHETIC
    assert normalize_eval_set("confirmatory") == EVAL_SET_CONFIRMATORY
    assert precision_allowed("synthetic") is False
    assert precision_allowed("confirmatory") is True
    assert "refused" in precision_refusal("synthetic")
    try:
        normalize_eval_set("ann")
    except LensEvalError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("ann is not an eval set")


def test_relevant_above_hard_neg_needs_a_relevant_hit():
    assert relevant_above_hard_neg(["rel", "neg"], ["rel"], ["neg"]) is True
    assert relevant_above_hard_neg(["neg", "rel"], ["rel"], ["neg"]) is False
    assert relevant_above_hard_neg(["rel"], ["rel"], ["neg"]) is True
    assert relevant_above_hard_neg(["neg"], ["rel"], ["neg"]) is False


def test_synthetic_brand_text_finds_acme(tmp_path):
    """BM25 must recall ACME. Beating a confident look-alike is the measured bar."""
    case = _by_family(FAMILY_BRAND_TEXT)
    assert case.observations[0]["payload"]["text"] == "ACME"
    rec = run_case(build_synthetic_store(tmp_path), case)
    assert rec["pass"] is True
    assert rec["relevant_ranks"]["acme-hit"] == 1
    assert rec["relevant_ranks"]["acme-hit"] < rec["hard_neg_ranks"]["acne-lookalike"]


def test_synthetic_same_kind_cup_above_chair(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_SAME_KIND))
    assert rec["pass"] is True
    assert rec["query_spec"]["mode_label"] == "Same kind"
    assert rec["relevant_ranks"]["cup-blue"] is not None
    chair = rec["hard_neg_ranks"]["chair-red"]
    assert chair is None or rec["relevant_ranks"]["cup-blue"] < chair


def test_synthetic_same_look_prefers_red_cup_over_blue(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_SAME_LOOK))
    assert rec["pass"] is True
    assert rec["query_spec"]["mode"] == "look"
    assert rec["relevant_ranks"]["cup-red-2"] < (rec["hard_neg_ranks"]["cup-blue"] or 99)


def test_synthetic_part_recalls_the_logo(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_PART_VS_WHOLE))
    assert rec["query_spec"]["part_index"] == 0
    assert rec["pass"] is True
    assert rec["relevant_ranks"]["logo-hit"] < rec["hard_neg_ranks"]["shirt-plain"]


def test_synthetic_hard_neg_same_colour_chair_loses(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_HARD_NEG_COLOUR))
    assert rec["pass"] is True
    assert rec["ranked"][0] != "chair-red"
    assert rec["relevant_ranks"]["cup-red-2"] < (rec["hard_neg_ranks"]["chair-red"] or 99)


def test_synthetic_refuses_precision(tmp_path):
    report = run_eval(tmp_path / "work", eval_set="synthetic")
    assert report["eval_set"] == EVAL_SET_SYNTHETIC
    assert report["precision"] is None
    assert report["precision_at_5"] is None
    assert report["recall_at_5"] is None
    assert "refused" in report["precision_reason"]
    assert report["status"] in {"PASS", "FAIL"}
    families = {row["family"] for row in report["cases"]}
    assert families == {
        FAMILY_BRAND_TEXT,
        FAMILY_SAME_KIND,
        FAMILY_SAME_LOOK,
        FAMILY_PART_VS_WHOLE,
        FAMILY_HARD_NEG_COLOUR,
    }
    dumped = json.dumps(report)
    assert '"precision": null' in dumped
    assert report["timing"]["ann_justified"] is False


def test_confirmatory_refuses_precision_without_frozen_set(tmp_path):
    report = run_eval(tmp_path / "work", eval_set="confirmatory")
    assert report["eval_set"] == EVAL_SET_CONFIRMATORY
    assert report["status"] == "not_confirmatory"
    assert report["precision"] is None
    assert "confirmatory" in report["precision_reason"]


def test_eval_does_not_write_identity(tmp_path):
    store = build_synthetic_store(tmp_path)
    for case in labelled_cases():
        run_case(store, case)
    assert identity_clean(store)
    conn = connect(store)
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    assert (
        conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
        == 0
    )
    conn.close()


def _write_swatch(path, color):
    import cv2
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), np.full((16, 16, 3), color, dtype=np.uint8))


def test_confirmatory_manifest_scores_precision_and_refuses_synthetic_ids(tmp_path):
    from semblon.lens_eval import load_confirmatory

    folder = tmp_path / "owner"
    folder.mkdir()
    media = []
    for name, color in (
        ("q-b", (10, 10, 200)),
        ("h-b", (12, 12, 180)),
        ("n-b", (14, 14, 160)),
        ("q-k", (20, 20, 20)),
        ("h-k", (30, 80, 20)),
        ("n-k", (20, 20, 200)),
        ("q-l", (40, 40, 200)),
        ("h-l", (40, 40, 180)),
        ("n-l", (200, 40, 40)),
        ("q-p", (140, 140, 140)),
        ("h-p", (150, 150, 150)),
        ("n-p", (130, 130, 130)),
        ("q-c", (20, 20, 200)),
        ("h-c", (20, 20, 190)),
        ("n-c", (20, 20, 170)),
    ):
        _write_swatch(folder / f"{name}.png", color)
        row = {"media_id": name, "image": f"{name}.png"}
        if name in {"h-b", "q-b"}:
            row["text"] = "TOKENB"
        if name in {"h-p", "q-p"}:
            row["text"] = "MARKP"
        if name in {"q-k", "h-k"}:
            row["objects"] = ["widget"]
        if name == "n-k":
            row["objects"] = ["stool"]
        if name in {"q-c", "h-c"}:
            row["objects"] = ["cupc"]
        if name == "n-c":
            row["objects"] = ["chairc"]
        media.append(row)
    manifest = {
        "frozen": True,
        "source": "owner-photographs",
        "eval_set": "confirmatory",
        "media": media,
        "cases": [
            {
                "case_id": "owner-brand",
                "family": "brand_text",
                "query_media_id": "q-b",
                "relevant": ["h-b"],
                "hard_negatives": ["n-b"],
                "observations": [{"kind": "text", "payload": {"text": "TOKENB", "role": "ocr"}}],
                "query_spec": {"mode": "look"},
                "look_items": [
                    {"media_id": "n-b", "score": 0.91, "match_norm": [0, 0, 1, 1]},
                    {"media_id": "h-b", "score": 0.31, "match_norm": [0, 0, 1, 1]},
                ],
                "notes": "owner brand",
            },
            {
                "case_id": "owner-kind",
                "family": "same_kind",
                "query_media_id": "q-k",
                "relevant": ["h-k"],
                "hard_negatives": ["n-k"],
                "observations": [{"kind": "object", "payload": {"label": "widget", "class": "widget"}}],
                "query_spec": {"mode": "kind"},
                "look_items": [
                    {"media_id": "n-k", "score": 0.93, "match_norm": [0, 0, 1, 1]},
                    {"media_id": "h-k", "score": 0.3, "match_norm": [0, 0, 1, 1]},
                ],
                "notes": "owner kind",
            },
            {
                "case_id": "owner-look",
                "family": "same_look",
                "query_media_id": "q-l",
                "relevant": ["h-l"],
                "hard_negatives": ["n-l"],
                "observations": [],
                "query_spec": {"mode": "look"},
                "look_items": [
                    {"media_id": "h-l", "score": 0.91, "match_norm": [0, 0, 1, 1]},
                    {"media_id": "n-l", "score": 0.4, "match_norm": [0, 0, 1, 1]},
                ],
                "notes": "owner look",
            },
            {
                "case_id": "owner-part",
                "family": "part_vs_whole",
                "query_media_id": "q-p",
                "relevant": ["h-p"],
                "hard_negatives": ["n-p"],
                "observations": [{"kind": "text", "payload": {"text": "MARKP", "role": "ocr"}}],
                "query_spec": {"mode": "look", "part_index": 0},
                "look_items": [
                    {"media_id": "n-p", "score": 0.90, "match_norm": [0, 0, 1, 1]},
                    {"media_id": "h-p", "score": 0.22, "match_norm": [0, 0, 1, 1]},
                ],
                "notes": "owner part",
            },
            {
                "case_id": "owner-colour",
                "family": "hard_neg_colour",
                "query_media_id": "q-c",
                "relevant": ["h-c"],
                "hard_negatives": ["n-c"],
                "observations": [{"kind": "object", "payload": {"label": "cupc", "class": "cupc"}}],
                "query_spec": {"mode": "look"},
                "look_items": [
                    {"media_id": "n-c", "score": 0.96, "match_norm": [0, 0, 1, 1]},
                    {"media_id": "h-c", "score": 0.7, "match_norm": [0, 0, 1, 1]},
                ],
                "notes": "owner colour",
            },
        ],
    }
    path = folder / "lens-confirmatory.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    report = run_eval(tmp_path / "work", eval_set="confirmatory", confirmatory_file=path)
    assert report["status"] == "PASS"
    assert report["precision"] is not None
    assert report["precision_at_5"] == report["precision"]
    assert report["failures"] == []
    assert "confirmatory frozen set" in report["precision_reason"]

    stolen = dict(manifest)
    stolen["media"] = [{"media_id": "acme-hit", "image": "h-b.png"}]
    stolen_path = folder / "stolen.json"
    stolen_path.write_text(json.dumps(stolen), encoding="utf-8")
    cases, _media, reason = load_confirmatory(stolen_path)
    assert cases == []
    assert "synthetic" in reason


def test_ann_stays_parked_on_synthetic_timing(tmp_path):
    report = score_report(
        [
            {
                "case_id": "x",
                "pass": True,
                "relevant_ranks": {"a": 1},
                "hard_neg_ranks": {"b": None},
            }
        ],
        eval_set="synthetic",
        elapsed_ms=4.0,
        corpus_size=10,
    )
    assert report["timing"]["ann_justified"] is False
    assert report["timing"]["index"]["ann"]["enabled"] is False
    assert "parked" in report["timing"]["ann_reason"].lower() or "small" in report["timing"]["ann_reason"].lower()
