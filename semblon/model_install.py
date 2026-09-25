"""Atomic model install. A partial file is never the published model."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


class InstallError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_model(source: Path, dest: Path, *, expected_sha256: str | None = None) -> dict:
    """Copy source onto dest only after the bytes are complete and checksummed.

    The published path is replaced with os.replace. A failed checksum leaves
    the previous dest in place. The temporary file is not a valid model path.
    """
    source = Path(source)
    dest = Path(dest)
    if not source.is_file():
        raise InstallError(f"source missing: {source}")
    digest = sha256_file(source)
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise InstallError("checksum mismatch; published model was not replaced")
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    data = source.read_bytes()
    with partial.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, dest)
    published = sha256_file(dest)
    if published != digest:
        raise InstallError("published model checksum changed during install")
    return {"path": str(dest), "sha256": published, "state": "AVAILABLE", "bytes": dest.stat().st_size}
