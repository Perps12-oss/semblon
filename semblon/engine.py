"""InsightFace pack loader. FACE-000 only — one image detect + embed."""

from __future__ import annotations

import hashlib
import os
import platform
import sys
from pathlib import Path

import cv2
import numpy as np

from semblon import ADAPTER_VERSION


def process_arch() -> str:
    """Architecture of this Python process, not the OS.

    x64 CPython on ARM64 Windows must report x64. Never call that native ARM64.
    """
    ver = sys.version.lower()
    if "amd64" in ver or "x86_64" in ver:
        return "x64"
    m = platform.machine().lower()
    if m in {"amd64", "x86_64"}:
        return "x64"
    if m in {"arm64", "aarch64"}:
        return "arm64"
    return m


def process_execution() -> str:
    """native vs emulated. x64 Python on ARM64 Windows is always emulated.

    An x64 process often sees PROCESSOR_ARCHITECTURE=AMD64 even on ARM64 OS.
    platform.machine() on recent Windows ARM64 reports arm64 for that case.
    """
    arch = process_arch()
    machine = platform.machine().lower()
    env_arch = os.environ.get("PROCESSOR_ARCHITECTURE", "").upper()
    env_native = os.environ.get("PROCESSOR_ARCHITEW6432", "").upper()
    os_is_arm = (
        env_arch == "ARM64"
        or env_native == "ARM64"
        or machine in {"arm64", "aarch64"}
    )
    if os_is_arm and arch == "x64":
        return "emulated"
    if arch in {"x64", "arm64"}:
        return "native"
    return "unknown"

PACK_FAMILY = "insightface/buffalo_l"

# ORT EPs Semblon may treat as GPU when prefer_gpu and listed.
# AzureExecutionProvider is NOT GPU (common on Windows ARM64 ORT wheels).
GPU_EP_NAMES: tuple[str, ...] = (
    "CUDAExecutionProvider",
    "DmlExecutionProvider",
    "TensorrtExecutionProvider",
)
NON_GPU_ACCEL_PROVIDERS: tuple[str, ...] = ("AzureExecutionProvider",)


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
    """Content-address pack. Digest stays 16 hex (frozen identity key — do not widen).

    Empty hashes → sha256:unhashed. Callers that load models must re-hash after
    download; never treat two unhashed packs as proven-equal weights.
    """
    if not weight_hashes:
        digest = "unhashed"
    else:
        blob = "".join(f"{k}:{v};" for k, v in sorted(weight_hashes.items()))
        digest = hashlib.sha256(blob.encode()).hexdigest()[:16]
    return f"{PACK_FAMILY}@{insightface_version}/adapter-{ADAPTER_VERSION}/sha256:{digest}"


def onnx_providers() -> list[str]:
    try:
        import onnxruntime as ort

        return list(ort.get_available_providers())
    except Exception:
        return ["CPUExecutionProvider"]


def select_execution_provider(*, prefer_gpu: bool = True) -> dict:
    """Pick an ORT EP for FaceKit load. Present ≠ proven usable.

    Product honesty:
    - CUDA / DirectML / TensorRT listed + prefer_gpu → may choose that GPU EP.
    - Otherwise CPU — never claim GPU.
    - AzureExecutionProvider is never treated as GPU.
    - Does not swap the FaceKit / InsightFace identity pack.
    """
    available = onnx_providers()
    gpu_eps = [p for p in GPU_EP_NAMES if p in available]
    azure_listed = [p for p in NON_GPU_ACCEL_PROVIDERS if p in available]
    chosen = "CPUExecutionProvider"
    gpu = False
    if prefer_gpu and gpu_eps:
        chosen = gpu_eps[0]
        gpu = True
    # Prefer CPU over Azure / unknown non-GPU accel when falling back.
    if chosen not in available:
        if "CPUExecutionProvider" in available:
            chosen = "CPUExecutionProvider"
            gpu = False
        elif gpu_eps and prefer_gpu:
            chosen = gpu_eps[0]
            gpu = True
        else:
            chosen = available[0] if available else "CPUExecutionProvider"
            gpu = False
    if chosen in NON_GPU_ACCEL_PROVIDERS:
        gpu = False
        if "CPUExecutionProvider" in available:
            chosen = "CPUExecutionProvider"
    return {
        "available": available,
        "chosen": chosen,
        "gpu": gpu,
        "gpu_eps": gpu_eps,
        "azure_listed": azure_listed,
        "prefer_gpu": bool(prefer_gpu),
        "device": "gpu" if gpu else "cpu",
        "arch": process_arch(),
        "execution": process_execution(),
        "note": (
            "GPU means CUDA/DirectML/TensorRT is listed by ORT; not a smoke test. "
            "Azure is not GPU. InsightFace ctx_id=-1 (CPU pre/post). "
            "FaceKit remains the only identity engine."
        ),
    }


