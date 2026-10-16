"""NanoDet-Plus COCO detector (observation only — never identity).

Algorithm adapted from OpenCV Zoo ``models/object_detection_nanodet``
(Apache-2.0). Semblon does not redistribute weights; see ``docs/OBJECT-PACK.md``.
Contour regions remain a separate provider (``opencv-contour``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from semblon.object_pack import WEIGHT_NAME, assert_nanodet_pack_ready, object_pack_dir

# COCO-80 class names (detector vocabulary only — not open-vocabulary search).
COCO_CLASSES: tuple[str, ...] = (
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
)


class NanoDetSession:
    """Lazy OpenCV DNN session for one BYO ONNX file."""

    def __init__(
        self,
        model_path: Path,
        *,
        prob_threshold: float = 0.35,
        iou_threshold: float = 0.6,
    ) -> None:
        import cv2

        self._cv2 = cv2
        self.strides = (8, 16, 32, 64)
        self.image_shape = (416, 416)
        self.reg_max = 7
        self.prob_threshold = float(prob_threshold)
        self.iou_threshold = float(iou_threshold)
        self.project = np.arange(self.reg_max + 1, dtype=np.float32)
        self.mean = np.array([103.53, 116.28, 123.675], dtype=np.float32).reshape(1, 1, 3)
        self.std = np.array([57.375, 57.12, 58.395], dtype=np.float32).reshape(1, 1, 3)
        self.net = cv2.dnn.readNet(str(model_path))
        self.anchors_mlvl: list[np.ndarray] = []
        for stride in self.strides:
            feat_h = int(self.image_shape[0] / stride)
            feat_w = int(self.image_shape[1] / stride)
            shift_x = np.arange(0, feat_w) * stride
            shift_y = np.arange(0, feat_h) * stride
            xv, yv = np.meshgrid(shift_x, shift_y)
            cx = xv.flatten() + 0.5 * (stride - 1)
            cy = yv.flatten() + 0.5 * (stride - 1)
            self.anchors_mlvl.append(np.column_stack((cx, cy)))

    def _pre_process(self, img: np.ndarray) -> np.ndarray:
        arr = img.astype(np.float32)
        arr = (arr - self.mean) / self.std
        return self._cv2.dnn.blobFromImage(arr)

    def _post_process(self, preds: list) -> np.ndarray:
        cv2 = self._cv2
        cls_scores, bbox_preds = preds[::2], preds[1::2]
        bboxes_mlvl = []
        scores_mlvl = []
        for stride, cls_score, bbox_pred, anchors in zip(
            self.strides, cls_scores, bbox_preds, self.anchors_mlvl
        ):
            if cls_score.ndim == 3:
                cls_score = cls_score.squeeze(axis=0)
            if bbox_pred.ndim == 3:
                bbox_pred = bbox_pred.squeeze(axis=0)
            x_exp = np.exp(bbox_pred.reshape(-1, self.reg_max + 1))
            x_sum = np.sum(x_exp, axis=1, keepdims=True)
            bbox_pred = x_exp / x_sum
            bbox_pred = np.dot(bbox_pred, self.project).reshape(-1, 4)
            bbox_pred *= stride
            nms_pre = 1000
            if nms_pre > 0 and cls_score.shape[0] > nms_pre:
                max_scores = cls_score.max(axis=1)
                topk_inds = max_scores.argsort()[::-1][0:nms_pre]
                anchors = anchors[topk_inds, :]
                bbox_pred = bbox_pred[topk_inds, :]
                cls_score = cls_score[topk_inds, :]
            distance = bbox_pred
            x1 = np.clip(anchors[:, 0] - distance[:, 0], 0, self.image_shape[1])
            y1 = np.clip(anchors[:, 1] - distance[:, 1], 0, self.image_shape[0])
            x2 = np.clip(anchors[:, 0] + distance[:, 2], 0, self.image_shape[1])
            y2 = np.clip(anchors[:, 1] + distance[:, 3], 0, self.image_shape[0])
            bboxes_mlvl.append(np.column_stack([x1, y1, x2, y2]))
            scores_mlvl.append(cls_score)
        bboxes_mlvl = np.concatenate(bboxes_mlvl, axis=0)
        scores_mlvl = np.concatenate(scores_mlvl, axis=0)
        bboxes_wh = bboxes_mlvl.copy()
        bboxes_wh[:, 2:4] = bboxes_wh[:, 2:4] - bboxes_wh[:, 0:2]
        class_ids = np.argmax(scores_mlvl, axis=1)
        confidences = np.max(scores_mlvl, axis=1)
        indices = cv2.dnn.NMSBoxes(
            bboxes_wh.tolist(),
            confidences.tolist(),
            self.prob_threshold,
            self.iou_threshold,
        )
        if len(indices) == 0:
            return np.zeros((0, 6), dtype=np.float32)
        idx = np.array(indices).reshape(-1)
        return np.concatenate(
            [
                bboxes_mlvl[idx],
                confidences[idx].reshape(-1, 1),
                class_ids[idx].reshape(-1, 1),
            ],
            axis=1,
        )

    def detect(self, bgr: np.ndarray, *, max_detections: int = 32) -> list[dict]:
        """Return COCO-labelled boxes in original image coordinates."""
        arr = np.asarray(bgr)
        if arr.ndim != 3 or arr.shape[2] != 3:
            return []
        h0, w0 = arr.shape[:2]
        import cv2

        resized = cv2.resize(arr, self.image_shape[::-1])
        blob = self._pre_process(resized)
        self.net.setInput(blob)
        outs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        preds = self._post_process(outs)
        if preds.size == 0:
            return []
        sx = float(w0) / float(self.image_shape[1])
        sy = float(h0) / float(self.image_shape[0])
        out: list[dict] = []
        for row in preds[:max_detections]:
            x1, y1, x2, y2, score, class_id = (float(v) for v in row)
            cid = int(class_id)
            label = COCO_CLASSES[cid] if 0 <= cid < len(COCO_CLASSES) else f"class_{cid}"
            out.append(
                {
                    "bbox": (x1 * sx, y1 * sy, x2 * sx, y2 * sy),
                    "score": score,
                    "class": label,
                    "label": label,
                    "class_id": cid,
                }
            )
        return out


_SESSION: NanoDetSession | None = None
_SESSION_PATH: str | None = None


def get_nanodet_session(root: Path | None = None) -> NanoDetSession:
    global _SESSION, _SESSION_PATH
    meta = assert_nanodet_pack_ready(root)
    path = meta["path"]
    if _SESSION is None or _SESSION_PATH != path:
        _SESSION = NanoDetSession(Path(path))
        _SESSION_PATH = path
    return _SESSION


def detect_objects(bgr, *, root: Path | None = None) -> list[dict]:
    """Run NanoDet when the BYO pack is ready. Raises FileNotFoundError if not."""
    session = get_nanodet_session(root)
    return session.detect(np.asarray(bgr))


def reset_session_for_tests() -> None:
    global _SESSION, _SESSION_PATH
    _SESSION = None
    _SESSION_PATH = None


def default_weight_name() -> str:
    return WEIGHT_NAME


def pack_home() -> Path:
    return object_pack_dir()
