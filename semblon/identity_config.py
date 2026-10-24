"""Active identity-engine configuration: YuNet detect + SFace recognise.

PROVISIONAL clustering/identify thresholds until a Semblon-specific Q-gate
eval records acceptance. Do not copy buffalo_l S1 values here by habit.
"""

from __future__ import annotations

# Content-address family for pack_id. Not a buffalo_l alias.
PACK_FAMILY = "opencv/yunet_sface"
ADAPTER_NAME = "yunet_sface"
PROVIDER_NAME = "yunet_sface"

# OpenCV Zoo artifacts (exact filenames). Detector prefers dynamic-shape 2026may
# when present; otherwise 2023mar. Recogniser is fixed.
YUNET_ONNX_PREFERRED = "face_detection_yunet_2026may.onnx"
YUNET_ONNX_FALLBACK = "face_detection_yunet_2023mar.onnx"
SFACE_ONNX = "face_recognition_sface_2021dec.onnx"

EXPECTED_FACE_DIM = 128

# Detection / quality (ingest). Independent of buffalo_l.
# FaceDetectorYN.create needs an initial size. That size is not the thumbnail
# a still is shrunk to: runtime detection uses DETECT_LONG_SIDE.
DET_SIZE = (320, 320)
# Longest side YuNet is asked to look at. Full-frame detection is what made
# a hard-drive folder take days. Boxes are mapped back onto the original
# image; SFace crops that original, not this view.
DETECT_LONG_SIDE = 1280
# Do not shrink a wide still so far that a face at the quality floor
# (CLUSTER_MIN_SIDE) falls under this many pixels on the detector.
DETECT_MIN_FACE_PX = 24
DET_SCORE_MIN = 0.70
NMS_THRESHOLD = 0.30
TOP_K = 5000
CLUSTER_MIN_SIDE = 80

# Clustering / identify — PROVISIONAL starting point (1-dot distance).
# Recalibrate on a Semblon corpus before claiming Q PASS.
DEFAULT_EPS = 0.45
DEFAULT_MIN_SAMPLES = 2
METRIC = "1-dot"
STRONG_MIN_INTRA = 0.50
DEFAULT_THRESHOLD = round(1.0 - DEFAULT_EPS, 2)  # 0.55

# Upstream Zoo (pin when recording L evidence).
YUNET_ZOO_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_2026_ZOO_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2026may.onnx"
)
SFACE_ZOO_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx"
)
YUNET_LICENSE_URL = (
    "https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE"
)
SFACE_LICENSE_URL = (
    "https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/LICENSE"
)
