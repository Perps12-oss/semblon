"""Ground truth for the synthetic small-object corpus. No model and no search."""

from __future__ import annotations

import json
from pathlib import Path

from tools.bench_small_object import recall_precision
from tools.small_object_corpus import SEED, checksum, generate, validate


def test_corpus_is_deterministic_and_labelled(tmp_path: Path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    manifest = generate(first, seed=SEED)
    again = generate(second, seed=SEED)
    validate(manifest)
    validate(again)
    assert checksum(manifest) == checksum(again)
    assert manifest["counts"]["queries"] >= 16
    bands = {query["size_band"] for query in manifest["queries"]}
    assert bands == {"very_small", "small", "medium_small", "larger"}
    for query in manifest["queries"]:
        assert query["photo_id"] not in query["relevant_photo_ids"]
        assert query["relevant_photo_ids"]
        assert set(query["relevant_photo_ids"]).isdisjoint(query["category_distractor_photo_ids"])
        assert set(query["relevant_photo_ids"]).isdisjoint(query["visual_distractor_photo_ids"])
        pct = query["area_frac"] * 100.0
        if query["size_band"] == "very_small":
            assert pct < 0.1
        elif query["size_band"] == "small":
            assert 0.1 <= pct < 0.5
        elif query["size_band"] == "medium_small":
            assert 0.5 <= pct < 1.0
        else:
            assert 1.0 <= pct <= 3.0
    dev = [q for q in manifest["queries"] if q["split"] == "dev"]
    held = [q for q in manifest["queries"] if q["split"] == "heldout"]
    assert {q["size_band"] for q in dev} == bands
    assert {q["size_band"] for q in held} == bands
    on_disk = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert [photo["sha256"] for photo in on_disk["photos"]] == [photo["sha256"] for photo in manifest["photos"]]
    for photo in manifest["photos"]:
        blob = (first / "lib" / photo["file"]).read_bytes()
        assert __import__("hashlib").sha256(blob).hexdigest() == photo["sha256"]


def test_recall_precision_uses_the_set_of_relevant_pictures():
    scores = recall_precision(["p2", "other", "p3", "x", "y"], ["p2", "p3", "p4", "p5"], 5)
    assert scores["hits"] == 2
    assert scores["recall"] == 0.5
    assert scores["precision"] == 0.4
    assert scores["any"] is True
    capped = recall_precision(["p2"], ["p2", "p3"], 10)
    assert capped["recall"] == 0.5
    assert capped["precision"] == 0.1
