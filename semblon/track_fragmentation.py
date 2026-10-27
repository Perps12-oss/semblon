"""Measure greedy IoU track fragmentation. Does not change the tracker.

The associator is ``tracks._associate_media``. Embeddings are not read.
A track is still not a person. This module does not write the store and
does not create persons.
"""

from __future__ import annotations

from semblon.tracks import (
    DEFAULT_IOU_MIN,
    DEFAULT_MAX_T_MS_GAP,
    _associate_media,
    bbox_iou,
)

# A track whose span is at most one sample step, or that holds only the
# minimum two observations, is short-lived. Singletons are counted apart.
SHORT_TRACK_MAX_MS = 1000


def _face_from_detection(det: dict, index: int, media_id: str) -> dict:
    bbox = tuple(float(v) for v in det["bbox"][:4])
    x1, y1, x2, y2 = bbox
    t_ms = det.get("t_ms")
    frame_id = det.get("frame_id")
    return {
        "face_id": str(det.get("face_id") or f"f{index:06d}"),
        "observation_id": str(det.get("observation_id") or f"o{index:06d}"),
        "media_id": media_id,
        "path": str(det.get("path") or ""),
        "frame_id": None if frame_id is None else int(frame_id),
        "t_ms": None if t_ms is None else int(t_ms),
        "bbox": bbox,
        "face_w": int(round(x2 - x1)),
        "face_h": int(round(y2 - y1)),
        "person_id": None,
        "cluster_id": None,
        "label": det.get("label"),
    }


def _duration_ms(members: list[dict]) -> int | None:
    times = [m["t_ms"] for m in members if m["t_ms"] is not None]
    if len(times) < 2:
        return None
    return int(max(times) - min(times))


def _percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return int(ordered[0])
    rank = (len(ordered) - 1) * (p / 100.0)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return int(round(ordered[lo] * (1.0 - frac) + ordered[hi] * frac))


def _below_iou_within_gap(
    faces: list[dict],
    *,
    iou_min: float,
    max_t_ms_gap: int,
) -> int:
    """New chains whose best in-window box was real but under the IoU gate.

    This is an observable split, not a proven missed identity. Same-frame
    boxes are ignored: one frame never shares a track.
    """
    ordered = sorted(
        faces,
        key=lambda f: (
            f["t_ms"] is None,
            f["t_ms"] if f["t_ms"] is not None else 0,
            f["face_id"],
        ),
    )
    chains: list[dict] = []
    splits = 0
    for face in ordered:
        ft = face["t_ms"]
        best = -1.0
        best_any = -1.0
        joined = False
        if ft is not None:
            for chain in chains:
                lt = chain["t_ms"]
                if lt is None or ft <= lt or ft - lt > max_t_ms_gap:
                    continue
                iou = bbox_iou(face["bbox"], chain["bbox"])
                if iou > best_any:
                    best_any = iou
                if iou >= iou_min and iou > best:
                    best = iou
                    joined = True
        if joined:
            # Mirror greedy: update the winning chain only. Recompute winner.
            winner = None
            winner_iou = -1.0
            for chain in chains:
                lt = chain["t_ms"]
                if lt is None or ft is None or ft <= lt or ft - lt > max_t_ms_gap:
                    continue
                iou = bbox_iou(face["bbox"], chain["bbox"])
                if iou >= iou_min and iou > winner_iou:
                    winner_iou = iou
                    winner = chain
            if winner is not None:
                winner["t_ms"] = ft
                winner["bbox"] = face["bbox"]
            continue
        if best_any >= 0.0:
            splits += 1
        chains.append({"t_ms": ft, "bbox": face["bbox"]})
    return splits


def _order_reversals(points_by_t: dict[int, list[tuple[str, float]]]) -> int:
    """Count pairwise left/right flips between successive timestamps."""
    times = sorted(points_by_t)
    prev: dict[tuple[str, str], bool] = {}
    flips = 0
    for t in times:
        present = {key: cx for key, cx in points_by_t[t]}
        ids = sorted(present)
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                a_left = present[a] < present[b]
                key = (a, b)
                if key in prev and prev[key] != a_left:
                    flips += 1
                prev[key] = a_left
    return flips


def _observed_crossings(tracks: list[list[dict]]) -> int:
    """Times two tracks reverse horizontal order between shared timestamps."""
    by_t: dict[int, list[tuple[str, float]]] = {}
    for ti, members in enumerate(tracks):
        for m in members:
            if m["t_ms"] is None:
                continue
            x1, _, x2, _ = m["bbox"]
            by_t.setdefault(int(m["t_ms"]), []).append((str(ti), (float(x1) + float(x2)) / 2.0))
    return _order_reversals(by_t)


def _label_order_reversals(faces: list[dict]) -> int | None:
    """Ground-truth label crossings. None when labels are absent."""
    if not any(face.get("label") is not None for face in faces):
        return None
    by_t: dict[int, list[tuple[str, float]]] = {}
    for face in faces:
        if face.get("label") is None or face["t_ms"] is None:
            continue
        x1, _, x2, _ = face["bbox"]
        by_t.setdefault(int(face["t_ms"]), []).append(
            (str(face["label"]), (float(x1) + float(x2)) / 2.0)
        )
    return _order_reversals(by_t)


