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


def _box_iou(a: np.ndarray, b: np.ndarray) -> float:
    ax, ay, aw, ah = (float(v) for v in a[:4])
    bx, by, bw, bh = (float(v) for v in b[:4])
    ax2, ay2, bx2, by2 = ax + aw, ay + ah, bx + bw, by + bh
    iw = max(0.0, min(ax2, bx2) - max(ax, bx))
    ih = max(0.0, min(ay2, by2) - max(ay, by))
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


@pytest.mark.skipif(_lab_pack() is None, reason="lab YuNet/SFace ONNX not present")
def test_ort_and_opencv_agree_on_lena(monkeypatch):
    """0.98 is the identity-embedding contract, not a claim about every detector geometry.

    Measured on this Lena still, OpenCV 5 and ONNX Runtime 1.30, with the pinned
    SFace file:

    * The same aligned crop embedded by FaceRecognizerSF and by ORT agrees at 1.0.
      The raw feature vectors differ by about 3e-6. Graph optimisation does not move them.
    * The same landmarks through alignCrop and align_crop agree at 1.0.
    * The same 640 blob through YuNet agrees between ORT and OpenCV DNN to about 1e-5.
    * End to end on face_detection_yunet_2023mar.onnx is about 0.918. Feeding the ORT
      landmarks through the OpenCV aligner and recogniser reproduces that number.
      OpenCV runs that graph at the view size (512, 4096 anchors). Standalone ORT is
      locked to the exported 640 input and letterboxes. The boxes still overlap
      (IoU about 0.96); the landmarks move by a few pixels.
    * End to end on face_detection_yunet_2026may.onnx, whose input is dynamic, is 1.0.

    So 0.98 stays on the shared crop. It is also required end to end when the
    detector input is dynamic. A fixed 640 graph must still be the same face, and
    the cosine gap must be explained by the landmarks alone.
    """
    import tempfile
    import urllib.request

    import cv2

    pack = _lab_pack()
    assert pack is not None
    monkeypatch.setenv("SEMBLON_PERF_FACE_PACK", str(pack))

    lena_dir = Path(tempfile.gettempdir()) / "semblon-perf-lab"
    lena_dir.mkdir(parents=True, exist_ok=True)
    lena = lena_dir / "lena.jpg"
    legacy = Path("/tmp/semblon-perf-lab/lena.jpg")
    if not lena.is_file() and legacy.is_file():
        lena.write_bytes(legacy.read_bytes())
    if not lena.is_file():
        try:
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg",
                lena,
            )
        except OSError as exc:
            pytest.skip(f"lena.jpg is not cached and could not be fetched: {exc}")
    img = cv2.imread(str(lena))
    assert img is not None

    from semblon.engine import _l2_normalize
    from semblon.experimental.inference import load_backend
    from semblon.experimental.inference.align import align_crop

    ref = load_backend("opencv_dnn")
    ort_b = load_backend("ort_yunet_sface")
    a = ref.embed_bgr_timed(img).faces
    b = ort_b.embed_bgr_timed(img).faces
    assert len(a) >= 1
    assert len(b) >= 1

    opencv_crop = ref.recognizer.alignCrop(img, a[0]["face_row"])
    opencv_feat = _l2_normalize(np.asarray(ref.recognizer.feature(opencv_crop), dtype=np.float32)).ravel()
    ort_feat = np.asarray(ort_b._embed_aligned(opencv_crop), dtype=np.float32).ravel()
    assert float(np.dot(opencv_feat, ort_feat)) >= 0.98

    ort_aligned = align_crop(img, a[0]["face_row"])
    ort_aligned_feat = np.asarray(ort_b._embed_aligned(ort_aligned), dtype=np.float32).ravel()
    assert float(np.dot(ort_feat, ort_aligned_feat)) >= 0.98

    best = max(float(np.dot(x["embedding"], y["embedding"])) for x in a for y in b)
    if ort_b.det_fixed_hw is None:
        assert best >= 0.98
        return

    swapped = ref.recognizer.alignCrop(img, b[0]["face_row"])
    swapped_feat = _l2_normalize(np.asarray(ref.recognizer.feature(swapped), dtype=np.float32)).ravel()
    landmark_only = float(np.dot(opencv_feat, swapped_feat))
    assert abs(landmark_only - best) < 1e-3
    assert _box_iou(a[0]["face_row"], b[0]["face_row"]) >= 0.90
