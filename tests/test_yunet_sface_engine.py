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
