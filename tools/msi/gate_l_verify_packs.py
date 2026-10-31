#!/usr/bin/env python3
"""Gate L BYO pack hash evidence — RELEASE / OWNER TOOLING ONLY (not shipped in MSI).

Compares ONNX files already on disk to the SHA-256 pins recorded in pack docs.
Success is evidence for docs/licenses.md review. It is NOT Gate L PASS and does
NOT allowlist MSI bundling (tools/msi/assert-no-weights.py still fails closed).

Run (after manual BYO download / pack-accept / fetch_region_pack):

  python tools/msi/gate_l_verify_packs.py --out docs/gate_l_signoff_temp.md
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

# Pins from docs/IDENTITY-PACK.md, docs/OBJECT-PACK.md, docs/REGION-PACK.md.
PACK_GATE_MANIFEST: list[dict] = [
    {
        "pack_name": "yunet_face_detector",
        "filename": "face_detection_yunet_2023mar.onnx",
        "rel_dirs": ["yunet_sface"],
        "license_type": "MIT (OpenCV Zoo directory — confirm exact bytes)",
        "expected_sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "doc": "docs/IDENTITY-PACK.md",
    },
    {
        "pack_name": "sface_face_encoder",
        "filename": "face_recognition_sface_2021dec.onnx",
        "rel_dirs": ["yunet_sface"],
        "license_type": "Apache-2.0 (OpenCV Zoo directory — confirm exact bytes)",
        "expected_sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "doc": "docs/IDENTITY-PACK.md",
    },
    {
        "pack_name": "nanodet_object_detector",
        "filename": "object_detection_nanodet_2022nov.onnx",
        "rel_dirs": ["nanodet"],
        "license_type": "Apache-2.0 (OpenCV Zoo directory — confirm exact bytes)",
        "expected_sha256": "4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186",
        "doc": "docs/OBJECT-PACK.md",
    },
    {
        "pack_name": "dinov2_region_encoder",
        "filename": "dinov2-vits14.onnx",
        "rel_dirs": ["region"],
        "license_type": "Apache-2.0 (onnx-community dinov2-small pin)",
        "expected_sha256": "f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a",
        "doc": "docs/REGION-PACK.md",
    },
]


def _models_root() -> Path:
    override = os.environ.get("SEMBLON_MODELS_ROOT", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".semblon" / "models"


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(2 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_pack_file(packs_dir: Path, pack: dict) -> Path | None:
    direct = packs_dir / pack["filename"]
    if direct.is_file():
        return direct
    for rel in pack.get("rel_dirs") or []:
        candidate = packs_dir / rel / pack["filename"]
        if candidate.is_file():
            return candidate
    return None


def run_gate(packs_dir: Path, out_md: Path) -> bool:
    lines: list[str] = [
        "# Gate L pack hash evidence (temporary)",
        "",
        "This file is operator evidence only. It does **not** mark Gate L PASS",
        "and does **not** unlock MSI weight bundling.",
        "",
        f"Packs dir: `{packs_dir}`",
        "",
    ]
    all_ok = True
    for pack in PACK_GATE_MANIFEST:
        path = _resolve_pack_file(packs_dir, pack)
        if path is None:
            lines.append(f"- FAIL `{pack['pack_name']}`: FILE MISSING — `{pack['filename']}`")
            all_ok = False
            continue
        actual = compute_sha256(path)
        expected = str(pack["expected_sha256"])
        if actual == expected:
            lines.append(f"- PASS `{pack['pack_name']}`: HASH MATCH — `{actual}`")
        else:
            lines.append(
                f"- FAIL `{pack['pack_name']}`: HASH MISMATCH — expected `{expected}`, got `{actual}`"
            )
            all_ok = False
        lines.append(f"  - License note: {pack['license_type']}")
        lines.append(f"  - Doc: {pack['doc']}")
        lines.append(f"  - Path: `{path}`")
        lines.append("")
    lines.append("Gate L status remains **OPEN / BYO** until legal sign-off (`docs/licenses.md`).")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nGate log written to {out_md}")
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packs-dir",
        type=Path,
        default=None,
        help="Directory that contains pack subfolders or ONNX files (default: ~/.semblon/models)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/gate_l_signoff_temp.md"),
        help="Markdown evidence path (default: docs/gate_l_signoff_temp.md)",
    )
    args = parser.parse_args(argv)
    packs_dir = (args.packs_dir or _models_root()).expanduser().resolve()
    ok = run_gate(packs_dir, args.out)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
