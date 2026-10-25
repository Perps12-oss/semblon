#!/usr/bin/env python3
"""Identity-safety compare: experimental backend vs OpenCV DNN reference.

Compares detection recall/precision vs reference, bbox IoU, embedding cosine,
and retrieval ranking — without changing thresholds, eps, min_samples, or
detection gates. Does not write persons / faces.person_id.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from semblon.experimental.inference import load_backend
from semblon.identity_config import DEFAULT_THRESHOLD, DET_SCORE_MIN


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return float(inter / denom) if denom > 0 else 0.0


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def _match_detections(
    ref: list[dict],
    cand: list[dict],
    iou_thresh: float = 0.5,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    pairs: list[tuple[float, int, int]] = []
    for i, r in enumerate(ref):
        for j, c in enumerate(cand):
            pairs.append((_iou(r["bbox"], c["bbox"]), i, j))
    pairs.sort(reverse=True)
    used_r: set[int] = set()
    used_c: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for iou, i, j in pairs:
        if iou < iou_thresh:
            break
        if i in used_r or j in used_c:
            continue
        used_r.add(i)
        used_c.add(j)
        matches.append((i, j, iou))
    fn = [i for i in range(len(ref)) if i not in used_r]
    fp = [j for j in range(len(cand)) if j not in used_c]
    return matches, fn, fp


def _iter_images(folder: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in exts)


def evaluate(
    *,
    corpus: Path,
    candidate: str,
    detect_long_side: int | None,
    limit: int | None,
) -> dict:
    images = _iter_images(corpus)
    if limit is not None:
        images = images[: int(limit)]
    ref_b = load_backend("opencv_dnn", detect_long_side=detect_long_side)
    cand_b = load_backend(candidate, detect_long_side=detect_long_side)  # type: ignore[arg-type]

    tp = fp = fn = 0
    ious: list[float] = []
    cosines: list[float] = []
    rank_top1 = 0
    rank_queries = 0

    # Collect embeddings for retrieval: use reference faces as gallery.
    gallery: list[tuple[str, np.ndarray]] = []
    per_image: list[dict] = []

    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        ref_rows = ref_b.embed_bgr_timed(img).faces
        cand_rows = cand_b.embed_bgr_timed(img).faces
        # Apply the same detection score gate production uses (no threshold change).
        ref_rows = [r for r in ref_rows if r["det_score"] >= DET_SCORE_MIN]
        cand_rows = [c for c in cand_rows if c["det_score"] >= DET_SCORE_MIN]

        matches, miss, extra = _match_detections(ref_rows, cand_rows)
        tp += len(matches)
        fn += len(miss)
        fp += len(extra)
        for i, j, iou in matches:
            ious.append(iou)
            cos = _cosine(ref_rows[i]["embedding"], cand_rows[j]["embedding"])
            cosines.append(cos)

        for r in ref_rows:
            gallery.append((path.name, r["embedding"]))

        per_image.append(
            {
                "file": path.name,
                "ref_faces": len(ref_rows),
                "cand_faces": len(cand_rows),
                "matches": len(matches),
                "fn": len(miss),
                "fp": len(extra),
            }
        )

    # Retrieval: for each matched pair, does candidate embedding retrieve the
    # same reference face as rank-1 among the gallery?
    # Simpler: within each image, cosine between matched embeddings already
    # measured. Cross-image: for each ref embedding, find nearest gallery
    # neighbour excluding itself; then check candidate's embedding ranks that
    # neighbour equivalently — skip if gallery too small.
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        ref_rows = [r for r in ref_b.embed_bgr_timed(img).faces if r["det_score"] >= DET_SCORE_MIN]
        cand_rows = [c for c in cand_b.embed_bgr_timed(img).faces if c["det_score"] >= DET_SCORE_MIN]
        matches, _, _ = _match_detections(ref_rows, cand_rows)
        for i, j, _iou in matches:
            q = cand_rows[j]["embedding"]
            # Rank all reference gallery faces by cosine to candidate embedding.
            scored = sorted(
                ((_cosine(q, emb), name) for name, emb in gallery),
                reverse=True,
            )
            if not scored:
                continue
            rank_queries += 1
            # Top-1 should be a face from the same file (same identity proxy).
            if scored[0][1] == path.name:
                rank_top1 += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    mean_iou = float(sum(ious) / len(ious)) if ious else None
    mean_cos = float(sum(cosines) / len(cosines)) if cosines else None
    min_cos = float(min(cosines)) if cosines else None

    # Safety gate: candidate must not invent automatic identity; we only compare
    # vectors. Numerical agreement bar for lab PASS-proxy.
    agreement_ok = (
        mean_cos is not None
        and mean_cos >= 0.98
        and (min_cos is None or min_cos >= 0.95)
        and precision >= 0.95
        and recall >= 0.95
        and (mean_iou is None or mean_iou >= 0.7)
    )

    return {
        "status": "MEASURED",
        "reference_backend": "opencv_dnn",
        "candidate_backend": candidate,
        "thresholds_unchanged": {
            "DET_SCORE_MIN": DET_SCORE_MIN,
            "DEFAULT_THRESHOLD": DEFAULT_THRESHOLD,
            "note": "No eps / min_samples / confidence / min-face edits",
        },
        "detection": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "mean_bbox_iou": mean_iou,
        },
        "embedding": {
            "matched_pairs": len(cosines),
            "mean_cosine": mean_cos,
            "min_cosine": min_cos,
            "p50_cosine": float(np.median(cosines)) if cosines else None,
        },
        "retrieval": {
            "queries": rank_queries,
            "top1_same_file": rank_top1,
            "top1_rate": (rank_top1 / rank_queries) if rank_queries else None,
        },
        "lab_agreement_gate": {
            "pass": bool(agreement_ok),
            "criteria": "mean_cos>=0.98, min_cos>=0.95, P/R>=0.95, mean_iou>=0.7",
            "production_cutover": False,
            "note": (
                "Lab agreement is necessary but not sufficient for production. "
                "Owner photographic set + native ARM64 evidence still required."
            ),
        },
        "reference_info": ref_b.info(),
        "candidate_info": cand_b.info(),
        "per_image": per_image,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/perf-inference/identity-safety.json"),
    )
    parser.add_argument("--candidate", default="ort_yunet_sface")
    parser.add_argument("--detect-long-side", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = evaluate(
        corpus=args.corpus,
        candidate=args.candidate,
        detect_long_side=args.detect_long_side,
        limit=args.limit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(args.out),
                "lab_agreement_pass": report["lab_agreement_gate"]["pass"],
                "precision": report["detection"]["precision"],
                "recall": report["detection"]["recall"],
                "mean_cosine": report["embedding"]["mean_cosine"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