def measure_detections(
    detections: list[dict],
    *,
    media_id: str = "m-measure",
    iou_min: float = DEFAULT_IOU_MIN,
    max_t_ms_gap: int = DEFAULT_MAX_T_MS_GAP,
    frames_sampled: int | None = None,
) -> dict:
    """Run the current associator and summarise fragmentation.

    Optional ``label`` on a detection is ground truth for purity only.
    It is stripped before association. Missing labels leave identity-error
    fields null rather than inventing them.
    """
    faces = [
        _face_from_detection(det, i, media_id) for i, det in enumerate(detections or [])
    ]
    clean = [{k: v for k, v in face.items() if k != "label"} for face in faces]
    tracks, singles = _associate_media(
        clean, iou_min=float(iou_min), max_t_ms_gap=int(max_t_ms_gap)
    )
    labels = {face["face_id"]: face.get("label") for face in faces}
    has_labels = any(label is not None for label in labels.values())

    durations: list[int] = []
    obs_counts: list[int] = []
    short = 0
    impure = 0
    label_parts: dict[str, int] = {}
    for members in tracks:
        obs_counts.append(len(members))
        span = _duration_ms(members)
        if span is not None:
            durations.append(span)
        if span is None or span <= SHORT_TRACK_MAX_MS or len(members) <= 2:
            short += 1
        if has_labels:
            seen = {labels.get(m["face_id"]) for m in members}
            seen.discard(None)
            if len(seen) > 1:
                impure += 1
            for label in seen:
                label_parts[str(label)] = label_parts.get(str(label), 0) + 1
    if has_labels:
        for single in singles:
            label = labels.get(single["face_id"])
            if label is not None:
                label_parts[str(label)] = label_parts.get(str(label), 0) + 1

    per_frame: dict[int, int] = {}
    for face in faces:
        if face["t_ms"] is None:
            continue
        per_frame[int(face["t_ms"])] = per_frame.get(int(face["t_ms"]), 0) + 1
    peak = max(per_frame.values()) if per_frame else 0
    n_tracks = len(tracks)
    ratio = None
    if peak > 0:
        ratio = round(n_tracks / float(peak), 3)

    fragments_per_label = None
    if has_labels and label_parts:
        fragments_per_label = {
            key: label_parts[key] for key in sorted(label_parts)
        }

    return {
        "associator": "greedy-iou",
        "iou_min": float(iou_min),
        "max_t_ms_gap": int(max_t_ms_gap),
        "embeddings_vote": False,
        "detections": len(faces),
        "frames_with_detections": len(per_frame),
        "frames_sampled": frames_sampled,
        "peak_simultaneous": peak,
        "tracks": n_tracks,
        "singletons": len(singles),
        "observations_per_track": {
            "min": min(obs_counts) if obs_counts else None,
            "max": max(obs_counts) if obs_counts else None,
            "mean": round(sum(obs_counts) / len(obs_counts), 3) if obs_counts else None,
        },
        "duration_ms": {
            "min": min(durations) if durations else None,
            "p50": _percentile(durations, 50),
            "p90": _percentile(durations, 90),
            "max": max(durations) if durations else None,
        },
        "short_lived_tracks": short,
        "tracks_per_peak_simultaneous": ratio,
        "below_iou_within_gap": _below_iou_within_gap(
            clean, iou_min=float(iou_min), max_t_ms_gap=int(max_t_ms_gap)
        ),
        "observed_crossings": _observed_crossings(tracks),
        "label_order_reversals": _label_order_reversals(faces),
        "labels_present": has_labels,
        "impure_tracks": impure if has_labels else None,
        "fragments_per_label": fragments_per_label,
        "false_associations": impure if has_labels else None,
        "note": (
            "Track is not a person. impure_tracks counts chains whose ground-truth "
            "labels disagree. Without labels that field is null."
        ),
    }


def synthetic_reports() -> dict[str, dict]:
    """Deterministic geometries. Labels are ground truth, not identity writes."""

    def box(x: float, y: float, w: float = 80.0, h: float = 80.0) -> tuple:
        return (x, y, x + w, y + h)

    def row(i: int, bbox, label: str, *, step_ms: int = 1000) -> dict:
        return {"t_ms": i * step_ms, "frame_id": i, "bbox": bbox, "label": label}

    continuation = [row(i, box(10 + i * 4, 20), "a") for i in range(8)]
    separated: list[dict] = []
    for i in range(6):
        separated.append(row(i, box(10, 10, 70, 70), "a"))
        separated.append(row(i, box(400, 30, 70, 70), "b"))
        separated.append(row(i, box(220, 200, 70, 70), "c"))
    gap = [row(i, box(30, 30), "a") for i in range(3)]
    gap += [row(i, box(36, 30), "a") for i in range(6, 9)]
    missed = [row(i, box(15 + i * 3, 15), "a") for i in (0, 1, 3, 4)]
    fast = [
        row(0, box(0, 0), "a"),
        row(0, box(200, 0), "b"),
        row(1, box(200, 0), "a"),
        row(1, box(0, 0), "b"),
    ]
    slow: list[dict] = []
    for i in range(12):
        slow.append(row(i, box(20 + i * 12, 40), "a"))
        slow.append(row(i, box(220 - i * 12, 40), "b"))
    fast_motion = [
        row(0, box(0, 40), "a"),
        row(1, box(8, 40), "a"),
        row(2, box(220, 40), "a"),
        row(3, box(228, 40), "a"),
    ]
    empty: list[dict] = []
    one = [row(0, box(10, 10), "a")]
    return {
        "zero": measure_detections(empty),
        "one_detection_not_a_track": measure_detections(one),
        "continuation": measure_detections(continuation),
        "three_separated": measure_detections(separated),
        "temporal_gap": measure_detections(gap),
        "missed_sample_within_window": measure_detections(missed),
        "fast_motion_split": measure_detections(fast_motion),
        "fast_position_swap": measure_detections(fast),
        "slow_cross": measure_detections(slow),
    }
