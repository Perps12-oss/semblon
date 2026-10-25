"""Locate the same YuNet/SFace ONNX files production uses — never download."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from semblon.identity_config import (
    SFACE_ONNX,
    YUNET_ONNX_FALLBACK,
    YUNET_ONNX_PREFERRED,
)

# Expected SHA-256 from docs/IDENTITY-PACK.md (owner pin 2026-10-16).
KNOWN_SHA256 = {
    YUNET_ONNX_FALLBACK: "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    SFACE_ONNX: "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lab_pack_candidates() -> list[Path]:
    """Search order for lab models. Production pin dir first, then lab override."""
    out: list[Path] = []
    env = (os.environ.get("SEMBLON_PERF_FACE_PACK") or "").strip()
    if env:
        out.append(Path(env))
    env2 = (os.environ.get("SEMBLON_FACE_PACK") or os.environ.get("FACEKIT_PACK_DIR") or "").strip()
    if env2:
        out.append(Path(env2))
    out.append(Path.home() / ".semblon" / "models" / "yunet_sface")
    out.append(Path("/tmp/semblon-perf-lab/models"))
    # Dedup preserving order.
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def resolve_yunet(root: Path) -> Path:
    preferred = root / YUNET_ONNX_PREFERRED
    if preferred.is_file():
        return preferred
    fallback = root / YUNET_ONNX_FALLBACK
    if fallback.is_file():
        return fallback
    raise FileNotFoundError(
        f"YuNet ONNX missing under {root} "
        f"(need {YUNET_ONNX_PREFERRED} or {YUNET_ONNX_FALLBACK})"
    )


def resolve_sface(root: Path) -> Path:
    path = root / SFACE_ONNX
    if path.is_file():
        return path
    raise FileNotFoundError(f"SFace ONNX missing: {path}")


def find_pack() -> tuple[Path, Path, Path]:
    """Return ``(pack_dir, yunet_path, sface_path)``."""
    errors: list[str] = []
    for root in lab_pack_candidates():
        try:
            yunet = resolve_yunet(root)
            sface = resolve_sface(root)
            return root, yunet, sface
        except FileNotFoundError as exc:
            errors.append(str(exc))
    raise FileNotFoundError(
        "No YuNet/SFace pack found for experimental inference. "
        "Set SEMBLON_PERF_FACE_PACK to a directory with the Zoo ONNX files "
        "(unchanged filenames). Semblon does not download weights. "
        + " | ".join(errors[:3])
    )


def verify_known_hashes(yunet: Path, sface: Path) -> dict[str, object]:
    """Report SHA-256 vs IDENTITY-PACK pins. Does not modify files."""
    report: dict[str, object] = {"yunet": {}, "sface": {}}
    for label, path in (("yunet", yunet), ("sface", sface)):
        digest = _sha256(path)
        expected = KNOWN_SHA256.get(path.name)
        entry = {
            "path": str(path),
            "name": path.name,
            "sha256": digest,
            "expected_sha256": expected,
            "matches_identity_pack_pin": (expected is None) or (digest == expected),
        }
        if expected is None and path.name == YUNET_ONNX_PREFERRED:
            entry["note"] = (
                "2026may preferred by production; IDENTITY-PACK.md pins 2023mar SHA only"
            )
        report[label] = entry
    return report
