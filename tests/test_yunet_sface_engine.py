"""YuNet+SFace pack gate and (when models present) real inference smoke."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from semblon.engine import (
    EXPECTED_FACE_DIM,
    ModelPackError,
    PACK_FAMILY,
    accept_local_face_pack,
    assert_face_pack_ready,
    embed_bgr,
    face_pack_dir,
    load_app,
)
from semblon.identity_config import SFACE_ONNX, YUNET_ONNX_FALLBACK
from semblon.providers import YuNetSFaceProvider, weights_status


def test_pack_family_and_dim():
    assert PACK_FAMILY == "opencv/yunet_sface"
    assert EXPECTED_FACE_DIM == 128


def test_weights_status_is_byo_not_buffalo():
    rec = weights_status()
    assert rec["engine"] == "yunet_sface"
    assert rec["bundled"] is False
    assert rec["redistributable"] is False
    assert "buffalo" not in rec["dir"].lower() or "yunet" in rec["dir"].lower()


def test_missing_pack_actionable(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_FACE_PACK", str(tmp_path / "empty"))
    with pytest.raises(ModelPackError, match="does not download|YuNet ONNX missing|pack"):
        assert_face_pack_ready()


def test_provider_info():
    assert YuNetSFaceProvider.info.name == "yunet_sface"
    assert YuNetSFaceProvider.info.pack_family == PACK_FAMILY


def _real_pack_ready() -> Path | None:
    root = face_pack_dir()
    yunet = root / YUNET_ONNX_FALLBACK
    if not yunet.is_file():
        yunet = root / "face_detection_yunet_2026may.onnx"
    sface = root / SFACE_ONNX
    pin = root / "semblon-pack-pin.json"
    if yunet.is_file() and sface.is_file() and pin.is_file():
        try:
            assert_face_pack_ready(root)
        except ModelPackError:
            return None
        return root
    return None


@pytest.mark.skipif(
    _real_pack_ready() is None,
    reason="BYO YuNet+SFace pack not installed/pinned on this machine",
)
def test_real_inference_through_load_app_embed_bgr():
    app = load_app()
    # Synthetic face-like gradient; may yield zero faces — still exercises the path.
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[120:360, 200:440] = (180, 160, 140)
    rows = embed_bgr(app, img)
    assert isinstance(rows, list)
    for row in rows:
        assert row["dim"] == EXPECTED_FACE_DIM
        assert row["embedding"].shape == (EXPECTED_FACE_DIM,)


def test_large_photo_is_detected_on_a_capped_view_and_boxes_stay_on_the_original():
    from semblon.engine import FaceSession, _detection_view

    class Detector:
        def __init__(self):
            self.size = None
            self.seen = None

        def setInputSize(self, size):
            self.size = size

        def detect(self, image):
            self.seen = image.shape
            face = np.zeros(15, dtype=np.float32)
            face[0], face[1], face[2], face[3], face[14] = 10, 12, 30, 40, 0.95
            # A box that starts in the padding (or past the photo) is not a face.
            pad = np.zeros(15, dtype=np.float32)
            pad[0], pad[1], pad[2], pad[3], pad[14] = 0, 10_000, 8, 8, 0.99
            return 1, np.array([face, pad])

    class Recognizer:
        def __init__(self):
            self.shape = None

        def alignCrop(self, image, face):
            self.shape = image.shape
            self.face = np.asarray(face).copy()
            return np.zeros((112, 112, 3), dtype=np.uint8)

        def feature(self, aligned):
            return np.ones(EXPECTED_FACE_DIM, dtype=np.float32)

    detector = Detector()
    recognizer = Recognizer()
    app = FaceSession(
        detector,
        recognizer,
        det_size=(320, 320),
        yunet_path=Path("yunet.onnx"),
        sface_path=Path("sface.onnx"),
    )
    image = np.zeros((3000, 4000, 3), dtype=np.uint8)
    view, sx, _sy, content_w, content_h = _detection_view(image)
    assert max(content_w, content_h) == 1280
    assert view.shape[0] <= content_h + 31
    assert view.shape[1] <= content_w + 31
    assert view.shape[1] % 32 == 0 and view.shape[0] % 32 == 0
    rows = embed_bgr(app, image)
    assert detector.size == (view.shape[1], view.shape[0])
    assert detector.size[0] < image.shape[1]
    assert recognizer.shape == image.shape
    assert len(rows) == 1
    assert rows[0]["face_w"] == int(30 * sx)
    assert rows[0]["bbox"][0] == pytest.approx(10 * sx)
    assert rows[0]["det_score"] == pytest.approx(0.95)

    small = np.zeros((80, 100, 3), dtype=np.uint8)
    same, small_sx, _small_sy, small_w, _small_h = _detection_view(small)
    assert same is small
    assert small_sx == 1.0
    assert small_w == 100

    wide = np.zeros((1000, 8000, 3), dtype=np.uint8)
    wide_view, wide_sx, _wide_sy, wide_w, wide_h = _detection_view(wide)
    assert wide_w < 8000
    assert (80 / wide_sx) >= 24 - 0.05
    assert wide_view.shape[0] % 32 == 0
    assert wide_view.shape[0] > wide_h
