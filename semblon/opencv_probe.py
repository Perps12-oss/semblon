"""Timed OpenCV import + PE diagnostics.

Treats ARM64 hang as an engineering result, not a product gate.
Never silent-swaps the S1 / identity path onto an ARM64 build.

IMPORTANT: this module must not import semblon.engine (engine imports cv2 at
module load). Arch helpers are duplicated here so `import semblon.opencv_probe`
stays safe when cv2 LoadLibrary hangs.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from semblon.pe_arch import pe_machine

# Historical P1 hang class (docs/PERF-P1-ARM64.md)
KNOWN_HANG_DLL = "opencv_geometry500.dll"

DEFAULT_ARM64_BIN = "C:/Users/S8633/.arm64-build/build/bin/Release"
DEFAULT_ARM64_PYD = (
    "C:/Users/S8633/.arm64-build/build/lib/python3/Release/"
    "cv2.cp314-win_arm64.pyd"
)

# Ordered load list matching the historical hang repro
ARM64_DLL_ORDER: tuple[str, ...] = (
    "opencv_core500.dll",
    "opencv_geometry500.dll",
    "opencv_imgproc500.dll",
    "opencv_imgcodecs500.dll",
    "opencv_highgui500.dll",
)


def _process_arch() -> str:
    """Architecture of this Python process, not the OS. (mirror engine.process_arch)"""
    ver = sys.version.lower()
    if "amd64" in ver or "x86_64" in ver:
        return "x64"
    m = platform.machine().lower()
    if m in {"amd64", "x86_64"}:
        return "x64"
    if m in {"arm64", "aarch64"}:
        return "arm64"
    return m


def _process_execution() -> str:
    """native vs emulated. x64 Python on ARM64 Windows is always emulated."""
    arch = _process_arch()
    machine = platform.machine().lower()
    env_arch = os.environ.get("PROCESSOR_ARCHITECTURE", "").upper()
    env_native = os.environ.get("PROCESSOR_ARCHITEW6432", "").upper()
    os_is_arm = (
        env_arch == "ARM64"
        or env_native == "ARM64"
        or machine in {"arm64", "aarch64"}
    )
    if os_is_arm and arch == "x64":
        return "emulated"
    if arch in {"x64", "arm64"}:
        return "native"
    return "unknown"


def _host_context() -> dict:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "machine": platform.machine(),
        "process_arch": _process_arch(),
        "process_execution": _process_execution(),
        "os_name": os.name,
    }


def inspect_opencv_binding(path: str | Path) -> dict:
    """PE-only inspect of a cv2 .pyd (or DLL). Does not LoadLibrary / import."""
    host = _host_context()
    pe = pe_machine(path)
    identity_note = None
    if pe.get("ok") and host["process_arch"] == "arm64" and pe.get("arch") == "x64":
        identity_note = (
            "x64 OpenCV binding under ARM64 Python would be wrong; "
            "S1 correctness path stays on separate x64 env — do not silent-swap"
        )
    if pe.get("ok") and host["process_arch"] == "x64" and pe.get("arch") == "arm64":
        identity_note = (
            "ARM64 OpenCV binding under x64 Python is not the S1 path; "
            "lab/perf only — do not silent-swap product identity env"
        )
    return {
        **host,
        "ok": bool(pe.get("ok")),
        "status": "ok" if pe.get("ok") else "error",
        "binding": pe,
        "identity_firewall": {
            "semblon_consumes_this_for_s1": False,
            "note": identity_note
            or "PE inspect only; adopting ARM64 cv2 requires an explicit separate decision",
        },
    }


def inspect_arm64_opencv_layout(
    bin_dir: str | Path | None = None,
    pyd_path: str | Path | None = None,
) -> dict:
    """PE-check ARM64 OpenCV build layout without loading any DLL.

    Safe on Linux CI when paths are missing (reports exists=false).
    """
    bin_p = Path(bin_dir or os.environ.get("SEMBLON_ARM64_OPENCV_BIN", DEFAULT_ARM64_BIN))
    pyd_p = Path(pyd_path or os.environ.get("SEMBLON_ARM64_OPENCV_PYD", DEFAULT_ARM64_PYD))
    dlls = []
    for name in ARM64_DLL_ORDER:
        dlls.append(pe_machine(bin_p / name))
    pyd = pe_machine(pyd_p)
    present = [d for d in dlls if d.get("exists")]
    expected_arm = bool(present) and all(
        (d.get("ok") and d.get("arch") == "arm64") for d in present
    ) and (not pyd.get("exists") or (pyd.get("ok") and pyd.get("arch") == "arm64"))
    hang_dll = next((d for d in dlls if str(d.get("path", "")).endswith(KNOWN_HANG_DLL)), None)
    return {
        **_host_context(),
        "ok": True,
        "status": "layout",
        "bin_dir": str(bin_p),
        "pyd": pyd,
        "dlls": dlls,
        "known_hang_dll": KNOWN_HANG_DLL,
        "hang_dll_present": bool(hang_dll and hang_dll.get("exists")),
        "all_present_are_arm64": expected_arm,
        "import_safe_to_try": False,
        "note": (
            "PE layout only — does not LoadLibrary. "
            f"Historical blocker: {KNOWN_HANG_DLL} hang after opencv_core500.dll. "
            "Use tools/_perf_p1_load_cv2.py on Windows ARM64 for timed load."
        ),
        "identity_firewall": {
            "semblon_consumes_this_for_s1": False,
            "product_workers_default": 1,
        },
    }


def probe_opencv(timeout_s: float = 8.0, *, pe_binding: bool = True) -> dict:
    """Timed subprocess import of cv2. Timeout => hang class (known on ARM64)."""
    host = _host_context()
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
            **host,
            "ok": False,
            "status": "timeout",
            "timeout_s": timeout_s,
            "known_hang_dll": KNOWN_HANG_DLL,
            "note": (
                "OpenCV import exceeded timeout (known ARM64 hang class: "
                f"{KNOWN_HANG_DLL}). See docs/PERF-P1-ARM64.md. "
                "S1 x64 cv2 path was not touched."
            ),
            "fail_fast": True,
        }
    if proc.returncode != 0:
        return {
            **host,
            "ok": False,
            "status": "error",
            "stderr": (proc.stderr or "")[-500:],
            "fail_fast": True,
        }
    try:
        rec = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        return {
            **host,
            "ok": False,
            "status": "parse",
            "error": str(e),
            "stdout": proc.stdout[-500:],
        }
    rec.update(host)
    rec["status"] = "ok"
    rec["fail_fast"] = False
    if pe_binding and rec.get("file"):
        rec["binding"] = pe_machine(rec["file"])
        barch = (rec.get("binding") or {}).get("arch")
        if barch == "x64" and host["process_execution"] == "emulated":
            rec["identity_path"] = "s1_x64_emulated_on_arm64_os"
        elif barch == "arm64" and host["process_arch"] == "arm64":
            rec["identity_path"] = "arm64_lab_candidate_not_s1_default"
        else:
            rec["identity_path"] = "reported"
        rec["semblon_consumes_as_native_opencv"] = False
    return rec
