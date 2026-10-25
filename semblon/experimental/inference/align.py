"""SFace five-point similarity transform — ports OpenCV FaceRecognizerSF.alignCrop.

Source of truth: opencv/modules/objdetect/src/face_recognize.cpp
(getSimilarityTransformMatrix). Used only by the experimental ORT path so
ARM64 hosts without OpenCV DNN can still align with the same landmarks.
"""

from __future__ import annotations

import cv2
import numpy as np

# ArcFace / SFace reference landmarks in the 112×112 crop (OpenCV constants).
_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float64,
)
_DST_MEAN = np.array([56.0262, 71.9008], dtype=np.float64)


def similarity_transform_matrix(src_points: np.ndarray) -> np.ndarray:
    """Return 2×3 affine matrix mapping ``src_points`` (5×2) onto SFace dst."""
    src = np.asarray(src_points, dtype=np.float64).reshape(5, 2)
    src_mean = src.mean(axis=0)
    src_demean = src - src_mean
    dst_demean = _DST - _DST_MEAN

    A00 = float(np.dot(dst_demean[:, 0], src_demean[:, 0]) / 5.0)
    A01 = float(np.dot(dst_demean[:, 0], src_demean[:, 1]) / 5.0)
    A10 = float(np.dot(dst_demean[:, 1], src_demean[:, 0]) / 5.0)
    A11 = float(np.dot(dst_demean[:, 1], src_demean[:, 1]) / 5.0)
    A = np.array([[A00, A01], [A10, A11]], dtype=np.float64)

    d = np.array([1.0, 1.0], dtype=np.float64)
    det_a = A00 * A11 - A01 * A10
    if det_a < 0:
        d[1] = -1.0

    u, s, vt = np.linalg.svd(A)
    smax = float(max(s[0], s[1]))
    tol = smax * 2.0 * np.finfo(np.float32).tiny
    rank = int(s[0] > tol) + int(s[1] > tol)

    det_u = float(np.linalg.det(u))
    det_vt = float(np.linalg.det(vt))
    T = np.eye(3, dtype=np.float64)

    if rank == 1:
        if (det_u * det_vt) > 0:
            uvt = u @ vt
            T[0:2, 0:2] = uvt
        else:
            temp = d[1]
            d[1] = -1.0
            D = np.diag(d)
            T[0:2, 0:2] = u @ D @ vt
            d[1] = temp
    else:
        D = np.diag(d)
        T[0:2, 0:2] = u @ D @ vt

    var = float((src_demean[:, 0] ** 2).sum() / 5.0 + (src_demean[:, 1] ** 2).sum() / 5.0)
    scale = (1.0 / var) * (s[0] * d[0] + s[1] * d[1]) if var > 0 else 1.0

    TS0 = T[0, 0] * src_mean[0] + T[0, 1] * src_mean[1]
    TS1 = T[1, 0] * src_mean[0] + T[1, 1] * src_mean[1]
    T[0, 2] = _DST_MEAN[0] - scale * TS0
    T[1, 2] = _DST_MEAN[1] - scale * TS1
    T[0, 0] *= scale
    T[0, 1] *= scale
    T[1, 0] *= scale
    T[1, 1] *= scale
    return T[0:2, :].astype(np.float64)


def align_crop(bgr: np.ndarray, face_row: np.ndarray) -> np.ndarray:
    """Warp ``bgr`` to a 112×112 BGR crop using YuNet's five landmarks."""
    face = np.asarray(face_row, dtype=np.float32).reshape(-1)
    if face.size < 14:
        raise ValueError("face row needs bbox + 5 landmarks")
    src = face[4:14].reshape(5, 2)
    mat = similarity_transform_matrix(src)
    return cv2.warpAffine(
        bgr,
        mat,
        (112, 112),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
