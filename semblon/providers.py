"""ObservationProvider boundary. FaceKit is the only identity provider.

CPU is the default record. GPU is only claimed when ORT lists CUDA /
DirectML / TensorRT (Azure is not GPU; present ≠ proven usable).
No second detector. load() does not silent-swap FaceKit.
"""

from __future__ import annotations

from dataclasses import dataclass

from semblon.engine import embed_bgr, load_app, select_execution_provider


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    modality: str
    device: str
    execution_provider: str
    pack_family: str


class FaceKitProvider:
    """First ObservationProvider. Identity embeddings stay FaceKit-only."""

    info = ProviderInfo(
        name="facekit",
        modality="face",
        device="cpu",
        execution_provider="CPUExecutionProvider",
        pack_family="insightface/buffalo_l",
    )

    def __init__(self):
        self._app = None
        self._runtime: dict | None = None

    def load(self, det_size: tuple[int, int] = (640, 640), *, prefer_gpu: bool = False):
        self._app = load_app(det_size, prefer_gpu=prefer_gpu)
        sel = getattr(self._app, "_semblon_ep", None) or select_execution_provider(
            prefer_gpu=prefer_gpu
        )
        self._runtime = {
            "provider": self.info.name,
            "modality": self.info.modality,
            "device": sel.get("device", "cpu"),
            "execution_provider": sel.get("chosen", "CPUExecutionProvider"),
            "pack_family": self.info.pack_family,
            "note": sel.get("note"),
        }
        return self

    @property
    def app(self):
        if self._app is None:
            raise RuntimeError("FaceKitProvider.load() has not run")
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


def weights_status() -> dict:
    """Where buffalo_l lives. Does not download. Does not bundle."""
    from pathlib import Path

    root = Path.home() / ".insightface" / "models" / "buffalo_l"
    present = sorted(p.name for p in root.glob("*.onnx")) if root.is_dir() else []
    return {
        "dir": str(root),
        "present": present,
        "onnx_count": len(present),
        "bundled": False,
        "redistributable": False,
        "note": "internal evaluation only; first ingest may download via InsightFace",
    }
