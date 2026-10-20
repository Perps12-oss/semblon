"""NanoDet object-detection pack — observation only, never identity.

Missing / invalid / unpinned weights → UNAVAILABLE. Probe and search never
download these files. A confirmed install lives in ``object_pack_install``.
Contour regions (``opencv-contour``) are a separate observation path and
must not be treated as detector labels.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

# OpenCV Zoo NanoDet-Plus-m 416 (COCO-80). Redistribution in MSI remains L OPEN.
WEIGHT_NAME = "object_detection_nanodet_2022nov.onnx"
PIN_NAME = "semblon-object-pack-pin.json"
PROVIDER = "opencv-zoo-nanodet"
PACK_FAMILY = "opencv/nanodet"

# Owner-machine hash after BYO download 2026-10-16 (opencv_zoo main raw).
# Directory Apache-2.0 claim ≠ MSI bundling clearance — see docs/OBJECT-PACK.md.
KNOWN_SHA256: dict[str, str] = {
    WEIGHT_NAME: "4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186",
}
SOURCE_URL = (
    "https://github.com/opencv/opencv_zoo/raw/refs/heads/main/"
    "models/object_detection_nanodet/object_detection_nanodet_2022nov.onnx"
)


def object_pack_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    env = (os.environ.get("SEMBLON_OBJECT_PACK") or "").strip()
    if env:
        return Path(env)
    return Path.home() / ".semblon" / "models" / "nanodet"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def weight_path(root: Path | None = None) -> Path:
    return object_pack_dir(root) / WEIGHT_NAME


def pin_path(root: Path | None = None) -> Path:
    return object_pack_dir(root) / PIN_NAME


def write_pin(root: Path, digest: str) -> None:
    """Record the verified digest beside the ONNX. Does not download."""
    payload = {
        "sha256": digest,
        "file": WEIGHT_NAME,
        "provider": PROVIDER,
        "pack_family": PACK_FAMILY,
        "source_url": SOURCE_URL,
        "license": "Apache-2.0",
        "redistribution": "user-confirmed local install — MSI bundling blocked until L PASS",
    }
    (Path(root) / PIN_NAME).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def probe_nanodet_status(root: Path | None = None) -> tuple[bool, str | None]:
    """True only when BYO NanoDet pack is present, pinned, and hash-verified."""
    home = object_pack_dir(root)
    onnx = home / WEIGHT_NAME
    if not onnx.is_file():
        return False, (
            f"unavailable: NanoDet pack missing ({WEIGHT_NAME}). "
            "Place BYO weights under ~/.semblon/models/nanodet/ "
            "or set SEMBLON_OBJECT_PACK. Contours are not object search."
        )
    if onnx.stat().st_size < 1024:
        return False, "unavailable: NanoDet ONNX looks like a Git LFS pointer or truncated file"
    digest = _sha256_file(onnx).lower()
    expected = KNOWN_SHA256.get(WEIGHT_NAME, "").lower()
    pin = home / PIN_NAME
    if not pin.is_file():
        return False, (
            f"unavailable: NanoDet pack pin missing ({PIN_NAME}). "
            "Record sha256 beside the ONNX — docs/OBJECT-PACK.md."
        )
    try:
        raw = pin.read_text(encoding="utf-8-sig")
        pin_data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return False, "unavailable: NanoDet pack pin is unreadable"
    if not isinstance(pin_data, dict):
        return False, "unavailable: NanoDet pack pin is invalid"
    pin_sha = str(pin_data.get("sha256") or pin_data.get(WEIGHT_NAME) or "").strip().lower()
    if not pin_sha:
        return False, "unavailable: NanoDet pack pin has no sha256"
    if pin_sha != digest:
        return False, "unavailable: NanoDet ONNX SHA-256 does not match pack pin"
    if expected and digest != expected:
        return False, (
            "unavailable: NanoDet ONNX SHA-256 is not the documented artifact "
            f"(expected {expected[:16]}…)"
        )
    return True, None


def assert_nanodet_pack_ready(root: Path | None = None) -> dict[str, str]:
    ready, note = probe_nanodet_status(root)
    if not ready:
        raise FileNotFoundError(note or "NanoDet pack unavailable")
    home = object_pack_dir(root)
    onnx = home / WEIGHT_NAME
    digest = _sha256_file(onnx)
    return {
        "provider": PROVIDER,
        "pack_family": PACK_FAMILY,
        "weight": WEIGHT_NAME,
        "path": str(onnx.resolve()),
        "sha256": digest,
        "redistribution": "BYO — MSI bundling blocked until L PASS",
    }
