"""Sweep ingest workers=1,2,4 on a user-supplied folder. Measurement only.

Does not retune identity (eps / min_samples / pack / det_size unchanged).
Product default remains workers=1. Never flips that default from this file.

Emits a machine-readable default_gate (PASS/FAIL/PENDING) for "safe to
consider raising the product default" — PASS still requires a separate
explicit PR after owner Windows evidence.

Usage:
  python tools/perf_workers_harness.py --out results.json
      → writes verified=false / status=pending_human (no folder)

  python tools/perf_workers_harness.py --folder PATH --out results.json --execute
      → fresh store per workers value; asserts face-count equality; records
        images/sec, faces/sec, peak_rss_mb, speedup_vs_w1, default_gate

See docs/PERF-WORKERS-HARNESS.md. Historical multi-session numbers live in
docs/PERF-WORKERS.md (superseded design).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

SWEEP_WORKERS: tuple[int, ...] = (1, 2, 4)

# Minimum images_per_second ratio vs workers=1 to even *consider* raising default.
# Conservative: hash-only parallelism rarely wins end-to-end on CPU FaceKit.
MIN_SPEEDUP_FOR_DEFAULT_CONSIDERATION = 1.15

HUMAN_STEPS = [
    "Supply a fixed stills folder you own (not the S1 golden dump for retune).",
    "Use a fresh --out-dir (or default under --out parent) so each w={1,2,4} gets its own sqlite.",
    "Run: python tools/perf_workers_harness.py --folder PATH --out results.json --execute",
    "Confirm face_count_equal is true; compare images_per_second / faces_per_second only as measurement.",
    "Read default_gate.verdict: PASS means safe to *consider* a separate default-change PR — never silent.",
    "Do not change the product default from workers=1 based on this harness alone.",
]


def pending_record(*, out: Path | None = None, folder: Path | None = None) -> dict[str, Any]:
    """Honest unverified scaffold. status=pending_human until a real --execute run."""
    return {
        "harness": "perf_workers",
        "verified": False,
        "status": "pending_human",
        "note": (
            "Default product workers remain 1. No speedup claimed. "
            "docs/PERF-WORKERS.md is historical (superseded multi-session design). "
            "Human must supply --folder and --execute for verified=true."
        ),
        "workers_sweep": list(SWEEP_WORKERS),
        "folder": str(folder) if folder else None,
        "human_steps": list(HUMAN_STEPS),
        "runs": [],
        "face_count_equal": None,
        "peak_rss_mb": None,
        "safe_to_consider_default": False,
        "product_default_workers": 1,
        "default_gate": evaluate_default_gate(None),
    }


def _peak_rss_mb() -> float | None:
    try:
        from semblon.profile import _rss_mb

        return _rss_mb()
    except Exception:
        return None


def _one_run(
    *,
    folder: Path,
    store: Path,
    workers: int,
) -> dict[str, Any]:
    from semblon.ingest import ingest

    rss_before = _peak_rss_mb()
    t0 = time.perf_counter()
    out = ingest(folder, store, workers=workers)
    wall = time.perf_counter() - t0
    rss_after = _peak_rss_mb()
    peak = rss_after
    if rss_before is not None and rss_after is not None:
        peak = max(rss_before, rss_after)
    return {
        "workers": workers,
        "store": str(store),
        "wall_s": round(wall, 3),
        "run_id": out.get("run_id"),
        "files": out.get("files"),
        "faces": out.get("faces"),
        "ok": out.get("ok"),
        "low_quality": out.get("low_quality"),
        "rejected": out.get("rejected"),
        "failed": out.get("failed"),
        "ingest_s": out.get("ingest_s"),
        "images_per_second": out.get("images_per_second"),
        "faces_per_second": out.get("faces_per_second"),
        "peak_rss_mb": peak,
        "provider": "facekit",
        "device": "cpu",
    }


def face_counts_equal(runs: list[dict[str, Any]]) -> bool:
    if len(runs) < 2:
        return True
    keys = ("files", "faces", "ok", "low_quality", "rejected", "failed")
    base = runs[0]
    return all(all(r.get(k) == base.get(k) for k in keys) for r in runs[1:])


def _speedup_vs_w1(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate each run with speedup_vs_w1 from images_per_second (None if unknown)."""
    base_ips = None
    for r in runs:
        if r.get("workers") == 1:
            base_ips = r.get("images_per_second")
            break
    out: list[dict[str, Any]] = []
    for r in runs:
        row = dict(r)
        ips = r.get("images_per_second")
        if base_ips and ips and float(base_ips) > 0:
            row["speedup_vs_w1"] = round(float(ips) / float(base_ips), 4)
        else:
            row["speedup_vs_w1"] = None
        out.append(row)
    return out


