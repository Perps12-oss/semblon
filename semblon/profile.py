"""FACE-000: write docs/runtime.md from this machine."""

from __future__ import annotations

import json
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from semblon import __version__
from semblon.engine import (
    PACK_FAMILY,
    discover_weight_hashes,
    embed_image,
    load_app,
    pack_id,
    process_arch,
    process_execution,
)

# Windows paste hazard: --out docs/runtime.mdC:\Users\...\Scripts (missing space/newline)
_GLUED_PATH = re.compile(r"\.(md|html|json|txt)([A-Za-z]:[\\/])", re.IGNORECASE)


class ProfileError(ValueError):
    pass


def validate_out_path(out: Path) -> Path:
    """Reject clearly-glued Windows paths before mkdir blows up with WinError 123."""
    raw = str(out)
    m = _GLUED_PATH.search(raw)
    if m:
        intended = raw[: m.start() + 1 + len(m.group(1))]
        raise ProfileError(
            f"invalid --out path (two paths glued together):\n  {raw}\n"
            f"Use a single file path, e.g.:\n"
            f'  --out "{intended}"\n'
            f'Full example:\n'
            f'  semblon lab profile --image "D:\\photos\\face.jpg" --out "docs\\runtime.md"'
        )
    # Colon only allowed as drive letter (C:\...)
    norm = raw.replace("/", "\\")
    if ":" in norm:
        drive_ok = bool(re.match(r"^[A-Za-z]:\\", norm)) and norm.count(":") == 1
        if not drive_ok:
            raise ProfileError(
                f"invalid --out path (bad ':' in path): {raw}\n"
                f'Example: --out "docs\\runtime.md"'
            )
    return out


def _rss_mb() -> float | None:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return None


def _execution() -> str:
    return process_execution()


def _arch() -> str:
    return process_arch()


def run_profile(image: Path, out: Path) -> dict:
    out = validate_out_path(Path(out))

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
    try:
        if out.parent != Path(".") and str(out.parent) != "":
            out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ProfileError(
            f"cannot create output directory for --out {out}: {e}\n"
            f'Example: semblon lab profile --image "D:\\photos\\face.jpg" --out "docs\\runtime.md"'
        ) from e
    out.write_text(
        "# Runtime record (FACE-000)\n\n```json\n" + json.dumps(rec, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    return rec
