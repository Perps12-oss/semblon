"""NanoDet object-detection pack — BYO only, never identity.

Missing / invalid / unpinned weights → UNAVAILABLE. Semblon never downloads
these files. Contour regions (``opencv-contour``) are a separate observation
path and must not be treated as detector labels.
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

# Owner-machine pin after download. Empty until recorded — probe still accepts
# a present ONNX + pin that either omits sha256 or matches when set.
# Do not treat a directory Apache-2.0 claim as MSI bundling clearance.
KNOWN_SHA256: dict[str, str] = {
    # Filled when owner records download evidence in docs/OBJECT-PACK.md
}


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


def probe_nanodet_status(root: Path | None = None) -> tuple[bool, str | None]:
    """True only when BYO NanoDet pack is present and pin/hash checks pass."""
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
    digest = _sha256_file(onnx)
    expected = KNOWN_SHA256.get(WEIGHT_NAME)
    pin = home / PIN_NAME
    pin_data: dict = {}
    if pin.is_file():
        try:
            pin_data = json.loads(pin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, "unavailable: NanoDet pack pin is unreadable"
        if not isinstance(pin_data, dict):
            return False, "unavailable: NanoDet pack pin is invalid"
        pin_sha = str(pin_data.get("sha256") or pin_data.get(WEIGHT_NAME) or "").strip().lower()
        if pin_sha and pin_sha != digest:
            return False, "unavailable: NanoDet ONNX SHA-256 does not match pack pin"
        if expected and pin_sha and pin_sha != expected.lower():
            return False, "unavailable: NanoDet pin SHA-256 is not the documented artifact"
    elif expected and digest != expected.lower():
        return False, (
            "unavailable: NanoDet ONNX SHA-256 does not match the documented artifact "
            f"(add {PIN_NAME} or replace the file)"
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
