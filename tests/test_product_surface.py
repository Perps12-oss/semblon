"""Product surface — soft copy + region hit-test (no identity writes)."""

from __future__ import annotations

from semblon.product_surface import (
    VERB_LABEL_ASSIGN,
    VERB_LABEL_MERGE,
    VERB_LABEL_NAME,
    region_hits,
    soft_canvas_status,
    soft_inspector_for_face,
    soft_inspector_for_media,
    soft_inspector_for_region,
    soft_media_list_label,
    soft_person_label,
    soft_progress_clock,
    soft_sel_item_label,
)


def test_soft_media_list_has_no_path_or_uuid():
    label = soft_media_list_label(
        {"path": r"L:\LIBRARY\GOOGLE\takeout\band.jpg", "media_id": "abc123"},
        face_count=3,
    )
    assert "band.jpg" in label
    assert "L:\\" not in label
    assert "faces=" not in label
    assert "abc123" not in label
    assert "3 faces" in label


def test_soft_canvas_status_purpose_line():
    s = soft_canvas_status(
        photo_count=1284, face_count=90, named_people=42, unknown_faces=17
    )
    assert "1284 photos" in s
    assert "42 people" in s
    assert "17 unknown" in s
    assert "elapsed" not in s
    assert "run=" not in s


def test_soft_progress_clock_is_counts_only():
    assert soft_progress_clock(files_processed=734, files_total=1284) == "734 of 1284"
    assert soft_progress_clock(files_processed=None, files_total=10) == ""
    assert "elapsed" not in soft_progress_clock(files_processed=1, files_total=2)


def test_soft_sel_item_never_uuid():
    assert soft_sel_item_label({"kind": "face", "face_id": "5f149d08831c"}) == "Unknown person"
    assert "5f149d" not in soft_sel_item_label(
        {"kind": "cluster", "cluster_id": "deadbeef", "face_count": 4}
    )
    assert soft_sel_item_label(
        {"kind": "face", "person_id": "p1", "display_name": "Sarah"}
    ) == "Sarah"


def test_soft_person_and_face_inspector_uncertainty():
    board = {
        "persons": [{"person_id": "p1", "display_name": "Sarah"}],
        "faces": [
            {"face_id": "f1", "person_id": "p1", "media_id": "m1"},
            {"face_id": "f2", "person_id": "p1", "media_id": "m2"},
            {"face_id": "f3", "person_id": None, "media_id": "m1"},
        ],
    }
    assert soft_person_label(board["faces"][0], board=board) == "Sarah"
    named = soft_inspector_for_face(board["faces"][0], board)
    text = "\n".join(named)
    assert "Sarah" in text
    assert "Possible match" in text
    assert "not confirmed" in text.lower()
    assert "Seen in 2 photos" in text
    assert "person_id" not in text
    assert "5f149d" not in text

    unknown = soft_inspector_for_face(board["faces"][2], board)
    ut = "\n".join(unknown)
    assert "Unknown person" in ut
    assert "Not confirmed" in ut
    assert "Name them" in ut


def test_soft_inspector_for_media_coaches_explore():
    lines = soft_inspector_for_media({}, None)
    text = "\n".join(lines)
    assert "Open a photo" in text or "Photos" in text
    assert "drag" in text.lower()
    assert "bbox" not in text.lower()
    assert "unassigned" not in text.lower()


def test_region_hits_overlap_only():
    board = {
        "faces": [
            {
                "face_id": "f1",
                "media_id": "m1",
                "bbox_x1": 10,
                "bbox_y1": 10,
                "bbox_x2": 50,
                "bbox_y2": 50,
                "person_id": None,
            }
        ],
        "items": [
            {
                "item_id": "i1",
                "kind": "object",
                "media_id": "m1",
                "bbox_x1": 100,
                "bbox_y1": 100,
                "bbox_x2": 140,
                "bbox_y2": 140,
            }
        ],
        "persons": [],
    }
    hits = region_hits(board, "m1", x1=0, y1=0, x2=60, y2=60)
    assert len(hits) == 1
    assert hits[0]["kind"] == "face"
    miss = region_hits(board, "m1", x1=200, y1=200, x2=220, y2=220)
    assert miss == []
    empty_lines = soft_inspector_for_region([], empty=True)
    assert "Nothing found" in empty_lines[0]


def test_verb_labels_are_soft():
    assert VERB_LABEL_MERGE == "Combine face groups"
    assert VERB_LABEL_ASSIGN == "Add to person"
    assert VERB_LABEL_NAME == "Name this person"
    assert "observation" not in VERB_LABEL_MERGE.lower()
    assert "Merge" not in VERB_LABEL_MERGE