def product_prefer_gpu() -> bool:
    """Product path: prefer GPU only when ORT lists CUDA/DirectML/TensorRT.

    Absent → False (CPU). Listed ≠ smoke-tested; Settings must say so.
    """
    return bool(select_execution_provider(prefer_gpu=True)["gpu"])


def gpu_product_status() -> dict:
    """Honest Settings / CLI GPU copy. Never invent a GPU when no EP is listed."""
    rec = select_execution_provider(prefer_gpu=True)
    prefer = bool(rec["gpu"])
    if prefer:
        copy = (
            f"GPU EP listed: {rec['chosen']}. Product ingest/live prefers GPU. "
            "Listed ≠ proven usable (driver/device may still fail)."
        )
    else:
        azure_note = ""
        if rec.get("azure_listed"):
            azure_note = " AzureExecutionProvider is listed but is not GPU."
        copy = (
            "No CUDA/DirectML/TensorRT EP listed. Product ingest/live stays CPU."
            f"{azure_note} Do not claim GPU acceleration on this machine."
        )
    return {
        **rec,
        "prefer_gpu": prefer,
        "product_path": "prefer_gpu" if prefer else "cpu",
        "copy": copy,
    }


def format_execution_status_lines() -> list[str]:
    """Home Settings lines: FaceKit + honest EP/GPU + native/emulated."""
    st = gpu_product_status()
    lines = [
        "Provider: FaceKit (InsightFace buffalo_l) — identity engine unchanged",
        f"Device: {st['device']}  EP: {st['chosen']}  gpu={st['gpu']}",
        f"Product path: {st['product_path']} (prefer_gpu={st['prefer_gpu']})",
        f"Process: arch={st['arch']} execution={st['execution']}",
        f"ORT providers: {', '.join(st['available']) or '(none)'}",
    ]
    if st["gpu_eps"]:
        lines.append(f"GPU EPs listed: {', '.join(st['gpu_eps'])}")
    else:
        lines.append("GPU EPs listed: (none — CUDA/DirectML/TensorRT)")
    if st.get("azure_listed"):
        lines.append(
            "AzureExecutionProvider listed — not GPU; Semblon does not claim GPU for Azure."
        )
    lines.append(st["copy"])
    return lines


def load_app(det_size: tuple[int, int] = (640, 640), *, prefer_gpu: bool = False):
    from insightface.app import FaceAnalysis

    sel = select_execution_provider(prefer_gpu=prefer_gpu)
    providers = [sel["chosen"]]
    if sel["chosen"] != "CPUExecutionProvider":
        providers.append("CPUExecutionProvider")
    app = FaceAnalysis(name="buffalo_l", providers=providers)
    # InsightFace ctx_id=-1 = CPU for its own path; ORT still uses `providers`.
    app.prepare(ctx_id=-1, det_size=det_size)
    app._semblon_ep = sel  # type: ignore[attr-defined]
    return app


EXPECTED_FACE_DIM = 512


def embed_bgr(app, img) -> list[dict]:
    """FaceKit detect+embed on a BGR array. Same pack path as stills. No disk write."""
    if app is None:
        raise ValueError("FaceAnalysis app is None")
    if img is None or getattr(img, "size", 0) == 0:
        raise FileNotFoundError("cannot decode empty image")
    faces = app.get(img)
    rows = []
    for f in faces:
        vec = np.asarray(f.normed_embedding, dtype=np.float32)
        dim = int(vec.size)
        if dim != EXPECTED_FACE_DIM:
            raise ValueError(f"unexpected face embedding dim={dim}; expected {EXPECTED_FACE_DIM}")
        x1, y1, x2, y2 = [float(v) for v in f.bbox]
        w, h = int(x2 - x1), int(y2 - y1)
        rows.append(
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": float(f.det_score),
                "face_w": w,
                "face_h": h,
                "dim": dim,
                "embedding": vec,
            }
        )
    return rows


def embed_image(app, path: Path) -> list[dict]:
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"cannot decode {path}")
    return embed_bgr(app, img)
