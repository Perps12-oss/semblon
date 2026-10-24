"""Experimental YuNet + SFace inference backends (lab only).

Production identity remains ``semblon.engine.load_app`` / ``embed_bgr`` via
OpenCV ``FaceDetectorYN`` + ``FaceRecognizerSF``. These adapters exist to
measure native ARM64 ONNX Runtime and alternate OpenCV DNN wiring without
changing the production path, thresholds, or model files.
"""

from __future__ import annotations

from semblon.experimental.inference.backends import (
    BackendName,
    InferenceBackend,
    TimedEmbed,
    available_backends,
    load_backend,
)

__all__ = [
    "BackendName",
    "InferenceBackend",
    "TimedEmbed",
    "available_backends",
    "load_backend",
]
