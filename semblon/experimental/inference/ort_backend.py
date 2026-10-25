"""Experimental native ONNX Runtime YuNet + SFace backend.

Runs the **same** Zoo ONNX files as production. Decode / align / L2 match
OpenCV's FaceDetectorYN + FaceRecognizerSF so identity compare stays on the
same embedding space. Not wired into ingest.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from semblon.engine import _detection_view, _l2_normalize, _scale_face_row
from semblon.experimental.inference.align import align_crop
from semblon.experimental.inference.backends_base import TimedEmbed, face_row_to_result
from semblon.experimental.inference.opencv_dnn_backend import _detection_view_capped
from semblon.experimental.inference.pack import find_pack, verify_known_hashes
from semblon.experimental.inference.yunet_decode import OUTPUT_NAMES, decode_yunet_outputs
from semblon.identity_config import (
    DET_SCORE_MIN,
    EXPECTED_FACE_DIM,
    NMS_THRESHOLD,
    TOP_K,
    YUNET_ONNX_FALLBACK,
)


def _ort_session(path: Path) -> ort.InferenceSession:
    # Zoo exports (esp. SFace / 2023mar) list weight initializers as graph
    # inputs; ORT warns loudly. Severity 3 = ERROR only.
    ort.set_default_logger_severity(3)
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    so.log_severity_level = 3
    # Prefer CPU EP. On Windows ARM64 native Python this is the native EP that
    # already worked historically (docs/PERF-P1-ARM64.md). Never claim GPU.
    available = ort.get_available_providers()
    providers: list[str] = []
    if "CPUExecutionProvider" in available:
        providers.append("CPUExecutionProvider")
    else:
        providers = list(available)
    return ort.InferenceSession(str(path), sess_options=so, providers=providers)


class ORTYuNetSFaceBackend:
    """YuNet detect + SFace embed via onnxruntime.InferenceSession."""

    name = "ort_yunet_sface"

    def __init__(
        self,
        *,
        yunet: Path | None = None,
        sface: Path | None = None,
        score_threshold: float = DET_SCORE_MIN,
        nms_threshold: float = NMS_THRESHOLD,
        top_k: int = TOP_K,
        detect_long_side: int | None = None,
        intra_op_threads: int | None = None,
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

        self.det_session = _ort_session(self.yunet_path)
        self.rec_session = _ort_session(self.sface_path)
        if intra_op_threads is not None:
            # Session already created; record intent for reports only.
            self._requested_threads = int(intra_op_threads)
        else:
            self._requested_threads = None

        det_inputs = self.det_session.get_inputs()
        # 2023mar lists weight initializers as inputs; find the image tensor.
        self.det_input_name = "input"
        self.det_fixed_hw: tuple[int, int] | None = None
        for inp in det_inputs:
            if inp.name == "input" or (
                isinstance(inp.shape, (list, tuple))
                and len(inp.shape) == 4
                and inp.shape[1] == 3
            ):
                self.det_input_name = inp.name
                shape = inp.shape
                h, w = shape[2], shape[3]
                if isinstance(h, int) and isinstance(w, int):
                    self.det_fixed_hw = (int(h), int(w))
                break

        rec_inputs = self.rec_session.get_inputs()
        self.rec_input_name = rec_inputs[0].name
        self.rec_output_name = self.rec_session.get_outputs()[0].name
        self.providers = list(self.det_session.get_providers())

        if self.yunet_path.name == YUNET_ONNX_FALLBACK and self.det_fixed_hw == (640, 640):
            self._fixed_note = (
                "2023mar is fixed 640×640 under standalone ORT; "
                "experimental path letterboxes to 640 then scales boxes. "
                "Prefer face_detection_yunet_2026may.onnx for dynamic H/W parity "
                "with OpenCV FaceDetectorYN."
            )
        else:
            self._fixed_note = None

    def info(self) -> dict:
        return {
            "backend": self.name,
            "yunet": str(self.yunet_path),
            "sface": str(self.sface_path),
            "providers": list(self.providers),
            "available_providers": ort.get_available_providers(),
            "hashes": self.hash_report,
            "score_threshold": self.score_threshold,
            "nms_threshold": self.nms_threshold,
            "detect_long_side_override": self.detect_long_side,
            "det_input_name": self.det_input_name,
            "det_fixed_hw": self.det_fixed_hw,
            "rec_input_name": self.rec_input_name,
            "requested_intra_op_threads": self._requested_threads,
            "fixed_shape_note": self._fixed_note,
            "ort_version": ort.__version__,
        }

    def _prepare_det_blob(self, view: np.ndarray) -> tuple[np.ndarray, float, float, int, int]:
        """BGR view → NCHW float32 blob. Returns blob, sx, sy, pad_w, pad_h."""
        h, w = view.shape[:2]
        if self.det_fixed_hw is None:
            pad_w = (32 - (w % 32)) % 32
            pad_h = (32 - (h % 32)) % 32
            if pad_w or pad_h:
                canvas = np.zeros((h + pad_h, w + pad_w, 3), dtype=view.dtype)
                canvas[:h, :w] = view
                padded = canvas
            else:
                padded = view
            # OpenCV FaceDetectorYN already received a multiple-of-32 view from
            # Semblon; keep the same top-left pad. blobFromImage: BGR, 0–255.
            blob = cv2.dnn.blobFromImage(padded)
            return blob, 1.0, 1.0, int(padded.shape[1]), int(padded.shape[0])

        # Fixed-shape model (2023mar under standalone ORT): letterbox into HxW.
        th, tw = self.det_fixed_hw
        scale = min(tw / float(w), th / float(h))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        resized = cv2.resize(view, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((th, tw, 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = resized
        blob = cv2.dnn.blobFromImage(canvas)
        # Map detections from letterboxed space back to ``view`` pixels.
        inv = 1.0 / scale if scale > 0 else 1.0
        return blob, inv, inv, tw, th

    def _detect(self, view: np.ndarray) -> tuple[np.ndarray | None, float, float]:
        blob, sx, sy, pad_w, pad_h = self._prepare_det_blob(view)
        feeds = {self.det_input_name: blob}
        # Only feed the image input; ignore initializer-as-input names on 2023mar.
        raw = self.det_session.run(list(OUTPUT_NAMES), feeds)
        outputs = {name: arr for name, arr in zip(OUTPUT_NAMES, raw)}
        faces = decode_yunet_outputs(
            outputs,
            pad_w=pad_w,
            pad_h=pad_h,
            score_threshold=self.score_threshold,
            nms_threshold=self.nms_threshold,
            top_k=self.top_k,
        )
        return faces, sx, sy

    def _embed_aligned(self, aligned_bgr: np.ndarray) -> np.ndarray:
        # OpenCV FaceRecognizerSF::feature uses swapRB=True (BGR→RGB), scale=1.
        blob = cv2.dnn.blobFromImage(
            aligned_bgr,
            scalefactor=1.0,
            size=(112, 112),
            mean=(0, 0, 0),
            swapRB=True,
            crop=False,
        )
        out = self.rec_session.run([self.rec_output_name], {self.rec_input_name: blob})[0]
        return _l2_normalize(np.asarray(out, dtype=np.float32))

    def embed_bgr_timed(self, img: np.ndarray) -> TimedEmbed:
        if img is None or getattr(img, "size", 0) == 0:
            raise FileNotFoundError("cannot decode empty image")

        t0 = time.perf_counter()
        if self.detect_long_side is None:
            view, view_sx, view_sy, content_w, content_h = _detection_view(img)
        else:
            view, view_sx, view_sy, content_w, content_h = _detection_view_capped(
                img, int(self.detect_long_side)
            )
        t_view = time.perf_counter()

        faces, letter_sx, letter_sy = self._detect(view)
        t_detect = time.perf_counter()

        rows: list[dict] = []
        align_s = 0.0
        embed_s = 0.0
        if faces is not None:
            for face in faces:
                face = np.asarray(face, dtype=np.float32).reshape(-1)
                if face.size < 15:
                    continue
                # Undo letterbox (fixed-shape path) then undo detection-view scale.
                if letter_sx != 1.0 or letter_sy != 1.0:
                    face = _scale_face_row(face, letter_sx, letter_sy)
                if float(face[0]) >= content_w or float(face[1]) >= content_h:
                    continue
                face = _scale_face_row(face, view_sx, view_sy)
                ta0 = time.perf_counter()
                try:
                    aligned = align_crop(img, face)
                except Exception:
                    continue
                ta1 = time.perf_counter()
                try:
                    vec = self._embed_aligned(aligned)
                except Exception:
                    continue
                te1 = time.perf_counter()
                align_s += ta1 - ta0
                embed_s += te1 - ta1
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
            extras={"letterbox_sx": letter_sx, "letterbox_sy": letter_sy},
        )
