from __future__ import annotations

from pathlib import Path

from semblon.hotspots import MAX_HOTSPOTS, label_for, rank_hotspots


def _box(i, nx, ny, nw=0.2, nh=0.2, kind="object", snap=True, tag="Dog"):
    return {"id": f"b{i}", "kind": kind, "snap": snap, "tag": tag, "nx": nx, "ny": ny, "nw": nw, "nh": nh}


def test_only_searchable_boxes_become_dots():
    out = rank_hotspots([_box(1, 0.1, 0.1), _box(2, 0.6, 0.6, snap=False)])
    assert [d["id"] for d in out] == ["b1"]


def test_specks_are_skipped():
    assert rank_hotspots([_box(1, 0.1, 0.1, nw=0.02, nh=0.02)]) == []


def test_dots_are_capped_and_biggest_first():
    boxes = [_box(i, (i % 5) * 0.2, (i // 5) * 0.3, nw=0.1 + i * 0.001, nh=0.1) for i in range(15)]
    out = rank_hotspots(boxes)
    assert len(out) <= MAX_HOTSPOTS
    areas = [d["nw"] * d["nh"] for d in out]
    assert areas == sorted(areas, reverse=True)


def test_overlapping_and_crowded_boxes_collapse_to_one():
    out = rank_hotspots([_box(1, 0.1, 0.1), _box(2, 0.12, 0.12), _box(3, 0.15, 0.1, nw=0.1, nh=0.1)])
    assert len(out) == 1


def test_labels_are_plain_words():
    assert label_for({"kind": "face"}) == "a face"
    assert label_for({"kind": "text"}) == "some writing"
    assert label_for({"kind": "object", "tag": "Bicycle"}) == "a bicycle"
    assert label_for({"kind": "object"}) == "this thing"


def test_hotspot_qml_has_no_technical_words():
    text = Path("semblon/native_shell/qml/Hotspots.qml").read_text(encoding="utf-8")
    import re

    for literal in re.findall(r'"([^"]*)"', text):
        for banned in ("embedding", "model", "pack", "query", "database", "index"):
            assert banned not in literal.lower()


def test_neighbouring_writing_becomes_one_dot():
    boxes = [
        _box(1, 0.10, 0.10, nw=0.20, nh=0.05, kind="text", tag=""),
        _box(2, 0.12, 0.17, nw=0.20, nh=0.05, kind="text", tag=""),
        _box(3, 0.70, 0.70, nw=0.20, nh=0.10, kind="text", tag=""),
    ]
    out = rank_hotspots(boxes)
    assert len(out) == 2
    joined = [d for d in out if d["joined"]]
    assert len(joined) == 1
    assert joined[0]["nw"] > 0.2 and joined[0]["nh"] > 0.1


def test_dots_say_what_they_are_for():
    out = rank_hotspots([_box(1, 0.1, 0.1, kind="face"), _box(2, 0.6, 0.6, kind="text", tag="")])
    assert {d["word"] for d in out} == {"Look-alikes", "Writing"}