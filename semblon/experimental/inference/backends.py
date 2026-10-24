"""Factory for experimental inference backends. Production path untouched."""

from __future__ import annotations

from typing import Literal, Protocol

from semblon.experimental.inference.backends_base import TimedEmbed

BackendName = Literal["opencv_dnn", "ort_yunet_sface"]


class InferenceBackend(Protocol):
    name: str

    def info(self) -> dict: ...

    def embed_bgr_timed(self, img) -> TimedEmbed: ...


def available_backends() -> list[str]:
    names = ["opencv_dnn", "ort_yunet_sface"]
    # OpenCV DNN face APIs require a build with BUILD_opencv_dnn=ON.
    try:
        import cv2

        if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
            names = [n for n in names if n != "opencv_dnn"]
    except Exception:
        names = [n for n in names if n != "opencv_dnn"]
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        names = [n for n in names if n != "ort_yunet_sface"]
    return names


def load_backend(
    name: BackendName,
    *,
    detect_long_side: int | None = None,
    **kwargs,
) -> InferenceBackend:
    if name == "opencv_dnn":
        from semblon.experimental.inference.opencv_dnn_backend import OpenCVDNNBackend

        return OpenCVDNNBackend(detect_long_side=detect_long_side, **kwargs)
    if name == "ort_yunet_sface":
        from semblon.experimental.inference.ort_backend import ORTYuNetSFaceBackend

        return ORTYuNetSFaceBackend(detect_long_side=detect_long_side, **kwargs)
    raise ValueError(f"unknown experimental backend: {name!r}")
