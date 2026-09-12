"""InsightFace pack loader. FACE-000 only — one image detect + embed."""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from semblon import ADAPTER_VERSION

PACK_FAMILY = "insightface/buffalo_l"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_weight_hashes(root: Path | None = None) -> dict[str, str]:
    home = Path(root) if root else Path.home() / ".insightface" / "models" / "buffalo_l"
    out: dict[str, str] = {}
    if not home.is_dir():
        return out
    for p in sorted(home.glob("*.onnx")):
        out[p.name] = _sha256_file(p)
    return out


def pack_id(insightface_version: str, weight_hashes: dict[str, str]) -> str:
    if not weight_hashes:
        digest = "unhashed"
    else:
        blob = "".join(f"{k}:{v};" for k, v in sorted(weight_hashes.items()))
        digest = hashlib.sha256(blob.encode()).hexdigest()[:16]
    return f"{PACK_FAMILY}@{insightface_version}/adapter-{ADAPTER_VERSION}/sha256:{digest}"


def load_app(det_size: tuple[int, int] = (640, 640)):
    from insightface.app import FaceAnalysis

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=det_size)
    return app


def embed_image(app, path: Path) -> list[dict]:
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"cannot decode {path}")
    faces = app.get(img)
    rows = []
    for f in faces:
        vec = np.asarray(f.normed_embedding, dtype=np.float32)
        x1, y1, x2, y2 = [float(v) for v in f.bbox]
        w, h = int(x2 - x1), int(y2 - y1)
        rows.append(
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": float(f.det_score),
                "face_w": w,
                "face_h": h,
                "dim": int(vec.size),
                "embedding": vec,
            }
        )
    return rows
