"""YuNet output decode + NMS — ports OpenCV FaceDetectorYNImpl::postProcess.

Source of truth: opencv/modules/objdetect/src/face_detect.cpp
"""

from __future__ import annotations

import cv2
import numpy as np

STRIDES = (8, 16, 32)
OUTPUT_NAMES = (
    "cls_8",
    "cls_16",
    "cls_32",
    "obj_8",
    "obj_16",
    "obj_32",
    "bbox_8",
    "bbox_16",
    "bbox_32",
    "kps_8",
    "kps_16",
    "kps_32",
)


def decode_yunet_outputs(
    outputs: dict[str, np.ndarray],
    *,
    pad_w: int,
    pad_h: int,
    score_threshold: float,
    nms_threshold: float,
    top_k: int,
) -> np.ndarray | None:
    """Return ``(N, 15)`` float32 faces or ``None`` when empty.

    Each row: ``x, y, w, h, 5×(x,y) landmarks, score``.
    """
    faces: list[np.ndarray] = []
    for i, stride in enumerate(STRIDES):
        cols = int(pad_w / stride)
        rows = int(pad_h / stride)
        cls = np.asarray(outputs[OUTPUT_NAMES[i]], dtype=np.float32).reshape(-1)
        obj = np.asarray(outputs[OUTPUT_NAMES[i + 3]], dtype=np.float32).reshape(-1)
        bbox = np.asarray(outputs[OUTPUT_NAMES[i + 6]], dtype=np.float32).reshape(-1, 4)
        kps = np.asarray(outputs[OUTPUT_NAMES[i + 9]], dtype=np.float32).reshape(-1, 10)
        expected = rows * cols
        if cls.size < expected or bbox.shape[0] < expected:
            raise ValueError(
                f"YuNet stride {stride}: got cls={cls.size} bbox={bbox.shape[0]} "
                f"expected anchors={expected} for pad=({pad_w},{pad_h})"
            )
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                cls_score = float(np.clip(cls[idx], 0.0, 1.0))
                obj_score = float(np.clip(obj[idx], 0.0, 1.0))
                score = float(np.sqrt(cls_score * obj_score))
                if score < score_threshold:
                    continue
                bx = bbox[idx]
                cx = (c + float(bx[0])) * stride
                cy = (r + float(bx[1])) * stride
                w = float(np.exp(bx[2])) * stride
                h = float(np.exp(bx[3])) * stride
                x1 = cx - w / 2.0
                y1 = cy - h / 2.0
                row = np.empty(15, dtype=np.float32)
                row[0] = x1
                row[1] = y1
                row[2] = w
                row[3] = h
                kp = kps[idx]
                for n in range(5):
                    row[4 + 2 * n] = (float(kp[2 * n]) + c) * stride
                    row[4 + 2 * n + 1] = (float(kp[2 * n + 1]) + r) * stride
                row[14] = score
                faces.append(row)

    if not faces:
        return None
    stacked = np.stack(faces, axis=0)
    if stacked.shape[0] == 1:
        return stacked

    boxes = [
        (int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in stacked
    ]
    scores = [float(r[14]) for r in stacked]
    keep = cv2.dnn.NMSBoxes(boxes, scores, score_threshold, nms_threshold, top_k=top_k)
    if keep is None or len(keep) == 0:
        return None
    idxs = np.asarray(keep).reshape(-1).tolist()
    return stacked[idxs]
