"""C3 — 4K/60 scrub frame time (< 16 ms).

Can ingest a human-supplied frame-time log (one float ms per line) and compute stats.
Does not invent PASS; leaves pass null even when stats are computed.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

MAX_FRAME_MS = 16.0

HUMAN_STEPS = [
    "Prepare a 3840×2160 (or higher) source, ideally 60 fps, on the owner Windows machine.",
    "In the candidate toolkit scrubber/preview, scrub continuously for ≥ 10 s at interactive speed.",
    "Capture per-frame present times (PIX, PresentMon, Qt QElapsedTimer log, or WinUI Composition timings).",
    "Write one frame duration in milliseconds per line to a UTF-8 text file (e.g. results/evidence/<toolkit>/c3/frametimes_ms.txt).",
    "Re-run: py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit <name> --frametimes <path-to-txt>",
    "Review measurements.p95_ms / max_ms against threshold 16.0. Human sets pass true only if scrub stays under 16 ms (p95 and visual jank-free).",
    "Do not mark PASS from average alone if spikes are visible.",
]


def _load_frametimes(path: Path) -> list[float]:
    values: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        values.append(float(s))
    if not values:
        raise ValueError(f"no frame times in {path}")
    return values


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    path_str = ctx.get("frametimes_path")
    if not path_str:
        detail = (
            "No --frametimes path supplied. Auto-measure needs a present-time log from a real scrub session."
        )
        return {
            "status": "pending_human",
            "pass": None,
            "measurements": {
                "max_frame_ms_threshold": MAX_FRAME_MS,
                "sample_count": 0,
            },
            "notes": detail,
            "human_steps": list(HUMAN_STEPS),
            "probe": {
                "name": "c3_scrub_frametime",
                "attempted": True,
                "auto_capable": True,
                "detail": detail,
            },
        }

    path = Path(path_str)
    try:
        samples = _load_frametimes(path)
    except (OSError, ValueError) as exc:
        return {
            "status": "error",
            "pass": None,
            "measurements": {},
            "notes": str(exc),
            "human_steps": list(HUMAN_STEPS),
            "probe": {
                "name": "c3_scrub_frametime",
                "attempted": True,
                "auto_capable": True,
                "detail": str(exc),
            },
        }

    ordered = sorted(samples)
    n = len(ordered)
    p95 = ordered[min(n - 1, int(0.95 * (n - 1)))]
    mean = statistics.fmean(samples)
    mx = max(samples)
    under = sum(1 for v in samples if v < MAX_FRAME_MS)
    measurements = {
        "max_frame_ms_threshold": MAX_FRAME_MS,
        "sample_count": n,
        "mean_ms": round(mean, 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(mx, 3),
        "pct_under_16ms": round(100.0 * under / n, 2),
        "source": str(path.resolve()),
    }
    detail = (
        "Frame-time stats computed from supplied log. pass left null — human must confirm "
        "4K/60 scrub context and visual jank before setting pass."
    )
    return {
        "status": "measured",
        "pass": None,
        "measurements": measurements,
        "evidence_path": str(path.resolve()),
        "notes": detail,
        "human_steps": list(HUMAN_STEPS),
        "probe": {
            "name": "c3_scrub_frametime",
            "attempted": True,
            "auto_capable": True,
            "detail": detail,
        },
    }
