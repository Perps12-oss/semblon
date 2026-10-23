"""S7a: video files as temporal sources. Sampled frames, not a JPEG storm.

Not S7b tracking. Not webcam/RTSP. Time does not change compare().
"""

from __future__ import annotations

import os
import shutil
import tempfile
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


def _decode_still(path: Path):
    """Bytes then imdecode. imread misses Unicode and long Windows paths."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data:
        return None
    import numpy as np

    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


_MAX_COUNTED_FRAMES = 250_000


class _Capture:
    """VideoCapture plus an optional ASCII temp path used when the real path will not open."""

    def __init__(self, cap, cleanup: Path | None = None):
        self._cap = cap
        self._cleanup = cleanup

    def isOpened(self) -> bool:
        return bool(self._cap is not None and self._cap.isOpened())

    def read(self):
        return self._cap.read()

    def grab(self) -> bool:
        return bool(self._cap.grab())

    def get(self, prop):
        return self._cap.get(prop)

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
        if self._cleanup is not None:
            try:
                self._cleanup.unlink()
            except OSError:
                pass
            self._cleanup = None


def _extended_prefix(resolved: str) -> str:
    """Long-path form of an already-resolved Windows path. Pure string logic."""
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


def _extended_win_path(path: Path) -> str | None:
    if os.name != "nt":
        return None
    return _extended_prefix(str(path.resolve()))


def _ascii_temp_copy(path: Path) -> Path | None:
    suffix = path.suffix if path.suffix.isascii() else ".bin"
    fd, name = tempfile.mkstemp(prefix="semblon-vid-", suffix=suffix)
    os.close(fd)
    dest = Path(name)
    try:
        dest.unlink()
        os.link(path, dest)
        return dest
    except OSError:
        try:
            shutil.copyfile(path, dest)
            return dest
        except OSError:
            try:
                dest.unlink()
            except OSError:
                pass
            return None


def open_video(path: Path | str) -> _Capture:
    """Open a video. Windows Unicode and long paths are not left to cv2.VideoCapture alone."""
    path = Path(path)
    attempts = [str(path)]
    extended = _extended_win_path(path)
    if extended and extended not in attempts:
        attempts.append(extended)
    for candidate in attempts:
        cap = cv2.VideoCapture(candidate)
        if cap.isOpened():
            return _Capture(cap)
        cap.release()
    cleanup = _ascii_temp_copy(path)
    if cleanup is None:
        return _Capture(cv2.VideoCapture())
    cap = cv2.VideoCapture(str(cleanup))
    if cap.isOpened():
        return _Capture(cap, cleanup)
    cap.release()
    try:
        cleanup.unlink()
    except OSError:
        pass
    return _Capture(cv2.VideoCapture())


def read_bgr(path: Path | str, frame_id: int | None = None):
    """Load one BGR frame for review/export thumbs.

    Stills: bytes first, then ``cv2.imread`` if that cannot decode.
    Video: grab sequentially to ``frame_id``. Frame-number seek is not used.
    Does not write crops to disk.
    """
    path = Path(path)
    if frame_id is None:
        img = _decode_still(path)
        if img is not None:
            return img
        return cv2.imread(str(path))
    cap = open_video(path)
    if not cap.isOpened():
        return None
    try:
        target = int(frame_id)
        if target < 0:
            return None
        for _ in range(target):
            if not cap.grab():
                return None
        ok, img = cap.read()
        if not ok or img is None:
            return None
        return img
    finally:
        cap.release()


def _sample_unknown_length(cap: _Capture, fps: float, sample_hz: float, path: Path):
    if sample_hz <= 0:
        raise VideoError("sample_hz must be > 0")
    if fps is None or fps <= 0:
        fps = 25.0
    step = max(1, int(round(fps / sample_hz)))
    idx = 0
    yielded = 0
    while idx < _MAX_COUNTED_FRAMES:
        if idx % step == 0:
            ok, img = cap.read()
            if not ok or img is None:
                break
            yielded += 1
            yield idx, frame_t_ms(idx, fps), img
        elif not cap.grab():
            break
        idx += 1
    if yielded == 0:
        raise VideoError(f"video reported no frames: {path}")


def iter_sampled_frames(path: Path, sample_hz: float = DEFAULT_SAMPLE_HZ):
    """Yield (frame_idx, t_ms, bgr) for sampled frames. Does not write JPEGs."""
    cap = open_video(path)
    if not cap.isOpened():
        raise VideoError(f"cannot open video: {path}")
    try:
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if n_frames <= 0:
            yield from _sample_unknown_length(cap, fps, sample_hz, path)
            return
        indices = sample_frame_indices(n_frames, fps, sample_hz)
        if not indices:
            raise VideoError(f"video reported no frames: {path}")
        want = set(indices)
        max_i = indices[-1]
        idx = 0
        yielded = 0
        while idx <= max_i:
            if idx in want:
                ok, img = cap.read()
                if not ok or img is None:
                    break
                yielded += 1
                yield idx, frame_t_ms(idx, fps), img
            else:
                if not cap.grab():
                    break
            idx += 1
        if yielded == 0:
            raise VideoError(f"video reported no frames: {path}")
    finally:
        cap.release()
