"""YuNet + SFace identity pack loader. Local ONNX only — Semblon never downloads."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import cv2
import numpy as np

from semblon import ADAPTER_VERSION
from semblon.identity_config import (
    DET_SCORE_MIN,
    DET_SIZE,
    EXPECTED_FACE_DIM,
    NMS_THRESHOLD,
    PACK_FAMILY,
    SFACE_ONNX,
    TOP_K,
    YUNET_ONNX_FALLBACK,
    YUNET_ONNX_PREFERRED,
)

# Re-export for callers that imported PACK_FAMILY from engine.
__all__ = [
    "PACK_FAMILY",
    "EXPECTED_FACE_DIM",
    "ModelPackError",
    "FaceSession",
    "load_app",
    "embed_bgr",
    "embed_image",
    "assert_face_pack_ready",
    "accept_local_face_pack",
    "face_pack_dir",
    "discover_weight_hashes",
    "pack_id",
    "current_identity_space",
    "identity_space_mismatch",
    "select_execution_provider",
    "process_arch",
    "process_execution",
]


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
    """native vs emulated. x64 Python on ARM64 Windows is always emulated."""
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


def face_pack_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    env = (os.environ.get("SEMBLON_FACE_PACK") or os.environ.get("FACEKIT_PACK_DIR") or "").strip()
    if env:
        return Path(env)
    return Path.home() / ".semblon" / "models" / "yunet_sface"


def discover_weight_hashes(root: Path | None = None) -> dict[str, str]:
    home = face_pack_dir(root)
    out: dict[str, str] = {}
    if not home.is_dir():
        return out
    for p in sorted(home.glob("*.onnx")):
        out[p.name] = _sha256_file(p)
    return out


def pack_id(engine_version: str, weight_hashes: dict[str, str]) -> str:
    """Content-address pack. Digest stays 16 hex (frozen identity key — do not widen)."""
    if not weight_hashes:
        digest = "unhashed"
    else:
        blob = "".join(f"{k}:{v};" for k, v in sorted(weight_hashes.items()))
        digest = hashlib.sha256(blob.encode()).hexdigest()[:16]
    return f"{PACK_FAMILY}@{engine_version}/adapter-{ADAPTER_VERSION}/sha256:{digest}"


def current_identity_space() -> dict:
    """Live YuNet+SFace space. Digest width stays 16 hex. Call after weights are loaded."""
    import onnxruntime as ort

    hashes = discover_weight_hashes()
    eng_ver = f"opencv-{getattr(cv2, '__version__', 'unknown')}"
    return {
        "pack_id": pack_id(eng_ver, hashes),
        "ort_version": getattr(ort, "__version__", None),
        "opencv_version": getattr(cv2, "__version__", None),
        "insightface_version": None,
        "identity_engine": "yunet_sface",
        "weights_present": bool(hashes),
    }


def identity_space_mismatch(
    run_pack: str | None,
    run_ort: str | None,
    run_runtime_json: str | dict | None,
    *,
    live: dict | None = None,
) -> str | None:
    """Why resume or identify must refuse this run, or None when the space matches."""
    space = live if live is not None else current_identity_space()
    live_pack = str(space.get("pack_id") or "")
    stored_pack = str(run_pack or "")
    if stored_pack != live_pack:
        return f"pack_id mismatch: run {stored_pack} live {live_pack}"
    if run_ort:
        live_ort = str(space.get("ort_version") or "")
        if live_ort != str(run_ort):
            return f"ort_version mismatch: run {run_ort} live {live_ort}"
    runtime = run_runtime_json
    if isinstance(runtime, str):
        try:
            runtime = json.loads(runtime or "{}")
        except json.JSONDecodeError:
            runtime = {}
    if not isinstance(runtime, dict):
        runtime = {}
    stored_cv = runtime.get("opencv_version")
    if stored_cv:
        live_cv = str(space.get("opencv_version") or "")
        if live_cv != str(stored_cv):
            return f"opencv_version mismatch: run {stored_cv} live {live_cv}"
    return None


def onnx_providers() -> list[str]:
    try:
        import onnxruntime as ort

        return list(ort.get_available_providers())
    except Exception:
        return ["CPUExecutionProvider"]


def select_execution_provider(*, prefer_gpu: bool = True) -> dict:
    """Honest EP listing. YuNet/SFace use OpenCV DNN; ORT is still reported for runtime honesty."""
    available = onnx_providers()
    gpu_eps = [p for p in GPU_EP_NAMES if p in available]
    azure_listed = [p for p in NON_GPU_ACCEL_PROVIDERS if p in available]
    chosen = "CPUExecutionProvider"
    gpu = False
    if prefer_gpu and gpu_eps:
        chosen = gpu_eps[0]
        gpu = True
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
            "Identity inference uses OpenCV FaceDetectorYN + FaceRecognizerSF (CPU DNN). "
            "ORT GPU listing does not swap the YuNet/SFace pack."
        ),
    }


def product_prefer_gpu() -> bool:
    return bool(select_execution_provider(prefer_gpu=True)["gpu"])


def gpu_product_status() -> dict:
    rec = select_execution_provider(prefer_gpu=True)
    prefer = bool(rec["gpu"])
    if prefer:
        copy = (
            f"GPU EP listed: {rec['chosen']}. Identity path remains OpenCV DNN CPU "
            "unless a future decision wires DNN CUDA. Listed ≠ proven usable."
        )
    else:
        azure_note = ""
        if rec.get("azure_listed"):
            azure_note = " AzureExecutionProvider is listed but is not GPU."
        copy = (
            "No CUDA/DirectML/TensorRT EP listed. Identity path is OpenCV DNN CPU."
            f"{azure_note}"
        )
    return {
        **rec,
        "prefer_gpu": prefer,
        "product_path": "opencv_dnn_cpu",
        "copy": copy,
    }


def format_execution_status_lines() -> list[str]:
    st = gpu_product_status()
    lines = [
        "Provider: YuNet + SFace (OpenCV Zoo) — FaceKit/buffalo_l retired from production",
        f"Device: {st['device']}  reported_ORT_EP: {st['chosen']}  gpu={st['gpu']}",
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


class ModelPackError(RuntimeError):
    """Local face-pack refusal. Semblon does not download identity weights."""


PACK_OPT_IN = "SEMBLON_ALLOW_FACE_PACK"
PACK_PIN_NAME = "semblon-pack-pin.json"


def assert_single_opencv() -> None:
    """Two cv2 builds in one process is a Windows access-violation setup."""
    from importlib.metadata import distributions

    names = set()
    for dist in distributions():
        label = dist.metadata.get("Name")
        if label:
            names.add(label.lower())
    extras = [name for name in ("opencv-python", "opencv-contrib-python") if name in names]
    if extras and "opencv-python-headless" in names:
        raise ModelPackError(
            "opencv-python is installed beside opencv-python-headless. "
            "Uninstall opencv-python so only the headless build remains."
        )


def _read_pack_pin(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelPackError(f"face pack pin is unreadable: {path.name}") from exc
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict) or not files or not payload.get("opt_in"):
        raise ModelPackError(
            "face pack is not opted in. Run: semblon lab pack-accept"
        )
    return {str(name): str(digest).lower() for name, digest in files.items()}


def _resolve_yunet_path(home: Path) -> Path:
    preferred = home / YUNET_ONNX_PREFERRED
    fallback = home / YUNET_ONNX_FALLBACK
    if preferred.is_file():
        return preferred
    if fallback.is_file():
        return fallback
    raise ModelPackError(
        "YuNet ONNX missing. Place "
        f"{YUNET_ONNX_PREFERRED} or {YUNET_ONNX_FALLBACK} under {home}, "
        "then run: semblon lab pack-accept. Semblon does not download weights. "
        "See docs/IDENTITY-PACK.md."
    )


def _resolve_sface_path(home: Path) -> Path:
    path = home / SFACE_ONNX
    if path.is_file():
        return path
    raise ModelPackError(
        f"SFace ONNX missing ({SFACE_ONNX}). Place it under {home}, "
        "then run: semblon lab pack-accept. Semblon does not download weights. "
        "See docs/IDENTITY-PACK.md."
    )


def assert_face_pack_ready(root: Path | None = None) -> dict[str, str]:
    """Refuse to load unless YuNet + SFace ONNX files are present and pinned.

    Missing weights are an error. This function does not download them.
    """
    if os.environ.get(PACK_OPT_IN) == "0":
        raise ModelPackError(f"{PACK_OPT_IN}=0; face pack load refused")
    home = face_pack_dir(root)
    yunet = _resolve_yunet_path(home)
    sface = _resolve_sface_path(home)
    required = {yunet.name, sface.name}
    onnx = sorted(home.glob("*.onnx")) if home.is_dir() else []
    names = {p.name for p in onnx}
    if not required.issubset(names):
        missing = ", ".join(sorted(required - names))
        raise ModelPackError(
            f"YuNet+SFace pack incomplete (missing {missing}). "
            "Semblon does not download weights. See docs/IDENTITY-PACK.md, "
            "then: semblon lab pack-accept"
        )
    pin_path = home / PACK_PIN_NAME
    if not pin_path.is_file():
        raise ModelPackError(
            "face pack has no local pin. Semblon does not download weights. "
            "Run: semblon lab pack-accept"
        )
    expected = _read_pack_pin(pin_path)
    actual = {path.name: _sha256_file(path) for path in onnx if path.name in required}
    # Pin may include only required files, or all onnx in the directory.
    for name, digest in actual.items():
        if name not in expected:
            raise ModelPackError(
                f"face pack pin missing {name}. Re-run: semblon lab pack-accept"
            )
        if expected[name] != digest:
            raise ModelPackError("YuNet/SFace ONNX hashes do not match the pinned set")
    for name in expected:
        if name.endswith(".onnx") and name not in actual and name in required:
            raise ModelPackError(f"pinned ONNX missing on disk: {name}")
    return actual


def accept_local_face_pack(root: Path | None = None) -> dict:
    """Record hashes of required YuNet + SFace ONNX files. Does not download."""
    home = face_pack_dir(root)
    yunet = _resolve_yunet_path(home)
    sface = _resolve_sface_path(home)
    files = {
        yunet.name: _sha256_file(yunet),
        sface.name: _sha256_file(sface),
    }
    pin = {
        "opt_in": True,
        "engine": "yunet_sface",
        "pack_family": PACK_FAMILY,
        "files": files,
    }
    dest = home / PACK_PIN_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(pin, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "opt_in": True,
        "engine": "yunet_sface",
        "files": len(files),
        "pin": dest.name,
        "dir": str(home),
    }


class FaceSession:
    """OpenCV YuNet detector + SFace recogniser. Replaces InsightFace FaceAnalysis."""

    def __init__(
        self,
        detector: cv2.FaceDetectorYN,
        recognizer: cv2.FaceRecognizerSF,
        *,
        det_size: tuple[int, int],
        yunet_path: Path,
        sface_path: Path,
    ):
        self.detector = detector
        self.recognizer = recognizer
        self.det_size = det_size
        self.yunet_path = yunet_path
        self.sface_path = sface_path
        self._semblon_ep: dict | None = None

    def get(self, img: np.ndarray) -> list:
        """Compatibility shim: unused by embed_bgr; kept for rare callers."""
        return embed_bgr(self, img)


def load_app(det_size: tuple[int, int] = DET_SIZE, *, prefer_gpu: bool = False) -> FaceSession:
    """Load pinned YuNet + SFace. OpenCV DNN path is CPU; prefer_gpu is recorded only."""
    assert_single_opencv()
    home = face_pack_dir()
    assert_face_pack_ready(home)
    yunet = _resolve_yunet_path(home)
    sface = _resolve_sface_path(home)
    w, h = int(det_size[0]), int(det_size[1])
    try:
        detector = cv2.FaceDetectorYN.create(
            str(yunet),
            "",
            (w, h),
            float(DET_SCORE_MIN),
            float(NMS_THRESHOLD),
            int(TOP_K),
        )
        recognizer = cv2.FaceRecognizerSF.create(str(sface), "")
    except cv2.error as exc:
        raise ModelPackError(
            f"failed to load YuNet/SFace ONNX via OpenCV: {exc}. "
            "Confirm the exact Zoo files and a working opencv-python-headless build."
        ) from exc
    session = FaceSession(
        detector,
        recognizer,
        det_size=(w, h),
        yunet_path=yunet,
        sface_path=sface,
    )
    session._semblon_ep = select_execution_provider(prefer_gpu=prefer_gpu)
    return session


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    out = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(out))
    if norm <= 0.0:
        raise ValueError("SFace feature has zero norm")
    return out / norm


def embed_bgr(app: FaceSession, img) -> list[dict]:
    """YuNet detect + SFace alignCrop/feature on a BGR array. No disk write."""
    if app is None:
        raise ValueError("FaceSession app is None")
    if img is None or getattr(img, "size", 0) == 0:
        raise FileNotFoundError("cannot decode empty image")
    if not isinstance(app, FaceSession):
        # Tests sometimes pass a dummy object and patch this function entirely.
        raise TypeError("embed_bgr expects a FaceSession from load_app()")

    height, width = img.shape[:2]
    app.detector.setInputSize((int(width), int(height)))
    _retval, faces = app.detector.detect(img)
    rows: list[dict] = []
    if faces is None:
        return rows
    for face in faces:
        face = np.asarray(face, dtype=np.float32).reshape(-1)
        if face.size < 15:
            continue
        x, y, w, h = float(face[0]), float(face[1]), float(face[2]), float(face[3])
        score = float(face[14]) if face.size > 14 else float(face[-1])
        try:
            aligned = app.recognizer.alignCrop(img, face)
            feat = app.recognizer.feature(aligned)
        except cv2.error:
            continue
        vec = _l2_normalize(np.asarray(feat, dtype=np.float32))
        dim = int(vec.size)
        if dim != EXPECTED_FACE_DIM:
            raise ValueError(
                f"unexpected face embedding dim={dim}; expected {EXPECTED_FACE_DIM}"
            )
        x1, y1, x2, y2 = x, y, x + w, y + h
        rows.append(
            {
                "bbox": (x1, y1, x2, y2),
                "det_score": score,
                "face_w": int(w),
                "face_h": int(h),
                "dim": dim,
                "embedding": vec,
            }
        )
    return rows


def embed_image(app: FaceSession, path: Path) -> list[dict]:
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"cannot decode {path}")
    return embed_bgr(app, img)
