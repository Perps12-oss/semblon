"""Spatial discovery. Not an ObservationProvider. Not identity.

SAM2-AMG is the first serious provider when local weights exist.
It is not the product. Classical colour regions are a coarse fallback.
Neither provider invents a name.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from semblon.visual.masks import MaskCand, area_of, connected_labels
from semblon.visual.model import VisualConfig

_SAM2_NOT_INSTALLED = "SAM2 is not installed. Discovery does not pretend otherwise."
_SAM2_PARAMS = {"box_nms_thresh": 0.95, "points_per_side": 16, "crop_n_layers": 0, "pred_iou_thresh": 0.7, "stability_score_thresh": 0.8}
_RUNTIME: dict = {"weights": None, "error": None, "generator": None, "config": None}


def sam2_weights_path() -> Path | None:
    """Local file only. Never downloads."""
    env = os.environ.get("SEMBLON_SAM2_WEIGHTS", "").strip()
    if env:
        path = Path(env)
        if path.is_file():
            return path
        return None
    root = Path.home() / ".cache" / "semblon" / "sam2"
    if not root.is_dir():
        return None
    found = sorted(root.glob("*.pt")) + sorted(root.glob("*.pth"))
    return found[0] if found else None


def clear_sam2_runtime() -> None:
    _RUNTIME["weights"] = None
    _RUNTIME["error"] = None
    _RUNTIME["generator"] = None
    _RUNTIME["config"] = None


def mark_sam2_failed(message: str, weights: str | None = None) -> None:
    _RUNTIME["error"] = message
    _RUNTIME["generator"] = None
    if weights is not None:
        _RUNTIME["weights"] = str(weights)


def sam2_capability() -> dict:
    try:
        import sam2  # type: ignore  # noqa: F401
    except Exception:
        return {"state": "UNAVAILABLE", "note": _SAM2_NOT_INSTALLED, "params": dict(_SAM2_PARAMS)}
    weights = sam2_weights_path()
    if weights is None:
        return {
            "state": "UNAVAILABLE",
            "note": "sam2 imports, but no local checkpoint (SEMBLON_SAM2_WEIGHTS or ~/.cache/semblon/sam2)",
            "params": dict(_SAM2_PARAMS),
        }
    if _RUNTIME.get("error") and _RUNTIME.get("weights") == str(weights):
        return {
            "state": "FAILED",
            "note": _RUNTIME["error"],
            "weights": str(weights),
            "params": dict(_SAM2_PARAMS),
        }
    return {
        "state": "READY",
        "note": f"local checkpoint {weights.name}; masks are candidates, not hover truth",
        "weights": str(weights),
        "params": dict(_SAM2_PARAMS),
    }


class ClassicalColorDiscovery:
    """Coarse regions from colour. PARTIAL. Does not name grass because it is green."""

    name = "classical"

    def capability(self) -> dict:
        return {"state": "PARTIAL", "note": "colour regions on a small grid; not semantic"}

    def discover(self, rgb: np.ndarray, config: VisualConfig) -> list[MaskCand]:
        h, w = rgb.shape[:2]
        scale = 96 / max(h, w)
        if scale < 1:
            sh, sw = max(1, int(h * scale)), max(1, int(w * scale))
            ys = np.linspace(0, h - 1, sh).astype(np.int32)
            xs = np.linspace(0, w - 1, sw).astype(np.int32)
            small = rgb[ys][:, xs].astype(np.float32)
        else:
            small = rgb.astype(np.float32)
            sh, sw = h, w
        pixels = small.reshape(-1, 3)
        k = min(5, len(pixels))
        rng = np.random.default_rng(0)
        centres = pixels[rng.choice(len(pixels), size=k, replace=False)].astype(np.float32)
        labels = np.zeros(len(pixels), dtype=np.int32)
        for _ in range(4):
            dist = ((pixels[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
            labels = dist.argmin(axis=1)
            for i in range(len(centres)):
                sel = pixels[labels == i]
                if len(sel):
                    centres[i] = sel.mean(axis=0)
        lab = labels.reshape(sh, sw)
        out: list[MaskCand] = []
        y_map = np.linspace(0, sh - 1, h).astype(np.int32)
        x_map = np.linspace(0, sw - 1, w).astype(np.int32)
        floor = max(1, int(config.min_area_frac * h * w * 0.5))
        for cid in np.unique(lab):
            comp = connected_labels(lab == cid)
            for lid in np.unique(comp):
                if lid == 0:
                    continue
                piece = comp == lid
                if int(piece.sum()) < 8:
                    continue
                full = piece[y_map][:, x_map]
                if area_of(full) < floor:
                    continue
                out.append(MaskCand(full, "classical", "color", 1.0, 1.0, "raw"))
        return out


class Sam2AmgDiscovery:
    """Automatic masks when a local checkpoint exists. Stock NMS is loosened.

    Returned masks are raw candidates. Containment-preserving dedupe happens
    later, in the engine, so a hood is not discarded for overlapping a person.
    """

    name = "sam2-amg"

    def capability(self) -> dict:
        return sam2_capability()

    def discover(self, rgb: np.ndarray, config: VisualConfig) -> tuple[list[MaskCand], str | None]:
        cap = self.capability()
        if cap["state"] != "READY":
            return [], None
        try:
            masks = _generate_sam2(rgb, cap["weights"])
        except Exception as exc:  # noqa: BLE001 — capability said ready; this run failed
            message = f"{type(exc).__name__}: {exc}"
            mark_sam2_failed(message, str(cap["weights"]))
            return [], message
        return masks, None


def _generate_sam2(rgb: np.ndarray, weights: str) -> list[MaskCand]:
    """Call SAM2 AMG. box_nms_thresh is high so nested parts survive to our dedupe.

    The generator is cached for this checkpoint. Stock box-NMS is not the product filter.
    """
    import torch
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    from sam2.build_sam import build_sam2

    config = _config_for(weights)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    key = (str(weights), config, device)
    if _RUNTIME.get("generator") is None or _RUNTIME.get("config") != key:
        model = build_sam2(config_file=config, ckpt_path=weights, device=device)
        _RUNTIME["generator"] = SAM2AutomaticMaskGenerator(
            model,
            points_per_side=_SAM2_PARAMS["points_per_side"],
            pred_iou_thresh=_SAM2_PARAMS["pred_iou_thresh"],
            stability_score_thresh=_SAM2_PARAMS["stability_score_thresh"],
            box_nms_thresh=_SAM2_PARAMS["box_nms_thresh"],
            crop_n_layers=_SAM2_PARAMS["crop_n_layers"],
        )
        _RUNTIME["config"] = key
        _RUNTIME["weights"] = str(weights)
        _RUNTIME["error"] = None
    records = _RUNTIME["generator"].generate(np.ascontiguousarray(rgb))
    out: list[MaskCand] = []
    for rec in records:
        seg = np.asarray(rec.get("segmentation"), dtype=bool)
        if seg.shape != rgb.shape[:2] or not seg.any():
            continue
        out.append(
            MaskCand(
                seg,
                "sam2",
                "amg",
                float(rec.get("stability_score") or 0.0),
                float(rec.get("predicted_iou") or 0.0),
                "raw",
            )
        )
    return out


def _config_for(weights: str) -> str:
    name = Path(weights).name.lower()
    family = "sam2.1" if ("sam2.1" in name or "2.1" in name) else "sam2"
    if "large" in name:
        size = "l"
    elif "base" in name or "b+" in name:
        size = "b+"
    elif "tiny" in name or "hiera_t" in name:
        size = "t"
    else:
        size = "s"
    if family == "sam2.1":
        return f"configs/sam2.1/sam2.1_hiera_{size}.yaml"
    return f"configs/sam2/sam2_hiera_{size}.yaml"
