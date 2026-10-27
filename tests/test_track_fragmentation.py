"""Fragmentation of the current greedy tracker. The tracker is not replaced."""

from __future__ import annotations

from semblon.track_fragmentation import measure_detections, synthetic_reports


def test_zero_detections_are_not_tracks():
    report = measure_detections([])
    assert report["detections"] == 0
    assert report["tracks"] == 0
    assert report["singletons"] == 0
    assert report["false_associations"] is None
    assert report["embeddings_vote"] is False


def test_one_detection_is_not_a_track():
    report = synthetic_reports()["one_detection_not_a_track"]
    assert report["detections"] == 1
    assert report["tracks"] == 0
    assert report["singletons"] == 1


def test_continuation_is_one_pure_track():
    report = synthetic_reports()["continuation"]
    assert report["tracks"] == 1
    assert report["singletons"] == 0
    assert report["impure_tracks"] == 0
    assert report["fragments_per_label"] == {"a": 1}
    assert report["observations_per_track"]["min"] == 8


def test_three_separated_people_stay_independent():
    report = synthetic_reports()["three_separated"]
    assert report["peak_simultaneous"] == 3
    assert report["tracks"] == 3
    assert report["singletons"] == 0
    assert report["impure_tracks"] == 0
    assert report["fragments_per_label"] == {"a": 1, "b": 1, "c": 1}
    assert report["false_associations"] == 0


def test_temporal_gap_fragments_without_merging():
    report = synthetic_reports()["temporal_gap"]
    assert report["fragments_per_label"] == {"a": 2}
    assert report["impure_tracks"] == 0
    assert report["tracks"] == 2


def test_one_missed_sample_inside_the_window_continues():
    report = synthetic_reports()["missed_sample_within_window"]
    assert report["tracks"] == 1
    assert report["fragments_per_label"] == {"a": 1}
    assert report["impure_tracks"] == 0


def test_fast_position_swap_false_associates_without_track_crossing():
    """Boxes swap owners. Tracks follow the boxes, so track centres do not cross."""
    report = synthetic_reports()["fast_position_swap"]
    assert report["tracks"] == 2
    assert report["impure_tracks"] == 2
    assert report["false_associations"] == 2
    assert report["fragments_per_label"] == {"a": 2, "b": 2}
    assert report["label_order_reversals"] == 1
    assert report["observed_crossings"] == 0


def test_slow_cross_still_swaps_when_boxes_overlap_more_than_motion():
    """12 px/s approach. At the pass, the other last-box outscores own last-box."""
    report = synthetic_reports()["slow_cross"]
    assert report["tracks"] == 2
    assert report["impure_tracks"] == 2
    assert report["fragments_per_label"] == {"a": 2, "b": 2}
    assert report["label_order_reversals"] >= 1
    assert report["observed_crossings"] == 0


def test_fast_motion_inside_the_time_gate_splits_on_iou():
    report = synthetic_reports()["fast_motion_split"]
    assert report["fragments_per_label"] == {"a": 2}
    assert report["impure_tracks"] == 0
    assert report["below_iou_within_gap"] >= 1
    assert report["tracks"] == 2


def test_labels_absent_does_not_invent_false_associations():
    dets = [
        {"t_ms": 0, "frame_id": 0, "bbox": (0, 0, 40, 40)},
        {"t_ms": 1000, "frame_id": 1, "bbox": (2, 0, 42, 40)},
    ]
    report = measure_detections(dets)
    assert report["labels_present"] is False
    assert report["false_associations"] is None
    assert report["impure_tracks"] is None
    assert report["tracks"] == 1
