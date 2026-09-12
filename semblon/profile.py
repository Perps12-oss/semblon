"""FACE-000: write docs/runtime.md from this machine."""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from semblon import __version__
from semblon.engine import PACK_FAMILY, discover_weight_hashes, embed_image, load_app, pack_id


def _rss_mb() -> float | None:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return None


def _execution() -> str:
    proc = platform.machine().lower()
    if proc in {"amd64", "x86_64"}:
        os_arch = os.environ.get("PROCESSOR_ARCHITECTURE", "")
        if os_arch.upper() == "ARM64":
            return "emulated"
        return "native"
    if proc in {"arm64", "aarch64"}:
        return "native"
    return "unknown"


def _arch() -> str:
    m = platform.machine().lower()
    if m in {"amd64", "x86_64"}:
        return "x64"
    if m in {"arm64", "aarch64"}:
        return "arm64"
    return m


def run_profile(image: Path, out: Path) -> dict:
    import cv2
    import insightface
    import onnxruntime as ort

    t0 = time.perf_counter()
    app = load_app()
    load_s = time.perf_counter() - t0

    t_dec = time.perf_counter()
    raw = cv2.imread(str(image))
    decode_ms = (time.perf_counter() - t_dec) * 1000
    if raw is None:
        raise FileNotFoundError(image)

    t_det = time.perf_counter()
    faces = embed_image(app, image)
    both_ms = (time.perf_counter() - t_det) * 1000

    hashes = discover_weight_hashes()
    ifver = getattr(insightface, "__version__", "unknown")
    rec = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "os": platform.system().lower(),
        "os_version": platform.version(),
        "arch": _arch(),
        "execution": _execution(),
        "python": sys.version.split()[0],
        "python_arch": platform.architecture()[0],
        "ort_package": "onnxruntime",
        "ort_version": ort.__version__,
        "insightface_version": ifver,
        "pack_family": PACK_FAMILY,
        "pack_id": pack_id(ifver, hashes),
        "weight_files": hashes,
        "det_size": [640, 640],
        "device": "cpu",
        "device_name": None,
        "workers": 1,
        "embed_batch": 1,
        "peak_rss_mb": _rss_mb(),
        "model_load_s": round(load_s, 3),
        "software_version": __version__,
        "one_image": {
            "path": str(image),
            "decode_ms": round(decode_ms, 2),
            "detect_embed_ms": round(both_ms, 2),
            "faces": len(faces),
            "dims": [f["dim"] for f in faces],
        },
        "notes": "FACE-000 probe. detect_ms/embed_ms not split; see detect_embed_ms.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "# Runtime record (FACE-000)\n\n```json\n" + json.dumps(rec, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    return rec
