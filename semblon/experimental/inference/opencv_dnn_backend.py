"""Experimental wrapper around the production OpenCV DNN path.

Uses the same ``FaceDetectorYN`` / ``FaceRecognizerSF`` APIs as
``semblon.engine`` but does **not** go through ``load_app`` pack-pin gates so
lab folders (``SEMBLON_PERF_FACE_PACK``) can be timed without writing a pin.
Production ingest is unchanged.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from semblon.engine import (
    _detection_view,
    _l2_normalize,
    _scale_face_row,
)
from semblon.experimental.inference.backends_base import TimedEmbed, face_row_to_result
from semblon.experimental.inference.pack import find_pack, verify_known_hashes
from semblon.identity_config import (
    DET_SCORE_MIN,
    DET_SIZE,
    EXPECTED_FACE_DIM,
    NMS_THRESHOLD,
    TOP_K,
)


class OpenCVDNNBackend:
    """Reference backend: OpenCV DNN FaceDetectorYN + FaceRecognizerSF."""

    name = "opencv_dnn"

    def __init__(
        self,
        *,
        yunet: Path | None = None,
        sface: Path | None = None,
        score_threshold: float = DET_SCORE_MIN,
        nms_threshold: float = NMS_THRESHOLD,
        top_k: int = TOP_K,
        detect_long_side: int | None = None,
    ):
        if yunet is None or sface is None:
            _root, yunet, sface = find_pack()
        self.yunet_path = Path(yunet)
        self.sface_path = Path(sface)
        self.score_threshold = float(score_threshold)
        self.nms_threshold = float(nms_threshold)
        self.top_k = int(top_k)
        self.detect_long_side = detect_long_side
        self.hash_report = verify_known_hashes(self.yunet_path, self.sface_path)
        w, h = DET_SIZE
        self.detector = cv2.FaceDetectorYN.create(
            str(self.yunet_path),
            "",
            (w, h),
            self.score_threshold,
            self.nms_threshold,
            self.top_k,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(self.sface_path), "")
        self.providers = ["OpenCV_DNN_CPU"]
        self.dnn_available = True

    def info(self) -> dict:
        return {
            "backend": self.name,
            "yunet": str(self.yunet_path),
            "sface": str(self.sface_path),
            "providers": list(self.providers),
            "hashes": self.hash_report,
            "score_threshold": self.score_threshold,
            "nms_threshold": self.nms_threshold,
            "detect_long_side_override": self.detect_long_side,
            "dnn_module": True,
            "FaceDetectorYN": True,
            "FaceRecognizerSF": True,
        }

    def embed_bgr_timed(self, img: np.ndarray) -> TimedEmbed:
        if img is None or getattr(img, "size", 0) == 0:
            raise FileNotFoundError("cannot decode empty image")

        t0 = time.perf_counter()
        if self.detect_long_side is None:
            view, sx, sy, content_w, content_h = _detection_view(img)
        else:
            view, sx, sy, content_w, content_h = _detection_view_capped(
                img, int(self.detect_long_side)
            )
        t_view = time.perf_counter()

        view_h, view_w = view.shape[:2]
        self.detector.setInputSize((int(view_w), int(view_h)))
        _retval, faces = self.detector.detect(view)
        t_detect = time.perf_counter()

        rows: list[dict] = []
        align_s = 0.0
        embed_s = 0.0
        if faces is not None:
            for face in faces:
                face = np.asarray(face, dtype=np.float32).reshape(-1)
                if face.size < 15:
                    continue
                if float(face[0]) >= content_w or float(face[1]) >= content_h:
                    continue
                face = _scale_face_row(face, sx, sy)
                ta0 = time.perf_counter()
                try:
                    aligned = self.recognizer.alignCrop(img, face)
                except cv2.error:
                    continue
                ta1 = time.perf_counter()
                try:
                    feat = self.recognizer.feature(aligned)
                except cv2.error:
                    continue
                te1 = time.perf_counter()
                align_s += ta1 - ta0
                embed_s += te1 - ta1
                vec = _l2_normalize(np.asarray(feat, dtype=np.float32))
                if int(vec.size) != EXPECTED_FACE_DIM:
                    raise ValueError(f"unexpected dim={vec.size}")
                rows.append(face_row_to_result(face, vec))

        t_end = time.perf_counter()
        return TimedEmbed(
            faces=rows,
            decode_s=0.0,
            view_s=t_view - t0,
            detect_s=t_detect - t_view,
            align_s=align_s,
            embed_s=embed_s,
            total_s=t_end - t0,
        )


def _detection_view_capped(img: np.ndarray, long_side: int):
    """Same pad-to-32 shrink as production, but with an explicit long-side cap."""
    from semblon.identity_config import CLUSTER_MIN_SIDE, DETECT_MIN_FACE_PX

    height, width = img.shape[:2]
    keep_floor = int(round(max(width, height) * (DETECT_MIN_FACE_PX / float(CLUSTER_MIN_SIDE))))
    limit = min(max(width, height), max(int(long_side), keep_floor))
    if max(width, height) <= limit:
        return img, 1.0, 1.0, width, height
    scale = limit / float(max(width, height))
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    pad_w = (32 - (new_w % 32)) % 32
    pad_h = (32 - (new_h % 32)) % 32
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    if pad_w or pad_h:
        canvas = np.zeros((new_h + pad_h, new_w + pad_w, img.shape[2]), dtype=img.dtype)
        canvas[:new_h, :new_w] = resized
        view = canvas
    else:
        view = resized
    return view, width / float(new_w), height / float(new_h), new_w, new_h
