#!/usr/bin/env python3
"""Timed OpenCV DLL/pyd load probe for PERF P1 (Windows ARM64).

Fail-fast: each LoadLibrary runs in a child process with a hard timeout so a
hang on opencv_geometry500.dll does not freeze the parent forever.

Does NOT install into or swap the S1 / product identity environment.
Optional ARM64 lab venv: .venv-arm64-perf (see docs/PERF-P1-ARM64.md).

Env overrides:
  SEMBLON_ARM64_OPENCV_BIN   DLL directory
  SEMBLON_ARM64_OPENCV_PYD   cv2 .pyd path

Examples (owner Windows ARM64)::

  .venv-arm64-perf\\Scripts\\python.exe tools\\_perf_p1_load_cv2.py --pe-only
  .venv-arm64-perf\\Scripts\\python.exe tools\\_perf_p1_load_cv2.py --timeout 20 --json
  .venv-arm64-perf\\Scripts\\python.exe -m semblon lab opencv --timeout 8
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Allow running from repo root without install
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from semblon.opencv_probe import (  # noqa: E402
    ARM64_DLL_ORDER,
    DEFAULT_ARM64_BIN,
    DEFAULT_ARM64_PYD,
    KNOWN_HANG_DLL,
    inspect_arm64_opencv_layout,
)
from semblon.pe_arch import pe_machine  # noqa: E402


def _load_one_child(path: str) -> None:
    """Child entry: LoadLibrary one path and print ok."""
    import ctypes

    t0 = time.perf_counter()
    if hasattr(os, "add_dll_directory"):
        parent = str(Path(path).parent)
        try:
            os.add_dll_directory(parent)
        except (FileNotFoundError, OSError):
            pass
        os.environ["PATH"] = parent + os.pathsep + os.environ.get("PATH", "")
    ctypes.WinDLL(path)
    print(json.dumps({"ok": True, "path": path, "load_s": round(time.perf_counter() - t0, 3)}))


def _timed_load(path: Path, timeout_s: float) -> dict:
    pe = pe_machine(path)
    if not pe.get("exists"):
        return {"path": str(path), "ok": False, "status": "missing", "pe": pe}
    if not pe.get("ok"):
        return {"path": str(path), "ok": False, "status": "pe_error", "pe": pe}
    if os.name != "nt":
        return {
            "path": str(path),
            "ok": False,
            "status": "skipped_non_windows",
            "pe": pe,
            "note": "LoadLibrary only runs on Windows; PE inspect still valid",
        }
    try:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--_child-load", str(path)],
            capture_output=True,
            text=True,
            timeout=float(timeout_s),
        )
    except subprocess.TimeoutExpired:
        return {
            "path": str(path),
            "ok": False,
            "status": "timeout",
            "timeout_s": timeout_s,
            "pe": pe,
            "known_hang": path.name == KNOWN_HANG_DLL,
            "note": (
                f"LoadLibrary exceeded {timeout_s}s"
                + (f" (historical hang: {KNOWN_HANG_DLL})" if path.name == KNOWN_HANG_DLL else "")
            ),
        }
    if proc.returncode != 0:
        return {
            "path": str(path),
            "ok": False,
            "status": "error",
            "pe": pe,
            "stderr": (proc.stderr or "")[-500:],
            "stdout": (proc.stdout or "")[-500:],
        }
    try:
        line = proc.stdout.strip().splitlines()[-1]
        body = json.loads(line)
    except Exception as e:
        return {
            "path": str(path),
            "ok": False,
            "status": "parse",
            "error": str(e),
            "pe": pe,
            "stdout": (proc.stdout or "")[-500:],
        }
    body["status"] = "ok"
    body["pe"] = pe
    return body


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--_child-load":
        _load_one_child(argv[1])
        return 0

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--bin",
        default=os.environ.get("SEMBLON_ARM64_OPENCV_BIN", DEFAULT_ARM64_BIN),
        help="OpenCV DLL Release directory",
    )
    ap.add_argument(
        "--pyd",
        default=os.environ.get("SEMBLON_ARM64_OPENCV_PYD", DEFAULT_ARM64_PYD),
        help="cv2 ARM64 .pyd path",
    )
    ap.add_argument("--timeout", type=float, default=20.0, help="per-DLL LoadLibrary timeout seconds")
    ap.add_argument("--pe-only", action="store_true", help="PE inspect only (no LoadLibrary)")
    ap.add_argument("--json", action="store_true", help="print one JSON object")
    ap.add_argument("--stop-on-fail", action="store_true", default=True)
    ap.add_argument("--no-stop-on-fail", action="store_false", dest="stop_on_fail")
    args = ap.parse_args(argv)

    layout = inspect_arm64_opencv_layout(bin_dir=args.bin, pyd_path=args.pyd)
    if args.pe_only:
        rec = {"mode": "pe_only", "layout": layout, "identity_firewall": layout["identity_firewall"]}
        print(json.dumps(rec, indent=2))
        return 0

    results = []
    bin_p = Path(args.bin)
    overall_ok = True
    for name in ARM64_DLL_ORDER:
        r = _timed_load(bin_p / name, args.timeout)
        results.append(r)
        if not args.json:
            st = r.get("status")
            print(f"{name}: {st}" + (f" {r.get('load_s')}s" if r.get("load_s") is not None else ""), flush=True)
            if r.get("note"):
                print(f"  note: {r['note']}", flush=True)
        if not r.get("ok"):
            overall_ok = False
            if args.stop_on_fail:
                break
    else:
        # all DLLs ok — try pyd
        r = _timed_load(Path(args.pyd), args.timeout)
        results.append(r)
        if not args.json:
            print(f"pyd: {r.get('status')}", flush=True)
        if not r.get("ok"):
            overall_ok = False

    out = {
        "mode": "timed_load",
        "ok": overall_ok,
        "bin": str(bin_p),
        "pyd": args.pyd,
        "timeout_s": args.timeout,
        "results": results,
        "layout_pe": layout,
        "identity_firewall": {
            "semblon_consumes_this_for_s1": False,
            "note": "Lab/perf probe only. Do not swap S1 x64 cv2.",
        },
    }
    print(json.dumps(out, indent=2))
    if overall_ok:
        return 0
    # timeout on known hang dll => 2; other failure => 3
    if any(r.get("status") == "timeout" for r in results):
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
