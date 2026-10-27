"""Measure the current greedy IoU tracker. Does not replace it.

Synthetic rows use labelled boxes and the product associator.
A video row decodes with OpenCV, samples near 1 Hz, and detects with YuNet
at the product score / NMS / top-k. YuNet here is a measurement detector:
SFace is not run, nothing is written, and no person is created.

OpenCV 5.0 (the pinned build) has no CascadeClassifier and no HOG people
detector. This tool does not pretend those APIs exist.

    python tools/measure_track_fragmentation.py --video PATH --yunet MODEL --out results.json
    python tools/measure_track_fragmentation.py --synthetic-only --out results.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from semblon.identity_config import DET_SCORE_MIN, NMS_THRESHOLD, TOP_K
from semblon.track_fragmentation import measure_detections, synthetic_reports
from semblon.tracks import DEFAULT_IOU_MIN, DEFAULT_MAX_T_MS_GAP


class _Yunet:
    def __init__(self, model: Path):
        self.model = model
        self._det = None
        self._size: tuple[int, int] | None = None

    def __call__(self, frame):
        import cv2

        height, width = frame.shape[:2]
        if self._det is None:
            self._det = cv2.FaceDetectorYN.create(
                str(self.model),
                "",
                (width, height),
                float(DET_SCORE_MIN),
                float(NMS_THRESHOLD),
                int(TOP_K),
            )
            self._size = (width, height)
        elif self._size != (width, height):
            self._det.setInputSize((width, height))
            self._size = (width, height)
        _retval, faces = self._det.detect(frame)
        if faces is None:
            return []
        boxes = []
        for row in faces:
            x, y, bw, bh = (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
            boxes.append((x, y, x + bw, y + bh))
        return boxes


def measure_video(
    path: Path,
    *,
    yunet: Path,
    sample_hz: float = 1.0,
    max_frames: int | None = None,
) -> dict:
    """Decode + YuNet + associate. Identity embeddings are not computed."""
    import cv2

    detect = _Yunet(yunet)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 1.0:
        fps = 25.0
    step = max(1, int(round(fps / float(sample_hz))))
    detections: list[dict] = []
    decoded = 0
    sampled = 0
    decode_s = 0.0
    detect_s = 0.0
    index = 0
    try:
        while True:
            if max_frames is not None and sampled >= max_frames:
                break
            t0 = time.perf_counter()
            ok, frame = cap.read()
            decode_s += time.perf_counter() - t0
            if not ok or frame is None:
                break
            decoded += 1
            if (decoded - 1) % step != 0:
                continue
            t1 = time.perf_counter()
            boxes = detect(frame)
            detect_s += time.perf_counter() - t1
            t_ms = int(round((decoded - 1) * 1000.0 / fps))
            for bbox in boxes:
                detections.append(
                    {
                        "t_ms": t_ms,
                        "frame_id": sampled,
                        "bbox": bbox,
                        "face_id": f"d{index:06d}",
                    }
                )
                index += 1
            sampled += 1
    finally:
        cap.release()

    t_assoc = time.perf_counter()
    report = measure_detections(
        detections,
        media_id=path.stem,
        frames_sampled=sampled,
    )
    assoc_s = time.perf_counter() - t_assoc
    report.update(
        {
            "source": path.name,
            "detector": "yunet",
            "detector_score_min": float(DET_SCORE_MIN),
            "detector_nms": float(NMS_THRESHOLD),
            "detector_is_identity_engine": False,
            "embeddings_computed": False,
            "sample_hz": float(sample_hz),
            "native_fps": round(fps, 3),
            "sample_step_frames": step,
            "frames_decoded": decoded,
            "timing_s": {
                "decode": round(decode_s, 4),
                "detect": round(detect_s, 4),
                "associate": round(assoc_s, 4),
                "embed": None,
                "ui": None,
                "storage": None,
            },
            "effective_sample_hz": round(sampled / (decoded / fps), 3) if decoded else None,
        }
    )
    return report


def build_record(
    *,
    videos: list[tuple[Path, Path]],
    max_frames: int | None,
    sample_hz: float,
) -> dict:
    measured = []
    for path, model in videos:
        measured.append(
            measure_video(path, yunet=model, max_frames=max_frames, sample_hz=sample_hz)
        )
    return {
        "tool": "measure_track_fragmentation",
        "tracker_replaced": False,
        "constants": {"iou_min": DEFAULT_IOU_MIN, "max_t_ms_gap": DEFAULT_MAX_T_MS_GAP},
        "opencv_note": (
            "Pinned opencv 5.0 has FaceDetectorYN. It does not expose "
            "CascadeClassifier or HOGDescriptor. Those were not used."
        ),
        "synthetic": synthetic_reports(),
        "videos": measured,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, action="append", default=[])
    parser.add_argument("--yunet", type=Path, default=None)
    parser.add_argument("--sample-hz", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.synthetic_only and not args.video:
        parser.error("pass --video or --synthetic-only")
    if args.video and args.yunet is None:
        parser.error("--video requires --yunet MODEL (local file; this tool does not download)")
    pairs = [] if args.synthetic_only else [(path, args.yunet) for path in args.video]
    record = build_record(videos=pairs, max_frames=args.max_frames, sample_hz=args.sample_hz)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    brief = []
    for row in record["videos"]:
        brief.append(
            {
                "source": row["source"],
                "detections": row["detections"],
                "tracks": row["tracks"],
                "singletons": row["singletons"],
                "peak": row["peak_simultaneous"],
                "short": row["short_lived_tracks"],
                "ratio": row["tracks_per_peak_simultaneous"],
            }
        )
    print(json.dumps({"out": str(args.out), "videos": brief}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
