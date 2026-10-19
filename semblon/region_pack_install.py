"""User-confirmed installer for the pinned region-encoder pack.

This is an explicit install step. Query paths never download weights.
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from semblon.region_encoder import (
    KNOWN_SHA256,
    PIN_NAME,
    SOURCE_COMMIT,
    SOURCE_URL,
    WEIGHT_NAME,
    region_pack_dir,
    write_pin,
)


class RegionPackInstallError(RuntimeError):
    """Install failed; no partial file was published."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path, *, timeout_s: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    if partial.exists():
        partial.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "semblon-region-pack-install"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response, partial.open("wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    partial.replace(dest)


def install_region_pack(*, root: Path | None = None, timeout_s: float = 120.0) -> dict:
    """Install the pinned DINOv2 ONNX pack under the Semblon region-pack path."""
    home = region_pack_dir(root)
    dest = home / WEIGHT_NAME
    expected = KNOWN_SHA256[WEIGHT_NAME]
    if dest.is_file():
        digest = _sha256_file(dest)
        if digest.lower() == expected.lower():
            write_pin(home, digest)
            return {
                "state": "AVAILABLE",
                "path": str(dest),
                "sha256": digest,
                "bytes": dest.stat().st_size,
                "source": SOURCE_URL,
                "commit": SOURCE_COMMIT,
                "pin": str(home / PIN_NAME),
                "changed": False,
            }
        dest.unlink(missing_ok=True)
    try:
        _download(SOURCE_URL, dest, timeout_s=timeout_s)
        digest = _sha256_file(dest)
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise RegionPackInstallError(f"region pack install failed: {exc.__class__.__name__}") from exc
    if digest.lower() != expected.lower():
        dest.unlink(missing_ok=True)
        raise RegionPackInstallError(
            f"region pack install refused: sha256={digest} expected={expected}"
        )
    write_pin(home, digest)
    return {
        "state": "AVAILABLE",
        "path": str(dest),
        "sha256": digest,
        "bytes": dest.stat().st_size,
        "source": SOURCE_URL,
        "commit": SOURCE_COMMIT,
        "pin": str(home / PIN_NAME),
        "changed": True,
    }

