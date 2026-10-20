"""Multi-leg retrieval: query spec, BM25, RRF, Focus-ready labels."""

from __future__ import annotations

import json

import numpy as np

from semblon.query_spec import parse_query_spec, refine_hint
from semblon.rank_fusion import feature_rerank, reciprocal_rank_fusion
from semblon.store import connect, init_db
from semblon.text_index import bm25_rank


def _run(conn) -> None:
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "emulated"),
    )


def test_query_spec_uses_plain_words():
    spec = parse_query_spec({"mode": "same kind", "word": "red", "part": 0})
    public = spec.as_public()
    assert public["mode"] == "kind"
    assert public["mode_label"] == "Same kind"
    assert public["modifier"] == "red"
    assert "SigLIP" not in public["hint"]
    assert "DINOv2" not in refine_hint(spec)
    assert "same kind" in public["hint"].lower() or "kind" in public["mode_hint"].lower()


def test_bm25_finds_token_overlap_substring_misses():
    ranked = bm25_rank(
        [
            ("a", "a red ceramic mug on the table"),
            ("b", "blue plate"),
        ],
        "red mug",
        limit=2,
    )
    assert ranked
    assert ranked[0][0] == "a"
    assert ranked[0][1] > 0


def test_rrf_prefers_hits_on_more_doors():
    fused = reciprocal_rank_fusion(
        {
            "look": ["m-visual", "m-other"],
            "text": ["m-visual", "m-text"],
            "object": ["m-object"],
        }
    )
    assert max(fused, key=fused.get) == "m-visual"


def test_feature_rerank_lifts_kind_mode():
    items = [
        {
            "media_id": "look-hit",
            "rrf": 0.2,
            "bases": ["Similar look"],
            "door_scores": {"look": 0.9, "kind": 0.1},
        },
        {
            "media_id": "kind-hit",
            "rrf": 0.2,
            "bases": ["Same kind"],
            "door_scores": {"look": 0.2, "kind": 0.9},
        },
    ]
    look = feature_rerank(items, spec={"mode": "look"}, limit=2)
    kind = feature_rerank(items, spec={"mode": "kind"}, limit=2)
    assert look[0]["media_id"] == "look-hit"
    assert kind[0]["media_id"] == "kind-hit"


def test_search_text_adds_token_match(tmp_path):
    from semblon.search import search_text

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    conn.execute("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", ("m1", "folder", "/a.jpg", "a", 8, 8, 0, 1))
    conn.execute("INSERT INTO observations VALUES (?,?,?,?,?)", ("o1", "m1", None, None, "r1"))
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "t1",
            "o1",
            "r1",
            "text",
            "tesseract",
            0,
            0,
            8,
            8,
            1,
            json.dumps({"text": "a red ceramic mug", "role": "ocr", "contract_status": "SUCCESS"}),
        ),
    )
    conn.commit()
    conn.close()
    rec = search_text(store, "red mug")
    assert rec["status"] == "SUCCESS"
    assert rec["media_ids"] == ["m1"]
    assert rec["items"][0]["why"].startswith("OCR")


