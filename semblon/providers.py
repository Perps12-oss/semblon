"""ObservationProvider boundary. YuNet + SFace is the production identity provider.

CPU OpenCV DNN is the default record. No InsightFace / buffalo_l.
No second detector. load() does not silent-swap engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from semblon.engine import embed_bgr, face_pack_dir, load_app, select_execution_provider
from semblon.identity_config import PACK_FAMILY, PROVIDER_NAME


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    modality: str
    device: str
    execution_provider: str
    pack_family: str


class YuNetSFaceProvider:
    """Production identity ObservationProvider (YuNet detect + SFace embed)."""

    info = ProviderInfo(
        name=PROVIDER_NAME,
        modality="face",
        device="cpu",
        execution_provider="OpenCV_DNN_CPU",
        pack_family=PACK_FAMILY,
    )

    def __init__(self):
        self._app = None
        self._runtime: dict | None = None

    def load(self, det_size: tuple[int, int] | None = None, *, prefer_gpu: bool = False):
        from semblon.identity_config import DET_SIZE

        size = det_size if det_size is not None else DET_SIZE
        self._app = load_app(size, prefer_gpu=prefer_gpu)
        sel = getattr(self._app, "_semblon_ep", None) or select_execution_provider(
            prefer_gpu=prefer_gpu
        )
        self._runtime = {
            "provider": self.info.name,
            "modality": self.info.modality,
            "device": "cpu",
            "execution_provider": self.info.execution_provider,
            "ort_reported_ep": sel.get("chosen", "CPUExecutionProvider"),
            "pack_family": self.info.pack_family,
            "note": sel.get("note"),
        }
        return self

    @property
    def app(self):
        if self._app is None:
            raise RuntimeError("YuNetSFaceProvider.load() has not run")
        return self._app

    def observe_bgr(self, img) -> list[dict]:
        return embed_bgr(self.app, img)

    def as_runtime(self) -> dict:
        if self._runtime is not None:
            return dict(self._runtime)
        return {
            "provider": self.info.name,
            "modality": self.info.modality,
            "device": self.info.device,
            "execution_provider": self.info.execution_provider,
            "pack_family": self.info.pack_family,
            "note": "load() not run; advertised CPU defaults only",
        }


# Backward-compatible name for tests that still import FaceKitProvider.
FaceKitProvider = YuNetSFaceProvider


def weights_status() -> dict:
    """Where YuNet + SFace live. Does not download. Does not bundle."""
    root = face_pack_dir()
    present = sorted(p.name for p in root.glob("*.onnx")) if root.is_dir() else []
    return {
        "dir": str(root),
        "present": present,
        "onnx_count": len(present),
        "engine": "yunet_sface",
        "pack_family": PACK_FAMILY,
        "bundled": False,
        "redistributable": False,
        "note": (
            "BYO OpenCV Zoo YuNet + SFace. Semblon does not download or MSI-bundle "
            "weights until licence gate L PASS. See docs/IDENTITY-PACK.md."
        ),
    }
