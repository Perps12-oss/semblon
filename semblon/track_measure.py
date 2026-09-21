"""Measure greedy IoU tracker fragmentation on video (or synthetic frames).

Does not replace the tracker. Does not touch identity. Evidence only.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Callable

from semblon.tracks import DEFAULT_IOU_MIN, DEFAULT_MAX_T_MS_GAP, _associate_media, bbox_iou


class TrackMeasureError(ValueError):
    pass


DetectFn = Callable[[object, int], list[dict]]


def _durations_ms(tracks: list[list[dict]]) -> list[int]:
    out: list[int] = []
    for members in tracks:
        ts = [m["t_ms"] for m in members if m.get("t_ms") is not None]
        if not ts:
            out.append(0)
            continue
        out.append(int(max(ts) - min(ts)))
    return out


def summarize_association(
    detections: list[dict],
    *,
    iou_min: float = DEFAULT_IOU_MIN,
    max_t_ms_gap: int = DEFAULT_MAX_T_MS_GAP,
    short_track_obs: int = 2,
) -> dict:
    """Fragmentation stats for one media's detection stream."""
    tracks, singles = _associate_media(
        detections,
        iou_min=iou_min,
        max_t_ms_gap=max_t_ms_gap,
    )
    all_tracks = list(tracks) + [[s] for s in singles]
    n_det = len(detections)
    n_tracks = len(all_tracks)
    obs_per = [len(t) for t in all_tracks]
    durs = _durations_ms(all_tracks)
    short = sum(1 for n in obs_per if n <= short_track_obs)
    # Fragmentation index: tracks per detection (1.0 = every det is its own track).
    frag = (float(n_tracks) / float(n_det)) if n_det else 0.0
    frames: dict[int, list[dict]] = {}
    for d in detections:
        frames.setdefault(int(d.get("frame_id") or 0), []).append(d)
    multi_face_frames = sum(1 for v in frames.values() if len(v) >= 2)
    zero_face_frames = sum(1 for v in frames.values() if len(v) == 0)
    # Missed association heuristic: consecutive-frame boxes with IoU>=min but different tracks.
    missed = 0
    false_assoc = 0
    mapping: dict[str, str] = {}
    for tr in all_tracks:
        key = tr[0]["face_id"]
        for m in tr:
            mapping[m["face_id"]] = key
    by_frame = sorted(frames.items())
    for i in range(1, len(by_frame)):
        prev_f, prev = by_frame[i - 1]
        cur_f, cur = by_frame[i]
        _ = prev_f, cur_f
        used_prev: set[str] = set()
        for c in cur:
            best = None
            best_iou = -1.0
            for p in prev:
                if p["face_id"] in used_prev:
                    continue
                iou = bbox_iou(c["bbox"], p["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best = p
            if best is None:
                continue
            if best_iou < iou_min:
                continue
            used_prev.add(best["face_id"])
            same = mapping.get(c["face_id"]) == mapping.get(best["face_id"])
            if not same and best_iou >= iou_min:
                missed += 1
            # False assoc: linked but IoU was weak relative to another candidate — rare in greedy.
            if same and best_iou < iou_min:
                false_assoc += 1
    return {
        "detections": n_det,
        "frames_with_detections": len(frames),
        "multi_face_frames": multi_face_frames,
        "zero_face_listed_frames": zero_face_frames,
        "tracks": n_tracks,
        "singles": len(singles),
        "obs_per_track": obs_per,
        "obs_per_track_mean": round(statistics.mean(obs_per), 3) if obs_per else 0.0,
        "obs_per_track_median": float(statistics.median(obs_per)) if obs_per else 0.0,
        "track_duration_ms": durs,
        "track_duration_ms_mean": round(statistics.mean(durs), 1) if durs else 0.0,
        "track_duration_ms_median": float(statistics.median(durs)) if durs else 0.0,
        "short_lived_tracks": short,
        "fragmentation_index": round(frag, 4),
        "missed_associations_heuristic": missed,
        "false_associations_heuristic": false_assoc,
        "iou_min": float(iou_min),
        "max_t_ms_gap": int(max_t_ms_gap),
    }


def measure_video_fragmentation(
    path: Path,
    *,
    detect: DetectFn | None = None,
    sample_hz: float = 5.0,
    max_frames: int | None = 300,
    iou_min: float = DEFAULT_IOU_MIN,
    max_t_ms_gap: int = DEFAULT_MAX_T_MS_GAP,
) -> dict:
    """Decode ``path``, run ``detect`` (or empty), associate, summarize.

    ``detect(frame_bgr, frame_index) -> list[{bbox, det_score?}]``.
    """
    import cv2

    path = Path(path)
    if not path.is_file():
        raise TrackMeasureError(f"video not found: {path}")
    if sample_hz <= 0:
        raise TrackMeasureError("sample_hz must be > 0")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise TrackMeasureError(f"cannot open video: {path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 25.0
    interval = max(1, int(round(fps / float(sample_hz))))
    detections: list[dict] = []
    frames_seen = 0
    samples = 0
    people_enter_leave = {"max_simultaneous": 0, "sample_face_counts": []}
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if frames_seen % interval != 0:
                frames_seen += 1
                continue
            t_ms = int(round((frames_seen / fps) * 1000.0))
            raw = detect(frame, samples) if detect is not None else []
            people_enter_leave["sample_face_counts"].append(len(raw))
            people_enter_leave["max_simultaneous"] = max(
                people_enter_leave["max_simultaneous"], len(raw)
            )
            for j, det in enumerate(raw):
                bbox = det.get("bbox")
                if bbox is None or len(bbox) < 4:
                    continue
                det_id = f"v-{samples}-{j}"
                detections.append(
                    {
                        "face_id": det_id,
                        "det_id": det_id,
                        "observation_id": f"o-{samples}",
                        "media_id": "measure",
                        "path": str(path),
                        "frame_id": samples,
                        "t_ms": t_ms,
                        "bbox": tuple(float(v) for v in bbox[:4]),
                        "face_w": int(max(0, round(bbox[2] - bbox[0]))),
                        "face_h": int(max(0, round(bbox[3] - bbox[1]))),
                        "person_id": None,
                        "cluster_id": None,
                    }
                )
            samples += 1
            frames_seen += 1
            if max_frames is not None and samples >= int(max_frames):
                break
    finally:
        cap.release()

    summary = summarize_association(
        detections, iou_min=iou_min, max_t_ms_gap=max_t_ms_gap
    )
    counts = people_enter_leave["sample_face_counts"]
    enters = leaves = 0
    for i in range(1, len(counts)):
        delta = counts[i] - counts[i - 1]
        if delta > 0:
            enters += delta
        elif delta < 0:
            leaves += -delta
    summary.update(
        {
            "video": str(path),
            "fps": fps,
            "sample_hz": float(sample_hz),
            "samples": samples,
            "frames_decoded": frames_seen,
            "max_simultaneous_faces": people_enter_leave["max_simultaneous"],
            "people_enter_events": enters,
            "people_leave_events": leaves,
            "detector": "provided" if detect is not None else "none",
        }
    )
    return summary


def write_report(summary: dict, out: Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
