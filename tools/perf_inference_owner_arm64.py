#!/usr/bin/env python3
"""PERF-6 owner-machine native ARM64 validation orchestrator.

Runs in **one** interpreter at a time (emulated x64 or native ARM64).
The PowerShell wrapper invokes this twice and merges the decision gate.

Does not modify production inference, thresholds, model packs, or the shell.
Does not run 1K/5K/10K stress. Refuses the Linux lab stand-in corpus unless
``--allow-lab-stand-in`` is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from semblon.experimental.inference import load_backend
from semblon.experimental.inference.runtime_verify import verify_runtime
from semblon.identity_config import DET_SCORE_MIN

LAB_STAND_IN_MARKER = "perf-inference-48still"


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


def _working_set_mb() -> float | None:
    """Peak / current working set in MiB. Windows uses GetProcessMemoryInfo."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            )
            if not ok:
                return None
            return float(counters.PeakWorkingSetSize) / (1024.0 * 1024.0)
        except Exception:
            return None
    try:
        import resource

        # Linux: kilobytes
        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    except Exception:
        return None


def _iter_images(folder: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in exts)


def _refuse_lab_stand_in(corpus: Path, allow: bool) -> None:
    resolved = str(corpus.resolve()).replace("\\", "/")
    if LAB_STAND_IN_MARKER in resolved and not allow:
        raise SystemExit(
            f"Refusing lab stand-in corpus {corpus}. "
            "PERF-6 requires the owner photographic 48-still set. "
            "Pass --allow-lab-stand-in only for harness dry-runs."
        )


def _iou(a, b) -> float:
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


def _match(ref: list[dict], cand: list[dict], iou_thresh: float = 0.5):
    pairs = []
    for i, r in enumerate(ref):
        for j, c in enumerate(cand):
            pairs.append((_iou(r["bbox"], c["bbox"]), i, j))
    pairs.sort(reverse=True)
    used_r, used_c = set(), set()
    matches = []
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


