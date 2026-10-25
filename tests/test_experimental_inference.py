"""Unit tests for experimental inference adapters (no production path edits)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from semblon.experimental.inference.align import align_crop, similarity_transform_matrix
from semblon.experimental.inference.backends import available_backends
from semblon.experimental.inference.yunet_decode import decode_yunet_outputs


def test_available_backends_lists_experimental_only():
    names = available_backends()
    assert "ort_yunet_sface" in names or "opencv_dnn" in names
    # Must not pretend to be the production provider registry.
    assert "yunet_sface" not in names


def test_similarity_transform_identity_ish():
    # Landmarks already at dst → near-identity scale/translation.
    dst = np.array(
        [
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        dtype=np.float64,
    )
    mat = similarity_transform_matrix(dst)
    assert mat.shape == (2, 3)
    # Diagonal scale near 1, translation near 0.
    assert abs(mat[0, 0] - 1.0) < 0.05
    assert abs(mat[1, 1] - 1.0) < 0.05


def test_align_crop_shape():
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[40:160, 40:160] = 200
    face = np.array(
        [
            40,
            40,
            120,
            120,
            70,
            80,
            110,
            80,
            90,
            100,
            75,
            130,
            105,
            130,
            0.99,
        ],
        dtype=np.float32,
    )
    cropped = align_crop(img, face)
    assert cropped.shape == (112, 112, 3)


def test_yunet_decode_empty():
    # All-zero heads below threshold → no faces.
    h, w = 64, 64
    outputs = {}
    for stride, name_i in ((8, 0), (16, 1), (32, 2)):
        anchors = (h // stride) * (w // stride)
        outputs[f"cls_{stride}"] = np.zeros((1, anchors, 1), dtype=np.float32)
        outputs[f"obj_{stride}"] = np.zeros((1, anchors, 1), dtype=np.float32)
        outputs[f"bbox_{stride}"] = np.zeros((1, anchors, 4), dtype=np.float32)
        outputs[f"kps_{stride}"] = np.zeros((1, anchors, 10), dtype=np.float32)
    faces = decode_yunet_outputs(
        outputs,
        pad_w=w,
        pad_h=h,
        score_threshold=0.7,
        nms_threshold=0.3,
        top_k=5000,
    )
    assert faces is None


def _lab_pack() -> Path | None:
    for candidate in (
        Path("/tmp/semblon-perf-lab/models"),
        Path.home() / ".semblon" / "models" / "yunet_sface",
    ):
        if (candidate / "face_recognition_sface_2021dec.onnx").is_file() and (
            (candidate / "face_detection_yunet_2026may.onnx").is_file()
            or (candidate / "face_detection_yunet_2023mar.onnx").is_file()
        ):
            return candidate
    return None


@pytest.mark.skipif(_lab_pack() is None, reason="lab YuNet/SFace ONNX not present")
def test_ort_and_opencv_agree_on_lena(monkeypatch):
    import cv2
    import urllib.request

    pack = _lab_pack()
    assert pack is not None
    monkeypatch.setenv("SEMBLON_PERF_FACE_PACK", str(pack))

    lena = Path("/tmp/semblon-perf-lab/lena.jpg")
    if not lena.is_file():
        urllib.request.urlretrieve(
            "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg",
            lena,
        )
    img = cv2.imread(str(lena))
    assert img is not None

    from semblon.experimental.inference import load_backend

    ref = load_backend("opencv_dnn")
    ort_b = load_backend("ort_yunet_sface")
    a = ref.embed_bgr_timed(img).faces
    b = ort_b.embed_bgr_timed(img).faces
    assert len(a) >= 1
    assert len(b) >= 1
    # Best cosine between any pair should be near 1 for the same person crop.
    best = max(float(np.dot(x["embedding"], y["embedding"])) for x in a for y in b)
    assert best >= 0.98
