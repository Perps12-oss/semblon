"""Historical FaceKit / buffalo_l identity constants (S1 golden).

Frozen for interpreting old stores and rollback evidence.
These values must NOT control the YuNet + SFace production engine.
See docs/S1-GOLDEN.md and docs/decisions/2026-10-16-identity-stack-eval-order.md.
"""

from __future__ import annotations

PACK_FAMILY = "insightface/buffalo_l"
EXPECTED_FACE_DIM = 512
DEFAULT_EPS = 0.40
DEFAULT_MIN_SAMPLES = 2
METRIC = "1-dot"
STRONG_MIN_INTRA = 0.50
DEFAULT_THRESHOLD = 0.60  # 1 - DEFAULT_EPS
DET_SCORE_MIN = 0.60
CLUSTER_MIN_SIDE = 80
DET_SIZE = (640, 640)