def cmd_verify(out: Path) -> dict:
    report = verify_runtime()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def cmd_bench(
    *,
    role: str,
    backend: str,
    corpus: Path,
    out: Path,
    embeddings_out: Path,
    warmup: int,
    allow_lab: bool,
) -> dict:
    _refuse_lab_stand_in(corpus, allow_lab)
    images = _iter_images(corpus)
    if not images:
        raise SystemExit(f"no images under {corpus}")

    runtime = verify_runtime()
    t_init0 = time.perf_counter()
    backend_obj = load_backend(backend)  # type: ignore[arg-type]
    init_s = time.perf_counter() - t_init0

    # Warmup (excluded from steady-state).
    for path in images[: max(0, warmup)]:
        img = cv2.imread(str(path))
        if img is not None:
            backend_obj.embed_bgr_timed(img)

    ws_before = _working_set_mb()
    cpu_before = time.process_time()
    wall0 = time.perf_counter()

    decode_t: list[float] = []
    detect_t: list[float] = []
    align_t: list[float] = []
    embed_t: list[float] = []
    total_t: list[float] = []
    face_counts: list[int] = []
    dumps: list[dict] = []

    for path in images:
        t0 = time.perf_counter()
        img = cv2.imread(str(path))
        t1 = time.perf_counter()
        if img is None:
            continue
        timed = backend_obj.embed_bgr_timed(img)
        decode_t.append(t1 - t0)
        detect_t.append(timed.detect_s)
        align_t.append(timed.align_s)
        embed_t.append(timed.embed_s)
        total_t.append((t1 - t0) + timed.total_s)
        face_counts.append(len(timed.faces))
        faces_ser = []
        for f in timed.faces:
            if f["det_score"] < DET_SCORE_MIN:
                continue
            faces_ser.append(
                {
                    "bbox": [float(x) for x in f["bbox"]],
                    "det_score": float(f["det_score"]),
                    "face_w": int(f["face_w"]),
                    "face_h": int(f["face_h"]),
                    "embedding": [float(x) for x in np.asarray(f["embedding"]).tolist()],
                }
            )
        dumps.append({"file": path.name, "rel": str(path), "faces": faces_ser})

    wall = time.perf_counter() - wall0
    cpu = max(0.0, time.process_time() - cpu_before)
    ws_after = _working_set_mb()
    n_img = len(total_t)
    n_faces = int(sum(face_counts))

    report = {
        "status": "MEASURED",
        "role": role,
        "backend": backend,
        "slice": "PERF-6",
        "runtime": runtime,
        "corpus": {
            "path": str(corpus),
            "count": n_img,
            "lab_stand_in": LAB_STAND_IN_MARKER in str(corpus).replace("\\", "/"),
        },
        "init_s": float(init_s),
        "warmup_images": int(warmup),
        "steady_state": {
            "latency": {
                "decode": _summarize(decode_t),
                "yunet_detect": _summarize(detect_t),
                "face_align": _summarize(align_t),
                "sface_embed": _summarize(embed_t),
                "total_with_decode": _summarize(total_t),
            },
            "wall_s": float(wall),
            "cpu_s": float(cpu),
            "cpu_utilization_approx": float(cpu / wall) if wall > 0 else None,
            "images_per_s": float(n_img / wall) if wall > 0 else None,
            "faces_per_s": float(n_faces / wall) if wall > 0 else None,
            "faces_total": n_faces,
            "working_set_mb_before": ws_before,
            "peak_working_set_mb": ws_after,
            "memory_growth_mb": (
                float(ws_after - ws_before)
                if ws_before is not None and ws_after is not None
                else None
            ),
        },
        "backend_info": backend_obj.info(),
        "identity_writes": False,
        "thresholds_unchanged": True,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    embeddings_out.parent.mkdir(parents=True, exist_ok=True)
    embeddings_out.write_text(
        json.dumps(
            {
                "role": role,
                "backend": backend,
                "runtime": {
                    "process_arch": runtime.get("process_arch"),
                    "process_execution": runtime.get("process_execution"),
                },
                "images": dumps,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def cmd_identity_compare(
    *,
    reference_embeddings: Path,
    candidate_embeddings: Path,
    out: Path,
    small_face_max: int = 80,
) -> dict:
    """Cross-process identity safety using dumped embeddings (no threshold edits)."""
    ref = json.loads(reference_embeddings.read_text(encoding="utf-8"))
    cand = json.loads(candidate_embeddings.read_text(encoding="utf-8"))
    ref_by = {row["file"]: row["faces"] for row in ref["images"]}
    cand_by = {row["file"]: row["faces"] for row in cand["images"]}
    files = sorted(set(ref_by) & set(cand_by))

    tp = fp = fn = 0
    ious: list[float] = []
    cosines: list[float] = []
    small_tp = small_fn = 0
    distant_proxy_tp = distant_proxy_fn = 0

    gallery: list[tuple[str, np.ndarray]] = []
    for name, faces in ref_by.items():
        for f in faces:
            gallery.append((name, np.asarray(f["embedding"], dtype=np.float32)))

    top1_ok = 0
    top1_n = 0

    for name in files:
        rfaces = ref_by[name]
        cfaces = cand_by[name]
        matches, miss, extra = _match(rfaces, cfaces)
        tp += len(matches)
        fn += len(miss)
        fp += len(extra)
        for i, j, iou in matches:
            ious.append(iou)
            a = np.asarray(rfaces[i]["embedding"], dtype=np.float32)
            b = np.asarray(cfaces[j]["embedding"], dtype=np.float32)
            cosines.append(float(np.dot(a, b)))
            side = min(int(rfaces[i]["face_w"]), int(rfaces[i]["face_h"]))
            if side < small_face_max:
                small_tp += 1
            # Distant proxy: small face on large canvas (face side < 120).
            if side < 120:
                distant_proxy_tp += 1
        for i in miss:
            side = min(int(rfaces[i]["face_w"]), int(rfaces[i]["face_h"]))
            if side < small_face_max:
                small_fn += 1
            if side < 120:
                distant_proxy_fn += 1

        for i, j, _ in matches:
            q = np.asarray(cfaces[j]["embedding"], dtype=np.float32)
            scored = sorted(((float(np.dot(q, emb)), n) for n, emb in gallery), reverse=True)
            if not scored:
                continue
            top1_n += 1
            if scored[0][1] == name:
                top1_ok += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    mean_iou = float(sum(ious) / len(ious)) if ious else None
    mean_cos = float(sum(cosines) / len(cosines)) if cosines else None
    min_cos = float(min(cosines)) if cosines else None
    small_recall = (
        small_tp / (small_tp + small_fn) if (small_tp + small_fn) else None
    )
    distant_recall = (
        distant_proxy_tp / (distant_proxy_tp + distant_proxy_fn)
        if (distant_proxy_tp + distant_proxy_fn)
        else None
    )

    agreement = (
        mean_cos is not None
        and mean_cos >= 0.98
        and (min_cos is None or min_cos >= 0.95)
        and precision >= 0.95
        and recall >= 0.95
        and (mean_iou is None or mean_iou >= 0.7)
    )

    report = {
        "status": "MEASURED",
        "slice": "PERF-6",
        "reference": {
            "path": str(reference_embeddings),
            "role": ref.get("role"),
            "backend": ref.get("backend"),
            "runtime": ref.get("runtime"),
        },
        "candidate": {
            "path": str(candidate_embeddings),
            "role": cand.get("role"),
            "backend": cand.get("backend"),
            "runtime": cand.get("runtime"),
        },
        "thresholds_unchanged": {
            "DET_SCORE_MIN": DET_SCORE_MIN,
            "note": "No eps / min_samples / confidence / min-face edits",
        },
        "unauthorized_identity_assignment": False,
        "detection": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "mean_bbox_iou": mean_iou,
            "small_face_recall": small_recall,
            "distant_face_proxy_recall": distant_recall,
        },
        "embedding": {
            "matched_pairs": len(cosines),
            "mean_cosine": mean_cos,
            "min_cosine": min_cos,
            "p50_cosine": float(np.median(cosines)) if cosines else None,
        },
        "retrieval": {
            "queries": top1_n,
            "top1_same_file": top1_ok,
            "top1_rate": (top1_ok / top1_n) if top1_n else None,
        },
        "owner_agreement_gate": {
            "pass": bool(agreement),
            "criteria": "mean_cos>=0.98, min_cos>=0.95, P/R>=0.95, mean_iou>=0.7",
            "linux_lab_not_a_substitute": True,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def cmd_decide(
    *,
    bench_a: Path,
    bench_b: Path,
    identity: Path,
    bench_c: Path | None,
    out: Path,
) -> dict:
    a = json.loads(bench_a.read_text(encoding="utf-8"))
    b = json.loads(bench_b.read_text(encoding="utf-8"))
    ident = json.loads(identity.read_text(encoding="utf-8"))
    c = json.loads(bench_c.read_text(encoding="utf-8")) if bench_c and bench_c.is_file() else None

    a_ips = (a.get("steady_state") or {}).get("images_per_s") or 0.0
    b_ips = (b.get("steady_state") or {}).get("images_per_s") or 0.0
    a_wall = (a.get("steady_state") or {}).get("wall_s") or 0.0
    b_wall = (b.get("steady_state") or {}).get("wall_s") or 0.0
    speedup = (a_wall / b_wall) if b_wall > 0 else None
    faster = b_ips > a_ips and (speedup or 0) > 1.05
    slower = b_ips < a_ips and (speedup or 99) < 0.95
    identity_ok = bool((ident.get("owner_agreement_gate") or {}).get("pass"))

    a_rt = a.get("runtime") or {}
    b_rt = b.get("runtime") or {}
    a_emulated = (a_rt.get("process_execution") == "emulated") or (
        (a_rt.get("labels") or {}).get("emulated_x64_on_arm64")
    )
    b_native = (b_rt.get("process_arch") == "arm64") and (
        b_rt.get("process_execution") == "native"
    )

    if not identity_ok:
        verdict = "NO_CUTOVER"
        reason = "identity agreement gate failed on owner photographic set"
        recommend = "Do not integrate. Investigate decode/align numerical drift."
    elif not b_native:
        verdict = "INCONCLUSIVE"
        reason = "candidate run was not native ARM64"
        recommend = "Re-run role B under .venv-arm64-perf native ARM64 Python."
    elif not a_emulated and a_rt.get("process_execution") != "emulated":
        # Still allow compare if A is x64 native on x64 host, but PERF-6 expects emulated.
        verdict = "INCONCLUSIVE"
        reason = (
            "role A was not labelled emulated x64-on-ARM64; "
            f"got arch={a_rt.get('process_arch')} execution={a_rt.get('process_execution')}"
        )
        recommend = "Re-run role A with the production x64 venv on the ARM64 Windows host."
    elif faster and identity_ok and b_native:
        verdict = "RECOMMEND_CONTROLLED_EXPERIMENTAL_INTEGRATION"
        reason = (
            f"native ORT faster than emulated OpenCV "
            f"(ips {b_ips:.3f} vs {a_ips:.3f}, wall speedup {speedup:.3f}×) "
            "and identity gate PASS"
        )
        recommend = (
            "Proceed to Phase 2: explicit backend selection lab CLI only. "
            "Do not silent-swap production ingest."
        )
    elif slower and identity_ok:
        verdict = "INVESTIGATE_SETTINGS"
        reason = (
            f"native ORT slower than emulated OpenCV "
            f"(ips {b_ips:.3f} vs {a_ips:.3f}); identity still PASS"
        )
        recommend = (
            "Tune ORT intra_op threads / session options and re-measure memory "
            "before deciding. No cutover."
        )
    else:
        verdict = "INCONCLUSIVE"
        reason = "speed delta within 5% or missing metrics"
        recommend = "Do not cut over. Collect another timed run on the same corpus."

    report = {
        "status": "DECIDED",
        "slice": "PERF-6",
        "verdict": verdict,
        "reason": reason,
        "recommendation": recommend,
        "comparison": {
            "A_emulated_opencv": {
                "path": str(bench_a),
                "images_per_s": a_ips,
                "wall_s": a_wall,
                "process_arch": a_rt.get("process_arch"),
                "process_execution": a_rt.get("process_execution"),
            },
            "B_native_ort": {
                "path": str(bench_b),
                "images_per_s": b_ips,
                "wall_s": b_wall,
                "process_arch": b_rt.get("process_arch"),
                "process_execution": b_rt.get("process_execution"),
            },
            "C_native_opencv": (
                {
                    "path": str(bench_c),
                    "images_per_s": (c.get("steady_state") or {}).get("images_per_s"),
                    "wall_s": (c.get("steady_state") or {}).get("wall_s"),
                    "process_arch": (c.get("runtime") or {}).get("process_arch"),
                    "process_execution": (c.get("runtime") or {}).get("process_execution"),
                }
                if c
                else None
            ),
            "wall_speedup_A_over_B": speedup,
            "identity_pass": identity_ok,
        },
        "production_cutover": False,
        "stress_1k_5k_10k": "not_run",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify = sub.add_parser("verify", help="Runtime architecture verification")
    p_verify.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/perf-inference/owner-arm64-runtime.json"),
    )

    p_bench = sub.add_parser("bench", help="Steady-state backend benchmark")
    p_bench.add_argument("--role", required=True, choices=["A", "B", "C"])
    p_bench.add_argument("--backend", required=True, choices=["opencv_dnn", "ort_yunet_sface"])
    p_bench.add_argument("--corpus", type=Path, required=True)
    p_bench.add_argument("--out", type=Path, required=True)
    p_bench.add_argument("--embeddings-out", type=Path, required=True)
    p_bench.add_argument("--warmup", type=int, default=3)
    p_bench.add_argument("--allow-lab-stand-in", action="store_true")

    p_id = sub.add_parser("identity", help="Compare dumped embeddings A vs B")
    p_id.add_argument("--reference-embeddings", type=Path, required=True)
    p_id.add_argument("--candidate-embeddings", type=Path, required=True)
    p_id.add_argument("--out", type=Path, required=True)

    p_dec = sub.add_parser("decide", help="PERF-6 decision gate")
    p_dec.add_argument("--bench-a", type=Path, required=True)
    p_dec.add_argument("--bench-b", type=Path, required=True)
    p_dec.add_argument("--bench-c", type=Path, default=None)
    p_dec.add_argument("--identity", type=Path, required=True)
    p_dec.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "verify":
        rep = cmd_verify(args.out)
        print(json.dumps({"wrote": str(args.out), "labels": rep.get("labels")}, indent=2))
        return 0
    if args.cmd == "bench":
        rep = cmd_bench(
            role=args.role,
            backend=args.backend,
            corpus=args.corpus,
            out=args.out,
            embeddings_out=args.embeddings_out,
            warmup=args.warmup,
            allow_lab=args.allow_lab_stand_in,
        )
        ss = rep["steady_state"]
        print(
            json.dumps(
                {
                    "wrote": str(args.out),
                    "role": args.role,
                    "backend": args.backend,
                    "images_per_s": ss.get("images_per_s"),
                    "faces_per_s": ss.get("faces_per_s"),
                    "wall_s": ss.get("wall_s"),
                    "arch": rep["runtime"].get("process_arch"),
                    "execution": rep["runtime"].get("process_execution"),
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "identity":
        rep = cmd_identity_compare(
            reference_embeddings=args.reference_embeddings,
            candidate_embeddings=args.candidate_embeddings,
            out=args.out,
        )
        print(
            json.dumps(
                {
                    "wrote": str(args.out),
                    "pass": rep["owner_agreement_gate"]["pass"],
                    "precision": rep["detection"]["precision"],
                    "recall": rep["detection"]["recall"],
                    "mean_cosine": rep["embedding"]["mean_cosine"],
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "decide":
        rep = cmd_decide(
            bench_a=args.bench_a,
            bench_b=args.bench_b,
            identity=args.identity,
            bench_c=args.bench_c,
            out=args.out,
        )
        print(json.dumps({"wrote": str(args.out), "verdict": rep["verdict"]}, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
