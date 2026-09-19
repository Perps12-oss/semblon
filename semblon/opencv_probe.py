"""Timed OpenCV import. Treats ARM64 hang as an engineering result, not a gate."""

from __future__ import annotations

import json
import subprocess
import sys


def probe_opencv(timeout_s: float = 8.0) -> dict:
    code = (
        "import json,sys,time,platform;"
        "t=time.perf_counter();"
        "import cv2;"
        "print(json.dumps({"
        "'ok': True,"
        "'import_s': round(time.perf_counter()-t, 3),"
        "'cv2': getattr(cv2,'__version__',None),"
        "'file': getattr(cv2,'__file__',None),"
        "'python': sys.version.split()[0],"
        "'machine': platform.machine(),"
        "}))"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=float(timeout_s),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "timeout",
            "timeout_s": timeout_s,
            "note": "OpenCV import exceeded timeout (known ARM64 hang class)",
        }
    if proc.returncode != 0:
        return {
            "ok": False,
            "status": "error",
            "stderr": (proc.stderr or "")[-500:],
        }
    try:
        rec = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        return {"ok": False, "status": "parse", "error": str(e), "stdout": proc.stdout[-500:]}
    rec["status"] = "ok"
    return rec
