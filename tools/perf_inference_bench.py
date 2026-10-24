#!/usr/bin/env python3
"""Benchmark experimental YuNet+SFace backends on a still corpus.

Measures separately: image decoding, YuNet detection, face alignment,
SFace embedding, total. Reports p50 / p95 / mean latency, peak RSS, CPU.

Does **not** modify production inference. Does **not** run 1K/5K/10K stress.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import time
from pathlib import Path

import cv2
import numpy as np

from semblon.engine import process_arch, process_execution
from semblon.experimental.inference import available_backends, load_backend


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    arr = np.asarray(sorted(values), dtype=np.float64)
    if arr.size == 1:
        return float(arr[0])
    k = (arr.size - 1) * (p / 100.0)
    f = int(np.floor(k))
    c = int(np.ceil(k))
    if f == c:
        return float(arr[f])
    return float(arr[f] * (c - k) + arr[c] * (k - f))


def _summarize(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean_s": 0.0, "p50_s": 0.0, "p95_s": 0.0, "sum_s": 0.0}
    return {
        "n": len(values),
        "mean_s": float(sum(values) / len(values)),
        "p50_s": _percentile(values, 50),
        "p95_s": _percentile(values, 95),
        "sum_s": float(sum(values)),
    }


def _iter_images(folder: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in exts)


def _rss_mb() -> float:
    # Linux: ru_maxrss is kilobytes.
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def run_bench(
    *,
    corpus: Path,
    backends: list[str],
    detect_long_side: int | None,
    warmup: int,
    limit: int | None,
) -> dict:
    images = _iter_images(corpus)
    if limit is not None:
        images = images[: int(limit)]
    if not images:
        raise SystemExit(f"no images under {corpus}")

    report: dict = {
        "status": "MEASURED",
        "host": {
            "process_arch": process_arch(),
            "process_execution": process_execution(),
            "os_machine": os.uname().machine if hasattr(os, "uname") else "",
            "opencv_threads": int(cv2.getNumThreads()) if hasattr(cv2, "getNumThreads") else None,
        },
        "corpus": {"path": str(corpus), "count": len(images)},
        "detect_long_side": detect_long_side,
        "backends": {},
        "note": (
            "Linux cloud timings are a numerical/API proxy. "
            "Native Windows ARM64 must be re-measured on the owner machine; "
            "x64-on-ARM64 remains emulated."
        ),
    }

    for name in backends:
        backend = load_backend(name, detect_long_side=detect_long_side)  # type: ignore[arg-type]
        # Warmup
        for path in images[: max(0, warmup)]:
            img = cv2.imread(str(path))
            if img is not None:
                backend.embed_bgr_timed(img)

        rss_before = _rss_mb()
        cpu_before = time.process_time()
        wall0 = time.perf_counter()

        decode_times: list[float] = []
        view_times: list[float] = []
        detect_times: list[float] = []
        align_times: list[float] = []
        embed_times: list[float] = []
        total_times: list[float] = []
        face_counts: list[int] = []

        for path in images:
            t_dec0 = time.perf_counter()
            img = cv2.imread(str(path))
            t_dec1 = time.perf_counter()
            if img is None:
                continue
            timed = backend.embed_bgr_timed(img)
            decode_times.append(t_dec1 - t_dec0)
            view_times.append(timed.view_s)
            detect_times.append(timed.detect_s)
            align_times.append(timed.align_s)
            embed_times.append(timed.embed_s)
            total_times.append(timed.total_s + (t_dec1 - t_dec0))
            face_counts.append(len(timed.faces))

        wall1 = time.perf_counter()
        cpu_after = time.process_time()
        rss_after = _rss_mb()
        wall = wall1 - wall0
        cpu = max(0.0, cpu_after - cpu_before)
        report["backends"][name] = {
            "info": backend.info(),
            "faces_total": int(sum(face_counts)),
            "faces_per_image_mean": float(sum(face_counts) / max(1, len(face_counts))),
            "latency": {
                "decode": _summarize(decode_times),
                "view_prep": _summarize(view_times),
                "yunet_detect": _summarize(detect_times),
                "face_align": _summarize(align_times),
                "sface_embed": _summarize(embed_times),
                "total_with_decode": _summarize(total_times),
            },
            "wall_s": float(wall),
            "cpu_s": float(cpu),
            "cpu_utilization_approx": float(cpu / wall) if wall > 0 else None,
            "peak_rss_mb": float(max(rss_before, rss_after)),
            "rss_delta_mb": float(rss_after - rss_before),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True, help="Folder of stills")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/perf-inference/backend-bench.json"),
        help="JSON report path (space after --out)",
    )
    parser.add_argument(
        "--backends",
        default="opencv_dnn,ort_yunet_sface",
        help="Comma-separated backend names",
    )
    parser.add_argument("--detect-long-side", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    wanted = [b.strip() for b in args.backends.split(",") if b.strip()]
    have = set(available_backends())
    missing = [b for b in wanted if b not in have]
    if missing:
        raise SystemExit(f"backends unavailable: {missing}; have={sorted(have)}")

    report = run_bench(
        corpus=args.corpus,
        backends=wanted,
        detect_long_side=args.detect_long_side,
        warmup=args.warmup,
        limit=args.limit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(args.out), "backends": list(report["backends"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
