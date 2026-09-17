"""S7a: video files as temporal sources. Sampled frames, not a JPEG storm.

Not S7b tracking. Not webcam/RTSP. Time does not change compare().
"""

from __future__ import annotations

from pathlib import Path

import cv2

VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
DEFAULT_SAMPLE_HZ = 1.0


class VideoError(ValueError):
    pass


def discover_videos(folder: Path) -> list[Path]:
    """Sorted video paths under folder. Disjoint from still extensions."""
    folder = Path(folder)
    return sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT
    )


def sample_frame_indices(
    n_frames: int,
    fps: float,
    sample_hz: float = DEFAULT_SAMPLE_HZ,
) -> list[int]:
    """Evenly spaced frame indices at sample_hz. Never every native frame."""
    if n_frames <= 0:
        return []
    if sample_hz <= 0:
        raise VideoError("sample_hz must be > 0")
    if fps is None or fps <= 0:
        fps = 25.0
    step = max(1, int(round(fps / sample_hz)))
    return list(range(0, n_frames, step))


def frame_t_ms(frame_idx: int, fps: float) -> int:
    if fps is None or fps <= 0:
        fps = 25.0
    return int(round(frame_idx / fps * 1000.0))


def iter_sampled_frames(path: Path, sample_hz: float = DEFAULT_SAMPLE_HZ):
    """Yield (frame_idx, t_ms, bgr) for sampled frames. Does not write JPEGs."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoError(f"cannot open video: {path}")
    try:
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        indices = sample_frame_indices(n_frames, fps, sample_hz)
        if not indices:
            return
        want = set(indices)
        max_i = indices[-1]
        idx = 0
        while idx <= max_i:
            if idx in want:
                ok, img = cap.read()
                if not ok or img is None:
                    break
                yield idx, frame_t_ms(idx, fps), img
            else:
                if not cap.grab():
                    break
            idx += 1
    finally:
        cap.release()