def test_retrieve_selection_fuses_and_keeps_bases(monkeypatch, tmp_path):
    from semblon.selection_retrieval import retrieve_selection

    crop = np.zeros((8, 8, 3), dtype=np.uint8)

    monkeypatch.setattr(
        "semblon.region_search.find_similar_crop",
        lambda *_args, **_kwargs: {
            "status": "SUCCESS",
            "items": [{"media_id": "m-visual", "score": 0.8, "match_norm": [0.1, 0.2, 0.3, 0.4]}],
            "similarity_basis": "Similar look",
            "engine": "dinov2-patch",
        },
    )
    monkeypatch.setattr(
        "semblon.search.search_text",
        lambda *_args, **_kwargs: {
            "status": "SUCCESS",
            "items": [{"media_id": "m-visual", "score": 1.0}, {"media_id": "m-text", "score": 1.0}],
            "similarity_basis": "Text in photos (OCR substring)",
        },
    )
    monkeypatch.setattr(
        "semblon.search.search_object",
        lambda *_args, **_kwargs: {
            "status": "SUCCESS",
            "items": [{"media_id": "m-object", "score": 0.7}],
            "similarity_basis": "COCO object detection (NanoDet)",
        },
    )
    monkeypatch.setattr("semblon.lens.probe_siglip", lambda: "MISSING")
    rec = retrieve_selection(
        tmp_path / "s.sqlite",
        crop=crop,
        observations=[
            {"kind": "text", "payload": {"text": "Nike Air", "role": "ocr"}},
            {"kind": "object", "payload": {"label": "cup", "class": "cup"}},
        ],
        selection_kind="text_priority",
    )
    assert rec["status"] == "SUCCESS"
    assert rec["items"][0]["media_id"] == "m-visual"
    assert rec["query_spec"]["mode_label"] == "Same look"
    assert "DINOv2" not in rec["query_spec"]["hint"]
    assert rec["strip_label"] == "Similar look"
    assert "Similar look" in rec["similarity_basis"]
    assert "Text in photos (OCR substring)" in rec["similarity_basis"]


def test_remember_and_find_stays_non_identity(tmp_path, monkeypatch):
    from semblon.region_search import remember_and_find

    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"x")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "m1", 32, 32, 0, 1),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(
        "semblon.region_search.crop_bgr",
        lambda *_args, **_kwargs: np.zeros((8, 8, 3), np.uint8),
    )
    monkeypatch.setattr(
        "semblon.region_search.find_similar_region",
        lambda *_args, **_kwargs: {
            "status": "SUCCESS",
            "items": [{"media_id": "m2", "score": 0.5, "match_norm": [0, 0, 1, 1]}],
            "similarity_basis": "Similar look",
            "count": 1,
        },
    )
    monkeypatch.setattr("semblon.lens.probe_siglip", lambda: "MISSING")
    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=0,
        y=0,
        w=8,
        h=8,
        query_spec={"mode": "look", "modifier": "red"},
    )
    assert rec["persons"] == 0
    assert rec["wrote_embedding"] is False
    assert rec["similar"]["query_spec"]["modifier"] == "red"
    assert rec["similar"]["parts"][0]["label"] == "Whole area"
    before = connect(store).execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert before == 0


def test_judge_reorders_without_writing(tmp_path):
    import cv2

    from semblon.match_judge import judge_matches

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    red = tmp_path / "red.png"
    blue = tmp_path / "blue.png"
    cv2.imwrite(str(red), np.full((24, 24, 3), (20, 20, 200), dtype=np.uint8))
    cv2.imwrite(str(blue), np.full((24, 24, 3), (200, 20, 20), dtype=np.uint8))
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("red", "folder", str(red), "red", 24, 24, 0, 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("blue", "folder", str(blue), "blue", 24, 24, 0, 1),
    )
    conn.commit()
    conn.close()
    query = np.full((16, 16, 3), (20, 20, 200), dtype=np.uint8)
    rec = judge_matches(
        store,
        crop=query,
        items=[
            {"media_id": "blue", "score": 0.9, "match_norm": [0, 0, 1, 1]},
            {"media_id": "red", "score": 0.4, "match_norm": [0, 0, 1, 1]},
        ],
    )
    assert rec["judge"] == "ready"
    assert rec["items"][0]["media_id"] == "red"
    assert connect(store).execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
    assert connect(store).execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0


def test_judge_skips_when_there_is_nothing_to_compare(tmp_path):
    from semblon.match_judge import judge_matches

    rec = judge_matches(
        tmp_path / "missing.sqlite",
        crop=None,
        items=[{"media_id": "m1", "score": 0.5}],
    )
    assert rec["status"] == "SKIPPED"
    assert rec["items"][0]["media_id"] == "m1"
