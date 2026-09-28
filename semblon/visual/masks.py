"""Mask geometry. No inference."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MaskCand:
    """One proposed mask, before product filtering. Not a hover region yet."""

    mask: np.ndarray
    provider: str
    method: str
    stability: float = 1.0
    pred_iou: float = 1.0
    fate: str = "raw"
    user_label: str | None = None


def bbox_of(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return (0, 0, 0, 0)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def area_of(mask: np.ndarray) -> int:
    return int(np.count_nonzero(mask))


def iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = int(np.count_nonzero(a & b))
    if inter == 0:
        return 0.0
    union = int(np.count_nonzero(a | b))
    return inter / union if union else 0.0


def containment(parent: np.ndarray, child: np.ndarray) -> float:
    """Fraction of child covered by parent."""
    child_area = int(np.count_nonzero(child))
    if child_area == 0:
        return 0.0
    return int(np.count_nonzero(parent & child)) / child_area


def box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0, x2 - x1), max(0, y2 - y1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def rows_from_mask(mask: np.ndarray, *, max_runs: int = 4000) -> dict[str, list[list[int]]]:
    """Row runs for hit-testing. Keys are y. Truncates pathological masks."""
    out: dict[str, list[list[int]]] = {}
    runs = 0
    h, w = mask.shape
    for y in range(h):
        row = mask[y]
        if not row.any():
            continue
        xs = np.flatnonzero(row)
        # group contiguous
        splits = np.where(np.diff(xs) > 1)[0]
        start = 0
        spans: list[list[int]] = []
        for s in list(splits) + [len(xs) - 1]:
            x0 = int(xs[start])
            x1 = int(xs[s]) + 1
            spans.append([x0, x1])
            start = int(s) + 1
            runs += 1
            if runs >= max_runs:
                out[str(y)] = spans
                return out
        out[str(y)] = spans
    return out


def point_in_rows(rows: dict, x: float, y: float) -> bool:
    spans = rows.get(str(int(y)))
    if not spans:
        return False
    xi = int(x)
    return any(a <= xi < b for a, b in spans)


def connected_labels(binary: np.ndarray) -> np.ndarray:
    """4-connected labels, 0 = background. Small images only."""
    h, w = binary.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent = [0]

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    nid = 0
    ys, xs = np.nonzero(binary)
    for y, x in zip(ys.tolist(), xs.tolist()):
        left = labels[y, x - 1] if x else 0
        up = labels[y - 1, x] if y else 0
        if left and up:
            labels[y, x] = left
            union(left, up)
        elif left or up:
            labels[y, x] = left or up
        else:
            nid += 1
            parent.append(nid)
            labels[y, x] = nid
    if nid == 0:
        return labels
    remap = {}
    next_id = 1
    flat = labels.ravel()
    for i, v in enumerate(flat):
        if v == 0:
            continue
        r = find(int(v))
        if r not in remap:
            remap[r] = next_id
            next_id += 1
        flat[i] = remap[r]
    return flat.reshape(h, w)


def stock_nms(masks: list[np.ndarray], scores: list[float], iou_thresh: float) -> list[int]:
    """Keep indices. High box-like mask IoU suppresses the lower score. Drops contained children."""
    order = sorted(range(len(masks)), key=lambda i: scores[i], reverse=True)
    keep: list[int] = []
    for i in order:
        if any(iou(masks[i], masks[j]) >= iou_thresh for j in keep):
            continue
        keep.append(i)
    return keep


def containment_keep(
    masks: list[np.ndarray],
    scores: list[float],
    *,
    contain_ratio: float,
    overlap_iou: float,
) -> tuple[list[int], list[str]]:
    """Keep nested masks. Drop only near-duplicates that do not contain each other."""
    order = sorted(range(len(masks)), key=lambda i: scores[i], reverse=True)
    keep: list[int] = []
    notes = ["raw"] * len(masks)
    for i in order:
        drop = False
        for j in keep:
            c_ij = containment(masks[j], masks[i])
            c_ji = containment(masks[i], masks[j])
            if c_ij >= contain_ratio or c_ji >= contain_ratio:
                notes[i] = "containment_kept"
                continue
            if iou(masks[i], masks[j]) >= overlap_iou:
                drop = True
                notes[i] = "dedupe_removed"
                break
        if not drop:
            keep.append(i)
            if notes[i] == "raw":
                notes[i] = "dedupe_kept"
    return keep, notes
