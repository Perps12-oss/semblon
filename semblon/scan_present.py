"""Scan card copy from real progress counters.

Percent is files_scanned / total at 1 decimal. Pace is an exponential
moving average (alpha 0.1) of files per second. ETA is remaining / rate.
Nothing here invents a denominator, a percent, or a remaining time.

Pause does not advance this pace. The ingest clock itself is wall time
from the job start (pause sleep is included after resume). The card
shows the last reported elapsed and stops updating while paused because
progress events stop at the file boundary.
"""

from __future__ import annotations

from semblon.progress import ratio_percent

_RUNNING = frozenset({"queued", "started", "progress", "partial", "stalled"})


def format_hms(seconds: float | None) -> str | None:
    """``h:mm:ss``. Hours are not wrapped at 24. None when the input is missing."""
    if seconds is None:
        return None
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return None
    if value < 0 or value != value:
        return None
    whole = int(round(value))
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


class ScanPace:
    """Files-per-second EMA. Alpha 0.1. First sample seeds from files/elapsed."""

    def __init__(self, alpha: float = 0.1) -> None:
        self.alpha = alpha
        self.rate: float | None = None
        self._files: int | None = None
        self._elapsed: float | None = None

    def reset(self) -> None:
        self.rate = None
        self._files = None
        self._elapsed = None

    def observe(self, files: int | None, elapsed_s: float | None) -> None:
        if files is None or elapsed_s is None:
            return
        try:
            files_i = int(files)
            elapsed = float(elapsed_s)
        except (TypeError, ValueError):
            return
        if files_i < 0 or elapsed < 0 or elapsed != elapsed:
            return
        if self._files is None or self._elapsed is None:
            if elapsed > 0 and files_i > 0:
                self.rate = files_i / elapsed
            self._files = files_i
            self._elapsed = elapsed
            return
        delta_files = files_i - self._files
        delta_t = elapsed - self._elapsed
        self._files = files_i
        self._elapsed = elapsed
        if delta_t <= 0 or delta_files < 0:
            return
        instant = delta_files / delta_t
        if self.rate is None:
            self.rate = instant
        else:
            self.rate = self.alpha * instant + (1.0 - self.alpha) * self.rate

    def eta_s(self, files: int | None, total: int | None) -> float | None:
        if self.rate is None or self.rate <= 0 or files is None or total is None:
            return None
        try:
            remaining = int(total) - int(files)
        except (TypeError, ValueError):
            return None
        if remaining <= 0:
            return 0.0
        return remaining / self.rate


def scan_title(*, stage: str | None, kind: str | None, paused: bool) -> str:
    """Scan card title. Deck labels, plus failed/cancelled when those are real."""
    if paused and kind not in {"completed", "failed", "cancelled"}:
        return "Paused"
    if kind == "completed":
        return "Completed"
    if kind == "failed":
        return "Couldn't finish"
    if kind == "cancelled":
        return "Cancelled"
    if stage == "ingest" and (kind in _RUNNING or kind is None):
        return "Reading photos…"
    return "Scanning"


def scan_stats(
    *,
    files_processed: int | None,
    files_total: int | None,
    faces_found: int | None,
) -> str:
    """``{n} of {n} files · {n} faces found``. Omit a part the event does not have."""
    bits: list[str] = []
    done = _as_int(files_processed)
    total = _as_int(files_total)
    if done is not None and total is not None and total >= 0:
        bits.append(f"{done} of {total} files")
    faces = _as_int(faces_found)
    if faces is not None and faces >= 0:
        bits.append(f"{faces} faces found")
    return " · ".join(bits)


def scan_meta(
    *,
    files_processed: int | None,
    files_total: int | None,
    elapsed_s: float | None,
    paused: bool,
    pace: ScanPace | None,
) -> str:
    """Percent, elapsed, and ETA only from real counters. No placeholder ETA."""
    elapsed = format_hms(elapsed_s)
    if paused:
        if elapsed is None:
            return ""
        return f"Elapsed {elapsed} · paused"
    pct = ratio_percent(_as_int(files_processed), _as_int(files_total))
    eta = None
    if pace is not None:
        eta = format_hms(pace.eta_s(files_processed, files_total))
    parts: list[str] = []
    if pct is not None:
        parts.append(f"{pct:.1f}%")
    if elapsed is not None:
        clock = f"Elapsed {elapsed}"
        if eta is not None:
            clock = f"{clock} · ETA {eta}"
        parts.append(clock)
    elif eta is not None:
        parts.append(f"ETA {eta}")
    return ", ".join(parts)


def scan_card(
    *,
    stage: str | None = None,
    kind: str | None = None,
    paused: bool = False,
    files_processed: int | None = None,
    files_total: int | None = None,
    faces_found: int | None = None,
    elapsed_s: float | None = None,
    pace: ScanPace | None = None,
) -> dict[str, str]:
    return {
        "title": scan_title(stage=stage, kind=kind, paused=paused),
        "stats": scan_stats(
            files_processed=files_processed,
            files_total=files_total,
            faces_found=faces_found,
        ),
        "meta": scan_meta(
            files_processed=files_processed,
            files_total=files_total,
            elapsed_s=elapsed_s,
            paused=paused,
            pace=pace,
        ),
    }


def _as_int(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
