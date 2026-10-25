#!/usr/bin/env python3
"""Sweep YuNet detection long-side caps; measure speed vs detection quality.

No resolution becomes a production default without a quality gate PASS.
Uses the same DET_SCORE_MIN / NMS / TOP_K as production (unchanged).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from semblon.experimental.inference import load_backend
from semblon.identity_config import DETECT_LONG_SIDE, DET_SCORE_MIN


def _iter_images(folder: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in exts)


def sweep(
    *,
    corpus: Path,
    backend: str,
    sizes: list[int],
    limit: int | None,
) -> dict:
    images = _iter_images(corpus)
    if limit is not None:
        images = images[: int(limit)]

    # Reference: production long side.
    ref = load_backend(backend, detect_long_side=DETECT_LONG_SIDE)  # type: ignore[arg-type]
    ref_counts: dict[str, int] = {}
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        rows = [r for r in ref.embed_bgr_timed(img).faces if r["det_score"] >= DET_SCORE_MIN]
        ref_counts[path.name] = len(rows)

    results = []
    for size in sizes:
        b = load_backend(backend, detect_long_side=int(size))  # type: ignore[arg-type]
        total_s = 0.0
        detect_s = 0.0
        faces = 0
        recall_num = 0
        recall_den = 0
        for path in images:
            img = cv2.imread(str(path))
            if img is None:
                continue
            timed = b.embed_bgr_timed(img)
            rows = [r for r in timed.faces if r["det_score"] >= DET_SCORE_MIN]
            total_s += timed.total_s
            detect_s += timed.detect_s
            faces += len(rows)
            ref_n = ref_counts.get(path.name, 0)
            recall_den += ref_n
            # Proxy recall: face-count ratio capped at 1 (not box-matched).
            recall_num += min(len(rows), ref_n)
        results.append(
            {
                "detect_long_side": int(size),
                "is_production_default": int(size) == int(DETECT_LONG_SIDE),
                "wall_embed_s": float(total_s),
                "detect_s": float(detect_s),
                "faces": int(faces),
                "face_count_recall_vs_default": (
                    float(recall_num / recall_den) if recall_den else None
                ),
                "production_default_candidate": False,
            }
        )

    return {
        "status": "MEASURED",
        "backend": backend,
        "production_DETECT_LONG_SIDE": DETECT_LONG_SIDE,
        "DET_SCORE_MIN_unchanged": DET_SCORE_MIN,
        "rule": "No resolution change becomes production default without quality PASS",
        "sizes": results,
        "recommendation": (
            "Keep DETECT_LONG_SIDE=1280 until an owner photographic eval shows "
            "equal-or-better small/distant face recall at a smaller cap."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/perf-inference/resolution-sweep.json"),
    )
    parser.add_argument("--backend", default="ort_yunet_sface")
    parser.add_argument(
        "--sizes",
        default="320,640,960,1280,1600",
        help="Comma-separated YuNet long-side caps",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    report = sweep(
        corpus=args.corpus,
        backend=args.backend,
        sizes=sizes,
        limit=args.limit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(args.out), "sizes": sizes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
