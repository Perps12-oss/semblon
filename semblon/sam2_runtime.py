"""Local SAM 2 spatial discovery. Optional, explicit, never auto-downloaded.

The rest of Semblon sees region dicts (bbox, mask, confidence). It does not
branch on whether those regions came from SAM 2, OpenCV, or a later provider.

Checkpoint contract (existing env names):

- ``SEMBLON_SAM2_CHECKPOINT`` — local ``.pt`` file. Required.
- ``SEMBLON_SAM2_CONFIG`` — Hydra config name. Inferred from the filename when unset.
- ``SEMBLON_SAM2_SHA256`` — optional expected digest. Mismatch is a load failure.

States (a package import is never READY):

- ``SAM2_NOT_INSTALLED``
- ``SAM2_AVAILABLE`` — package imports; weights file is present; model not loaded
- ``SAM2_NOT_CONFIGURED`` — no checkpoint path
- ``SAM2_WEIGHTS_MISSING`` — path set, file absent
- ``SAM2_LOAD_FAILURE``
- ``SAM2_READY`` — ``build_sam2`` succeeded for this process

Official package: ``facebookresearch/sam2`` (distribution name ``SAM-2``).
Device is CUDA when ``torch.cuda`` is available, otherwise CPU.
DirectML is recorded if importable and is not used: SAM 2's official runtime
does not execute on DirectML.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from semblon.engine import process_arch, process_execution
from semblon.visual_segment import LABEL_TYPE_REGION, LABEL_TYPE_UNKNOWN

SAM2_NOT_INSTALLED = "SAM2_NOT_INSTALLED"
SAM2_AVAILABLE = "SAM2_AVAILABLE"
SAM2_NOT_CONFIGURED = "SAM2_NOT_CONFIGURED"
SAM2_WEIGHTS_MISSING = "SAM2_WEIGHTS_MISSING"
SAM2_LOAD_FAILURE = "SAM2_LOAD_FAILURE"
SAM2_READY = "SAM2_READY"

# Official config names shipped inside facebookresearch/sam2.
_CONFIG_BY_STEM = {
    "sam2.1_hiera_tiny": "configs/sam2.1/sam2.1_hiera_t.yaml",
    "sam2.1_hiera_small": "configs/sam2.1/sam2.1_hiera_s.yaml",
    "sam2.1_hiera_base_plus": "configs/sam2.1/sam2.1_hiera_b+.yaml",
    "sam2.1_hiera_large": "configs/sam2.1/sam2.1_hiera_l.yaml",
    "sam2_hiera_tiny": "configs/sam2/sam2_hiera_t.yaml",
    "sam2_hiera_small": "configs/sam2/sam2_hiera_s.yaml",
    "sam2_hiera_base_plus": "configs/sam2/sam2_hiera_b+.yaml",
    "sam2_hiera_large": "configs/sam2/sam2_hiera_l.yaml",
}

_LOCK = threading.Lock()
_SESSION: "Sam2Session | None" = None
_LOAD_ERROR: str = ""


@dataclass
class Sam2Status:
    state: str
    detail: str = ""
    package_version: str = ""
    checkpoint: str = ""
    config: str = ""
    runtime: dict[str, Any] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.state == SAM2_READY


@dataclass
class Sam2Session:
    model: Any
    generator: Any
    predictor: Any
    device: str
    checkpoint: str
    config: str
    package_version: str
    runtime: dict[str, Any]


def checkpoint_path() -> Path | None:
    raw = os.environ.get("SEMBLON_SAM2_CHECKPOINT", "").strip()
    if not raw:
        return None
    return Path(raw)


def config_name_for(checkpoint: Path | None) -> str:
    explicit = os.environ.get("SEMBLON_SAM2_CONFIG", "").strip()
    if explicit:
        return explicit
    if checkpoint is None:
        return ""
    return _CONFIG_BY_STEM.get(checkpoint.stem, "")


def runtime_report() -> dict[str, Any]:
    """Native vs emulated, and the device SAM 2 will actually use."""
    report: dict[str, Any] = {
        "process_arch": process_arch(),
        "execution": process_execution(),
        "device": "cpu",
        "accelerator": "cpu",
        "directml_importable": False,
        "directml_used": False,
        "torch": "",
    }
    try:
        import torch

        report["torch"] = str(torch.__version__)
        if bool(torch.cuda.is_available()):
            report["device"] = "cuda"
            report["accelerator"] = "cuda"
    except Exception as exc:  # noqa: BLE001 — capability report, not a crash
        report["torch_error"] = type(exc).__name__
    try:
        import torch_directml  # noqa: F401

        report["directml_importable"] = True
    except Exception:
        report["directml_importable"] = False
    return report


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("SAM-2")
    except Exception:
        try:
            import sam2

            return str(getattr(sam2, "__version__", "installed"))
        except Exception:
            return ""


def sam2_importable() -> bool:
    try:
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator  # noqa: F401
        from sam2.build_sam import build_sam2  # noqa: F401
    except Exception:
        return False
    return True


def probe_sam2(*, attempt_load: bool = False, builder: Callable | None = None) -> Sam2Status:
    """Report one explicit state. READY only after a successful load."""
    runtime = runtime_report()
    if not sam2_importable():
        return Sam2Status(
            state=SAM2_NOT_INSTALLED,
            detail="sam2 package is not importable",
            runtime=runtime,
        )
    version = _package_version()
    path = checkpoint_path()
    if path is None:
        return Sam2Status(
            state=SAM2_NOT_CONFIGURED,
            detail="SEMBLON_SAM2_CHECKPOINT is unset",
            package_version=version,
            runtime=runtime,
        )
    if not path.is_file():
        return Sam2Status(
            state=SAM2_WEIGHTS_MISSING,
            detail=f"checkpoint file not found: {path}",
            package_version=version,
            checkpoint=str(path),
            runtime=runtime,
        )
    config = config_name_for(path)
    if not config:
        return Sam2Status(
            state=SAM2_NOT_CONFIGURED,
            detail="SEMBLON_SAM2_CONFIG is unset and the checkpoint name is not recognised",
            package_version=version,
            checkpoint=str(path),
            runtime=runtime,
        )
    expected = os.environ.get("SEMBLON_SAM2_SHA256", "").strip()
    if expected:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest.lower() != expected.lower():
            return Sam2Status(
                state=SAM2_LOAD_FAILURE,
                detail="checkpoint sha256 does not match SEMBLON_SAM2_SHA256",
                package_version=version,
                checkpoint=str(path),
                config=config,
                runtime=runtime,
            )
    if path.stat().st_size < 1024:
        return Sam2Status(
            state=SAM2_LOAD_FAILURE,
            detail="checkpoint file is too small to be a SAM 2 weight file",
            package_version=version,
            checkpoint=str(path),
            config=config,
            runtime=runtime,
        )
    if not attempt_load:
        return Sam2Status(
            state=SAM2_AVAILABLE,
            detail="package imports and the checkpoint file is present; model is not loaded",
            package_version=version,
            checkpoint=str(path),
            config=config,
            runtime=runtime,
        )
    try:
        session = ensure_session(builder=builder)
    except Exception as exc:  # noqa: BLE001 — load failure is a state, not a crash
        return Sam2Status(
            state=SAM2_LOAD_FAILURE,
            detail=f"{type(exc).__name__}: {exc}",
            package_version=version,
            checkpoint=str(path),
            config=config,
            runtime=runtime,
        )
    return Sam2Status(
        state=SAM2_READY,
        detail="SAM 2 weights loaded",
        package_version=session.package_version or version,
        checkpoint=session.checkpoint,
        config=session.config,
        runtime=session.runtime,
    )


def ensure_session(*, builder: Callable | None = None) -> Sam2Session:
    """Load the official SAM 2 model once per process. Does not download."""
    global _SESSION, _LOAD_ERROR
    path = checkpoint_path()
    config = config_name_for(path) if path is not None else ""
    with _LOCK:
        if (
            _SESSION is not None
            and path is not None
            and _SESSION.checkpoint == str(path)
            and _SESSION.config == config
            and builder is None
        ):
            return _SESSION
        if path is None or not path.is_file() or not config:
            raise RuntimeError("SAM 2 checkpoint is not configured")
        runtime = runtime_report()
        device = str(runtime.get("device") or "cpu")
        try:
            if builder is not None:
                model, generator, predictor = builder(config, str(path), device)
            else:
                model, generator, predictor = _build_official(config, str(path), device)
        except Exception as exc:
            _LOAD_ERROR = f"{type(exc).__name__}: {exc}"
            _SESSION = None
            raise
        session = Sam2Session(
            model=model,
            generator=generator,
            predictor=predictor,
            device=device,
            checkpoint=str(path),
            config=config,
            package_version=_package_version(),
            runtime=runtime,
        )
        _SESSION = session
        _LOAD_ERROR = ""
        return session


def reset_session_for_tests() -> None:
    global _SESSION, _LOAD_ERROR
    with _LOCK:
        _SESSION = None
        _LOAD_ERROR = ""


def _build_official(config: str, checkpoint: str, device: str):
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    model = build_sam2(config, checkpoint, device=device)
    points = int(os.environ.get("SEMBLON_SAM2_POINTS_PER_SIDE", "16"))
    crops = int(os.environ.get("SEMBLON_SAM2_CROP_LAYERS", "1"))
    # High box NMS keeps nested parts. Near-duplicates are removed later.
    generator = SAM2AutomaticMaskGenerator(
        model,
        points_per_side=max(4, points),
        points_per_batch=int(os.environ.get("SEMBLON_SAM2_POINTS_PER_BATCH", "8")),
        pred_iou_thresh=float(os.environ.get("SEMBLON_SAM2_PRED_IOU", "0.7")),
        stability_score_thresh=float(os.environ.get("SEMBLON_SAM2_STABILITY", "0.85")),
        box_nms_thresh=float(os.environ.get("SEMBLON_SAM2_BOX_NMS", "0.95")),
        crop_n_layers=max(0, crops),
        min_mask_region_area=0,
        output_mode="binary_mask",
    )
    predictor = SAM2ImagePredictor(model)
    return model, generator, predictor


def _mask_bbox(mask: np.ndarray) -> tuple[float, float, float, float] | None:
    ys, xs = np.where(mask)
    if xs.size == 0:
        return None
    return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)


def _downsample_bool(mask: np.ndarray, limit: int = 160) -> np.ndarray:
    m = np.asarray(mask).astype(bool)
    h, w = m.shape[:2]
    step = max(1, int(max(h, w) / limit))
    if step == 1:
        return m
    return m[::step, ::step]


def _mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    if inter <= 0:
        return 0.0
    union = np.logical_or(a, b).sum()
    return float(inter) / float(union) if union else 0.0


def generate_regions(image: np.ndarray) -> tuple[list[dict], dict]:
    """Class-agnostic masks. Labels stay unnamed; naming is a later stage.

    Returns region dicts plus discovery stats. Does not call naming models.
    """
    t0 = time.perf_counter()
    status = probe_sam2(attempt_load=True)
    if not status.ready:
        raise RuntimeError(status.detail or status.state)
    session = ensure_session()
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("SAM 2 discovery expects an HxWx3 BGR image")
    rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])
    if rgb.dtype != np.uint8:
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    h, w = rgb.shape[:2]
    t_norm0 = time.perf_counter()
    # The official generator resizes internally. Coordinates stay in this image.
    normalize_s = time.perf_counter() - t_norm0
    raw = session.generator.generate(rgb)
    n_raw = len(raw)
    quality: list[tuple[float, dict, np.ndarray]] = []
    removed_quality = 0
    min_frac = float(os.environ.get("SEMBLON_SAM2_MIN_AREA_FRAC", "0.002"))
    max_frac = float(os.environ.get("SEMBLON_SAM2_MAX_AREA_FRAC", "0.92"))
    total = float(max(h * w, 1))
    for item in raw:
        mask = np.asarray(item.get("segmentation"))
        if mask.shape[:2] != (h, w):
            removed_quality += 1
            continue
        mask_b = mask.astype(bool)
        area = int(mask_b.sum())
        frac = area / total
        score = float(item.get("predicted_iou") or 0.0)
        stability = float(item.get("stability_score") or 0.0)
        if frac < min_frac or frac > max_frac or area < 32:
            removed_quality += 1
            continue
        if score < float(os.environ.get("SEMBLON_SAM2_MIN_SCORE", "0.55")):
            removed_quality += 1
            continue
        bbox = _mask_bbox(mask_b)
        if bbox is None:
            removed_quality += 1
            continue
        small = _downsample_bool(mask_b)
        quality.append(
            (
                score,
                {
                    "bbox": bbox,
                    "label": "region",
                    "label_type": LABEL_TYPE_UNKNOWN,
                    "confidence": max(score, min(0.99, 0.5 * score + 0.5 * stability)),
                    "area_frac": frac,
                    "mask": mask_b.astype(np.uint8) * 255,
                    "source_provider": "sam2",
                    "payload": {
                        "discovery": "sam2_automatic",
                        "naming": "pending",
                        "predicted_iou": score,
                        "stability_score": stability,
                    },
                },
                small,
            )
        )
    quality.sort(key=lambda row: -row[0])
    kept: list[tuple[dict, np.ndarray]] = []
    removed_dedupe = 0
    for _score, reg, small in quality:
        duplicate = False
        for _other, other_small in kept:
            if small.shape != other_small.shape:
                continue
            if _mask_iou(small, other_small) >= 0.90:
                duplicate = True
                break
        if duplicate:
            removed_dedupe += 1
            continue
        kept.append((reg, small))
    nested = 0
    for idx, (reg, small) in enumerate(kept):
        area = int(small.sum())
        best_parent = None
        best_area = None
        for jdx, (other, other_small) in enumerate(kept):
            if idx == jdx or small.shape != other_small.shape:
                continue
            other_area = int(other_small.sum())
            if other_area <= area:
                continue
            inter = int(np.logical_and(small, other_small).sum())
            if area > 0 and inter / float(area) >= 0.80 and area <= 0.90 * other_area:
                if best_area is None or other_area < best_area:
                    best_parent = jdx
                    best_area = other_area
        if best_parent is not None:
            reg["payload"] = {**reg["payload"], "nested": True}
            nested += 1
    regions = [reg for reg, _small in kept]
    stats = {
        "sam2_state": SAM2_READY,
        "n_raw": n_raw,
        "n_quality_kept": len(quality),
        "n_removed_quality": removed_quality,
        "n_removed_dedupe": removed_dedupe,
        "n_nested_retained": nested,
        "n_regions": len(regions),
        "discovery_s": time.perf_counter() - t0,
        "normalize_s": normalize_s,
        "device": session.device,
        "execution": session.runtime.get("execution"),
        "process_arch": session.runtime.get("process_arch"),
        "checkpoint": session.checkpoint,
        "config": session.config,
        "package_version": session.package_version,
    }
    return regions, stats


class Sam2SpatialProvider:
    """Discovery provider. Implements the semantic-visual protocol.

    ``discover_regions`` returns unnamed spatial regions. Concept naming is
    intentionally empty here so a later propose/bind/abstain stage can run.
    """

    def __init__(self) -> None:
        runtime = runtime_report()
        path = checkpoint_path()
        self.info = _info(path, runtime)
        self.last_stats: dict = {}

    def discover_regions(self, image: np.ndarray) -> list[dict]:
        regions, stats = generate_regions(image)
        self.last_stats = stats
        return regions

    def discover_concepts(self, image: np.ndarray, *, regions: list[dict] | None = None) -> list[dict]:
        del image, regions
        return []

    def segment_concept(self, image: np.ndarray, concept: str) -> list[dict]:
        del image, concept
        return []

    def refine_from_point(self, image: np.ndarray, x: int, y: int) -> dict | None:
        return predict_point(image, x, y)

    def refine_from_box(
        self, image: np.ndarray, bbox: tuple[float, float, float, float]
    ) -> dict | None:
        return predict_box(image, bbox)


def _info(path: Path | None, runtime: dict):
    from semblon.semantic_visual import SemanticVisualInfo

    stem = path.stem if path is not None else "sam2"
    return SemanticVisualInfo(
        name="sam2",
        device=str(runtime.get("device") or "cpu"),
        model_id=stem,
        model_version="1",
    )


def discovery_cache_identity() -> dict[str, str]:
    """Cache key inputs. Does not load weights. Does not report READY."""
    status = probe_sam2(attempt_load=False)
    if status.state in {SAM2_AVAILABLE, SAM2_READY}:
        stem = Path(status.checkpoint).stem if status.checkpoint else "sam2"
        return {"provider": "sam2", "model_id": stem, "model_version": "1"}
    return {"provider": "local_opencv", "model_id": "local-opencv", "model_version": "1"}


def provider_for_discovery():
    """SAM 2 when it actually loads. Otherwise the existing OpenCV provider.

    The fallback is explicit on the returned status. It is not a silent success.
    """
    from semblon.semantic_visual import LocalSemanticVisualProvider

    status = probe_sam2(attempt_load=False)
    if status.state != SAM2_AVAILABLE:
        provider = LocalSemanticVisualProvider()
        provider.last_stats = {"sam2_state": status.state, "sam2_detail": status.detail}
        return provider, status
    status = probe_sam2(attempt_load=True)
    if status.state == SAM2_READY:
        return Sam2SpatialProvider(), status
    provider = LocalSemanticVisualProvider()
    provider.last_stats = {"sam2_state": status.state, "sam2_detail": status.detail}
    return provider, status


def _predictor_ready():
    status = probe_sam2(attempt_load=True)
    if not status.ready:
        return None
    return ensure_session()


def predict_point(image: np.ndarray, x: int, y: int) -> dict | None:
    """Point prompt on an already-configured checkpoint. None when not ready."""
    session = _predictor_ready()
    if session is None:
        return None
    arr = np.asarray(image)
    h, w = arr.shape[:2]
    if not (0 <= int(x) < w and 0 <= int(y) < h):
        return None
    try:
        rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])
        session.predictor.set_image(rgb)
        masks, scores, _ = session.predictor.predict(
            point_coords=np.array([[x, y]], dtype=np.float32),
            point_labels=np.array([1], dtype=np.int32),
            multimask_output=False,
        )
        mask = np.asarray(masks[0]) > 0
        bbox = _mask_bbox(mask)
        if bbox is None:
            return None
        return {
            "bbox": bbox,
            "label": "region",
            "label_type": LABEL_TYPE_REGION,
            "confidence": float(scores[0]) if scores is not None else 0.6,
            "mask": mask.astype(np.uint8) * 255,
            "source_provider": "sam2",
            "payload": {"refine": "sam2_point"},
        }
    except Exception:
        return None


def predict_box(image: np.ndarray, bbox: tuple[float, float, float, float]) -> dict | None:
    session = _predictor_ready()
    if session is None:
        return None
    arr = np.asarray(image)
    h, w = arr.shape[:2]
    x1 = int(max(0, min(w - 1, bbox[0])))
    y1 = int(max(0, min(h - 1, bbox[1])))
    x2 = int(max(0, min(w, bbox[2])))
    y2 = int(max(0, min(h, bbox[3])))
    if x2 <= x1 or y2 <= y1:
        return None
    try:
        rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])
        session.predictor.set_image(rgb)
        masks, scores, _ = session.predictor.predict(
            box=np.array([x1, y1, x2 - 1, y2 - 1], dtype=np.float32),
            multimask_output=False,
        )
        mask = np.asarray(masks[0]) > 0
        found = _mask_bbox(mask)
        if found is None:
            return None
        return {
            "bbox": found,
            "label": "region",
            "label_type": LABEL_TYPE_REGION,
            "confidence": float(scores[0]) if scores is not None else 0.6,
            "mask": mask.astype(np.uint8) * 255,
            "source_provider": "sam2",
            "payload": {"refine": "sam2_box"},
        }
    except Exception:
        return None
