"""Semblon-specific YuNet+SFace evaluation harness (honest, corpus-driven).

Does not invent PASS. Requires a local corpus directory of images and an
optional labels JSON. Writes a JSON report. Does not download weights.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from semblon.engine import (
    EXPECTED_FACE_DIM,
    ModelPackError,
    embed_bgr,
    load_app,
    process_arch,
    process_execution,
)
from semblon.identity_config import DEFAULT_EPS, DEFAULT_THRESHOLD, PACK_FAMILY


def _iter_images(root: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in exts and p.is_file())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True, help="Folder of stills")
    parser.add_argument("--out", type=Path, required=True, help="JSON report path")
    parser.add_argument(
        "--labels",
        type=Path,
        default=None,
        help="Optional JSON list of {path, person_id} for verification pairs",
    )
    args = parser.parse_args(argv)

    report: dict = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "pack_family": PACK_FAMILY,
        "expected_dim": EXPECTED_FACE_DIM,
        "provisional_eps": DEFAULT_EPS,
        "provisional_threshold": DEFAULT_THRESHOLD,
        "arch": process_arch(),
        "execution": process_execution(),
        "opencv_version": cv2.__version__,
        "status": "FAILED",
        "gate_q": "OPEN",
        "note": "Published Zoo benchmarks are not Semblon acceptance.",
    }
    try:
        app = load_app()
    except ModelPackError as exc:
        report["error"] = str(exc)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(report["error"], file=__import__("sys").stderr)
        return 1

    images = _iter_images(args.corpus)
    t0 = time.perf_counter()
    n_faces = 0
    per_image = []
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            per_image.append({"path": str(path), "error": "decode_failed"})
            continue
        t1 = time.perf_counter()
        faces = embed_bgr(app, img)
        dt = time.perf_counter() - t1
        n_faces += len(faces)
        per_image.append(
            {
                "path": str(path),
                "faces": len(faces),
                "detect_embed_s": round(dt, 4),
                "dims": [f["dim"] for f in faces],
            }
        )
    elapsed = time.perf_counter() - t0
    report.update(
        {
            "status": "MEASURED",
            "images": len(images),
            "faces": n_faces,
            "wall_s": round(elapsed, 3),
            "images_per_s": round(len(images) / elapsed, 3) if elapsed else None,
            "per_image": per_image,
            "labels_path": str(args.labels) if args.labels else None,
            "gate_q": "OPEN",
            "acceptance": (
                "Not claimed. Supply labelled same/different pairs and false-merge "
                "review before Q PASS."
            ),
        }
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "images", "faces", "wall_s", "gate_q")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