def evaluate_default_gate(rec: dict[str, Any] | None) -> dict[str, Any]:
    """Machine-readable PASS/FAIL for 'safe to consider default'.

    PASS never flips product default — owner must open a separate PR with
    measured Windows evidence. FAIL / PENDING keep default=1.
    """
    criteria = {
        "verified": True,
        "face_count_equal": True,
        "min_speedup_vs_w1": MIN_SPEEDUP_FOR_DEFAULT_CONSIDERATION,
        "some_workers_gt_1_meets_min_speedup": True,
        "no_failed_faces_across_sweep": True,
        "product_default_unchanged_by_harness": True,
    }
    base = {
        "criteria": criteria,
        "product_default_workers": 1,
        "product_default_unchanged": True,
        "min_speedup_required": MIN_SPEEDUP_FOR_DEFAULT_CONSIDERATION,
        "note": (
            "PASS = safe to *consider* raising default in a separate PR. "
            "This harness never changes CLI/API default from 1."
        ),
    }
    if rec is None or not rec.get("verified"):
        return {
            **base,
            "verdict": "PENDING",
            "safe_to_consider_default": False,
            "reasons": ["no verified --execute sweep yet"],
        }

    reasons: list[str] = []
    if not rec.get("face_count_equal"):
        reasons.append("face_count_equal is false — logical equivalence failed")

    runs = list(rec.get("runs") or [])
    failed_any = any(int(r.get("failed") or 0) > 0 for r in runs)
    # failed counts must match across sweep when face_count_equal; still refuse
    # default consideration if the baseline itself had failures.
    if failed_any:
        reasons.append("one or more runs reported failed > 0")

    best_speedup = None
    for r in runs:
        if int(r.get("workers") or 0) <= 1:
            continue
        s = r.get("speedup_vs_w1")
        if s is None:
            continue
        best_speedup = s if best_speedup is None else max(best_speedup, s)
    if best_speedup is None:
        reasons.append("no speedup_vs_w1 for workers>1 (missing images_per_second)")
    elif float(best_speedup) < MIN_SPEEDUP_FOR_DEFAULT_CONSIDERATION:
        reasons.append(
            f"best workers>1 speedup_vs_w1={best_speedup} "
            f"< required {MIN_SPEEDUP_FOR_DEFAULT_CONSIDERATION}"
        )

    if reasons:
        return {
            **base,
            "verdict": "FAIL",
            "safe_to_consider_default": False,
            "best_speedup_vs_w1": best_speedup,
            "reasons": reasons,
        }

    return {
        **base,
        "verdict": "PASS",
        "safe_to_consider_default": True,
        "best_speedup_vs_w1": best_speedup,
        "reasons": [
            "face counts equal; measured speedup meets threshold — "
            "owner may open a separate PR to raise default after review"
        ],
    }


def run_sweep(
    *,
    folder: Path,
    out_dir: Path,
    out_path: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for w in SWEEP_WORKERS:
        store = out_dir / f"w{w}.sqlite"
        if store.exists():
            store.unlink()
        runs.append(_one_run(folder=folder, store=store, workers=w))
    runs = _speedup_vs_w1(runs)
    equal = face_counts_equal(runs)
    peaks = [r["peak_rss_mb"] for r in runs if r.get("peak_rss_mb") is not None]
    rec: dict[str, Any] = {
        "harness": "perf_workers",
        "verified": True,
        "status": "measured" if equal else "face_count_mismatch",
        "note": (
            "Measurement only. Product default remains workers=1. "
            "Do not treat ratio of images_per_second as a product default change "
            "unless default_gate.verdict is PASS and a separate PR authorizes it."
        ),
        "workers_sweep": list(SWEEP_WORKERS),
        "folder": str(folder),
        "out_dir": str(out_dir),
        "human_steps": list(HUMAN_STEPS),
        "runs": runs,
        "face_count_equal": equal,
        "peak_rss_mb": max(peaks) if peaks else None,
        "product_default_workers": 1,
    }
    gate = evaluate_default_gate(rec)
    rec["default_gate"] = gate
    rec["safe_to_consider_default"] = bool(gate.get("safe_to_consider_default"))
    if equal and gate.get("verdict") == "PASS":
        rec["status"] = "measured_default_gate_pass"
    elif equal:
        rec["status"] = "measured_default_gate_fail"
    out_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="perf_workers_harness")
    p.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="user-supplied stills folder (required with --execute)",
    )
    p.add_argument("--out", type=Path, default=Path("perf-workers-results.json"))
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="directory for per-workers sqlite stores (default: <out.parent>/perf-workers-stores)",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="actually run ingest sweep (needs FaceKit + real folder)",
    )
    p.add_argument(
        "--require-default-gate",
        action="store_true",
        help="exit 2 when default_gate.verdict is not PASS (still never flips product default)",
    )
    args = p.parse_args(argv)

    if not args.execute or args.folder is None:
        rec = pending_record(out=args.out, folder=args.folder)
        if args.execute and args.folder is None:
            rec["error"] = "--execute requires --folder"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(json.dumps(rec, indent=2))
        if args.require_default_gate:
            return 2
        return 0

    out_dir = args.out_dir or (args.out.parent / "perf-workers-stores")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rec = run_sweep(folder=args.folder, out_dir=out_dir, out_path=args.out)
    print(json.dumps(rec, indent=2))
    if not rec.get("face_count_equal"):
        return 1
    if args.require_default_gate and (rec.get("default_gate") or {}).get("verdict") != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
