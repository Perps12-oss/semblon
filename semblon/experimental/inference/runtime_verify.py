"""Runtime architecture verification for PERF-6 owner ARM64 gate.

Labels native vs emulated honestly. Never silent-swaps production OpenCV.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from semblon.engine import process_arch, process_execution
from semblon.experimental.inference.pack import find_pack, verify_known_hashes
from semblon.pe_arch import pe_machine


def _ort_info() -> dict:
    try:
        import onnxruntime as ort
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    info: dict = {
        "available": True,
        "version": ort.__version__,
        "providers": list(ort.get_available_providers()),
        "cpu_ep": "CPUExecutionProvider" in ort.get_available_providers(),
        "package_file": getattr(ort, "__file__", None),
    }
    # Probe win_arm64 / win_amd64 wheel DLLs beside the package when present.
    pkg = Path(ort.__file__).resolve().parent if ort.__file__ else None
    pe_rows: list[dict] = []
    if pkg and pkg.is_dir():
        for pattern in ("*.dll", "*.pyd"):
            for path in sorted(pkg.glob(pattern))[:20]:
                try:
                    pe_rows.append(pe_machine(path))
                except Exception as exc:
                    pe_rows.append(
                        {"path": str(path), "ok": False, "error": f"{type(exc).__name__}: {exc}"}
                    )
    info["pe_binaries"] = pe_rows
    arches = sorted({str(r.get("arch") or "") for r in pe_rows if r.get("ok")} - {""})
    info["pe_arch_summary"] = arches
    return info


def _opencv_info() -> dict:
    try:
        import cv2
    except Exception as exc:
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "FaceDetectorYN": False,
            "FaceRecognizerSF": False,
            "dnn_usable": False,
        }
    info: dict = {
        "available": True,
        "version": getattr(cv2, "__version__", None),
        "file": getattr(cv2, "__file__", None),
        "FaceDetectorYN": hasattr(cv2, "FaceDetectorYN"),
        "FaceRecognizerSF": hasattr(cv2, "FaceRecognizerSF"),
        "threads": int(cv2.getNumThreads()) if hasattr(cv2, "getNumThreads") else None,
    }
    if cv2.__file__:
        try:
            info["pe"] = pe_machine(cv2.__file__)
        except Exception as exc:
            info["pe"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    info["dnn_usable"] = bool(info["FaceDetectorYN"] and info["FaceRecognizerSF"])
    return info


def _pack_info() -> dict:
    try:
        root, yunet, sface = find_pack()
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    pin = root / "semblon-pack-pin.json"
    return {
        "available": True,
        "dir": str(root),
        "yunet": str(yunet),
        "sface": str(sface),
        "pin_present": pin.is_file(),
        "hashes": verify_known_hashes(yunet, sface),
    }


def verify_runtime() -> dict:
    """Full host + pack + ORT + OpenCV verification record."""
    arch = process_arch()
    execution = process_execution()
    ort = _ort_info()
    opencv = _opencv_info()
    pack = _pack_info()

    # Gate helpers (honest labels only).
    native_arm64 = arch == "arm64" and execution == "native"
    emulated_x64_on_arm = arch == "x64" and execution == "emulated"
    ort_native_ok = bool(
        ort.get("available")
        and ort.get("cpu_ep")
        and (
            not native_arm64
            or not ort.get("pe_arch_summary")
            or "arm64" in ort.get("pe_arch_summary", [])
            or "AA64" in str(ort.get("pe_arch_summary"))
        )
    )

    return {
        "status": "VERIFIED" if (arch and execution) else "UNKNOWN",
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "process_arch": arch,
        "process_execution": execution,
        "os_machine": platform.machine(),
        "PROCESSOR_ARCHITECTURE": os.environ.get("PROCESSOR_ARCHITECTURE"),
        "PROCESSOR_ARCHITEW6432": os.environ.get("PROCESSOR_ARCHITEW6432"),
        "labels": {
            "native_arm64_python": native_arm64,
            "emulated_x64_on_arm64": emulated_x64_on_arm,
            "ort_cpu_ep_ok": bool(ort.get("cpu_ep")),
            "ort_native_probe_ok": ort_native_ok,
            "opencv_dnn_usable": bool(opencv.get("dnn_usable")),
            "face_pack_ok": bool(pack.get("available")),
        },
        "onnxruntime": ort,
        "opencv": opencv,
        "face_pack": pack,
        "note": (
            "x64 Python on ARM64 Windows is emulated — never call that native. "
            "OpenCV DNN may be unavailable on ARM64 even when ORT is native."
        ),
    }
