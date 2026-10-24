#!/usr/bin/env python3
"""Build a frozen 48-still lab corpus for inference backend benchmarks.

The owner 48-still set is not in the repo. This tool materialises a
**lab stand-in** from public OpenCV sample stills plus deterministic
transforms covering: small faces, distant faces, high-res portraits,
group-like multi-face canvases, difficult lighting, and multiples.

Does not touch production thresholds or ingest. Writes under
``docs/evidence/perf-inference-48still/`` by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np

SAMPLES = {
    "lena": "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg",
    "fruits": "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/fruits.jpg",
}


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file() or dest.stat().st_size < 1000:
        urllib.request.urlretrieve(url, dest)
    return dest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _write(path: Path, img: np.ndarray) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), img)
    if not ok:
        raise RuntimeError(f"failed to write {path}")
    return {
        "file": path.name,
        "sha256": _sha256(path),
        "shape": [int(img.shape[0]), int(img.shape[1]), int(img.shape[2])],
    }


def build(out_dir: Path, cache: Path) -> dict:
    lena = cv2.imread(str(_download(SAMPLES["lena"], cache / "lena.jpg")))
    fruits = cv2.imread(str(_download(SAMPLES["fruits"], cache / "fruits.jpg")))
    if lena is None or fruits is None:
        raise RuntimeError("failed to load sample stills")

    stills_dir = out_dir / "stills"
    if stills_dir.exists():
        for old in stills_dir.glob("*"):
            old.unlink()
    stills_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    idx = 0

    def add(tag: str, category: str, img: np.ndarray) -> None:
        nonlocal idx
        idx += 1
        name = f"{idx:02d}_{tag}.jpg"
        meta = _write(stills_dir / name, img)
        meta["tag"] = tag
        meta["category"] = category
        rows.append(meta)

    # High-resolution portraits (upscale + slight crops).
    for i, scale in enumerate((1.0, 1.5, 2.0, 2.5)):
        big = cv2.resize(
            lena,
            (int(lena.shape[1] * scale), int(lena.shape[0] * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
        add(f"portrait_hires_{i}", "high_resolution_portrait", big)

    # Small / distant faces: paste a shrunk face into a large canvas.
    for i, face_side in enumerate((48, 64, 80, 96, 120, 160)):
        canvas = np.full((1600, 2400, 3), 40, dtype=np.uint8)
        face = cv2.resize(lena, (face_side, face_side), interpolation=cv2.INTER_AREA)
        y0 = 200 + i * 30
        x0 = 400 + i * 80
        canvas[y0 : y0 + face_side, x0 : x0 + face_side] = face
        cat = "small_face" if face_side < 80 else "distant_face"
        add(f"distant_{face_side}", cat, canvas)

    # Difficult lighting.
    for i, (alpha, beta) in enumerate(((0.45, -40), (0.7, -20), (1.4, 30), (1.8, 50), (0.35, 10), (2.2, -10))):
        lit = cv2.convertScaleAbs(lena, alpha=alpha, beta=beta)
        add(f"lighting_{i}", "difficult_lighting", lit)

    # Group-like: multiple Lena faces on one frame.
    for i, n_faces in enumerate((2, 3, 4, 5, 6, 8)):
        canvas = np.full((1200, 1600, 3), 28, dtype=np.uint8)
        side = 180 if n_faces <= 4 else 140
        for j in range(n_faces):
            face = cv2.resize(lena, (side, side), interpolation=cv2.INTER_AREA)
            # Distinct bytes so ingest would not hash-collapse copies.
            face = face.copy()
            face[0, j % side, :] = (j * 37) % 256
            row, col = divmod(j, 4)
            y0 = 80 + row * (side + 40)
            x0 = 60 + col * (side + 50)
            canvas[y0 : y0 + side, x0 : x0 + side] = face
        add(f"group_{n_faces}", "group_photograph", canvas)

    # Multiples / mild pose proxies via flip + rotate.
    for i, angle in enumerate((0, 8, -8, 15, -15, 180)):
        m = cv2.getRotationMatrix2D((lena.shape[1] / 2, lena.shape[0] / 2), angle, 1.0)
        rot = cv2.warpAffine(lena, m, (lena.shape[1], lena.shape[0]))
        if i % 2:
            rot = cv2.flip(rot, 1)
        add(f"pose_{angle}", "multiple_faces_variant", rot)

    # Fill to exactly 48 with fruits composites (non-face + face) for negatives.
    while len(rows) < 48:
        i = len(rows)
        canvas = fruits.copy()
        side = 160
        face = cv2.resize(lena, (side, side), interpolation=cv2.INTER_AREA)
        y0 = 20 + (i % 5) * 10
        x0 = 20 + (i % 7) * 15
        h, w = canvas.shape[:2]
        if y0 + side < h and x0 + side < w:
            canvas[y0 : y0 + side, x0 : x0 + side] = face
        add(f"composite_{i}", "group_photograph", canvas)

    rows = rows[:48]
    # Drop extras if overshot.
    keep_names = {r["file"] for r in rows}
    for path in stills_dir.glob("*.jpg"):
        if path.name not in keep_names:
            path.unlink()

    manifest = {
        "name": "perf-inference-48still-lab",
        "status": "LAB_STAND_IN",
        "note": (
            "Owner 48-still photographic set is not in the repo. "
            "This corpus is a deterministic lab stand-in from OpenCV sample "
            "stills + transforms. Re-run identity-safety on the owner set "
            "before any production cutover."
        ),
        "count": len(rows),
        "categories": sorted({r["category"] for r in rows}),
        "stills": rows,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/perf-inference-48still"),
        help="Output directory (space after --out)",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("/tmp/semblon-perf-lab/sample-cache"),
    )
    args = parser.parse_args()
    manifest = build(args.out, args.cache)
    print(json.dumps({"wrote": str(args.out), "count": manifest["count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
