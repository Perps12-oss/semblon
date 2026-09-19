"""ObservationProvider boundary. FaceKit is the only identity provider.

CPU is recorded. GPU is not claimed. No second detector.
"""

from __future__ import annotations

from dataclasses import dataclass

from semblon.engine import embed_bgr, load_app


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

    def load(self, det_size: tuple[int, int] = (640, 640)):
        self._app = load_app(det_size)
        return self

    @property
    def app(self):
        if self._app is None:
            raise RuntimeError("FaceKitProvider.load() has not run")
        return self._app

    def observe_bgr(self, img) -> list[dict]:
        return embed_bgr(self.app, img)

    def as_runtime(self) -> dict:
        return {
            "provider": self.info.name,
            "modality": self.info.modality,
            "device": self.info.device,
            "execution_provider": self.info.execution_provider,
            "pack_family": self.info.pack_family,
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
