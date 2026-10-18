"""Photographic region retrieval.

Source pixels are scikit-image photographs. Viewpoint is a perspective warp of
a real crop pasted onto a different photograph. Lighting is a gamma and colour
cast of that crop on another photograph. The distractor is a rectangle of the
crop's mean colour, same size, on another photograph.

The query rectangle is not chosen from proposal boxes. The report records
whether that pasted content overlapped a proposal box in the other photo.

Writes docs/evidence/photo-region-eval.json. Exit 0 only when every query's
viewpoint and lighting hits rank above the same-colour distractor and the
match box meets the pasted region.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

OUT = ROOT / "docs" / "evidence" / "photo-region-eval.json"

# query photo, crop as fractions (x, y, w, h), viewpoint bg, lighting bg, distractor bg
CASES = (
    ("chelsea", (0.38, 0.28, 0.22, 0.28), "coffee", "grass", "brick"),
    ("clock", (0.30, 0.22, 0.28, 0.34), "astronaut", "gravel", "horse"),
    ("coins", (0.22, 0.30, 0.24, 0.28), "rocket", "moon", "page"),
    ("camera", (0.28, 0.22, 0.30, 0.32), "hubble_deep_field", "immunohistochemistry", "retina"),
)


def _bgr(name: str) -> np.ndarray:
    from skimage import data

    rgb = getattr(data, name)()
    if rgb.ndim == 2:
        rgb = np.stack([rgb, rgb, rgb], axis=-1)
    rgb = np.asarray(rgb)
    if rgb.shape[2] == 4:
        rgb = rgb[:, :, :3]
    return cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)


def _crop_box(image: np.ndarray, frac) -> tuple[int, int, int, int]:
    height, width = image.shape[:2]
    x = int(width * frac[0])
    y = int(height * frac[1])
    w = max(24, int(width * frac[2]))
    h = max(24, int(height * frac[3]))
    if x + w > width:
        w = width - x
    if y + h > height:
        h = height - y
    return x, y, w, h


def _relight(crop: np.ndarray) -> np.ndarray:
    img = np.clip(crop.astype(np.float32) / 255.0, 0, 1)
    img = np.power(img, 1.75)
    img *= np.array([1.18, 0.82, 0.90], dtype=np.float32)
    return np.clip(img * 255.0, 0, 255).astype(np.uint8)


def _paste_warp(background: np.ndarray, crop: np.ndarray, *, corner: str) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    bg = background.copy()
    bh, bw = bg.shape[:2]
    ch, cw = crop.shape[:2]
    target = max(36, int(min(bh, bw) * 0.22))
    scale = target / float(max(ch, cw))
    nw = max(20, int(round(cw * scale)))
    nh = max(20, int(round(ch * scale)))
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_CUBIC)
    if corner == "br":
        x0 = int(bw * 0.62)
        y0 = int(bh * 0.58)
    else:
        x0 = int(bw * 0.06)
        y0 = int(bh * 0.08)
    x0 = min(x0, max(0, bw - nw - 4))
    y0 = min(y0, max(0, bh - nh - 4))
    src = np.float32([[0, 0], [nw - 1, 0], [nw - 1, nh - 1], [0, nh - 1]])
    dst = np.float32(
        [
            [x0 + nw * 0.04, y0 + nh * 0.10],
            [x0 + nw * 0.96, y0],
            [x0 + nw, y0 + nh * 0.90],
            [x0 + nw * 0.08, y0 + nh],
        ]
    )
    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(resized, matrix, (bw, bh))
    mask = cv2.warpPerspective(np.full((nh, nw), 255, np.uint8), matrix, (bw, bh))
    sel = mask > 16
    bg[sel] = warped[sel]
    ys, xs = np.where(sel)
    box = (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
    return bg, box


def _paste_rect(background: np.ndarray, crop: np.ndarray, *, corner: str) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    bg = background.copy()
    bh, bw = bg.shape[:2]
    ch, cw = crop.shape[:2]
    target = max(36, int(min(bh, bw) * 0.22))
    scale = target / float(max(ch, cw))
    nw = max(20, int(round(cw * scale)))
    nh = max(20, int(round(ch * scale)))
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_CUBIC)
    if corner == "bl":
        x0 = int(bw * 0.08)
        y0 = int(bh * 0.62)
    else:
        x0 = int(bw * 0.55)
        y0 = int(bh * 0.12)
    x0 = min(max(0, x0), bw - nw)
    y0 = min(max(0, y0), bh - nh)
    bg[y0 : y0 + nh, x0 : x0 + nw] = resized
    return bg, (x0, y0, nw, nh)


def _iou(a: tuple[int, int, int, int], b: tuple[float, float, float, float]) -> float:
    ax2, ay2 = a[0] + a[2], a[1] + a[3]
    bx2, by2 = b[0] + b[2], b[1] + b[3]
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = float(a[2] * a[3]) + max(0.0, b[2]) * max(0.0, b[3]) - inter
    if union <= 0:
        return 0.0
    return float(inter / union)


def _center_inside(match: tuple[float, float, float, float], gt: tuple[int, int, int, int]) -> bool:
    if match[2] <= 1 or match[3] <= 1:
        return False
    cx = gt[0] + gt[2] / 2.0
    cy = gt[1] + gt[3] / 2.0
    return match[0] <= cx <= match[0] + match[2] and match[1] <= cy <= match[1] + match[3]


def _proposal_iou(image: np.ndarray, gt: tuple[int, int, int, int]) -> float:
    from semblon.region_encoder import proposal_boxes

    best = 0.0
    for box in proposal_boxes(image):
        prop = (box[0], box[1], box[2] - box[0], box[3] - box[1])
        best = max(best, _iou(gt, prop))
    return best


def _insert_run(conn) -> None:
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "photo-eval", 384, "l2", "{}", "{}", "x64", "emulated"),
    )


def _add(conn, root: Path, media_id: str, image: np.ndarray) -> None:
    from semblon.observers import observe_bgr

    path = root / f"{media_id}.png"
    cv2.imwrite(str(path), image)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        (media_id, "folder", str(path), media_id, int(image.shape[1]), int(image.shape[0]), 0, 1),
    )
    conn.execute(
        "INSERT INTO observations VALUES (?,?,?,?,?)",
        (f"o-{media_id}", media_id, None, None, "r1"),
    )
    observe_bgr(conn, observation_id=f"o-{media_id}", run_id="r1", img=image, observers=("region",))


def run_eval(root: Path | None = None) -> dict:
    from semblon.region_encoder import probe_region_pack
    from semblon.region_search import find_similar_region, search_patches
    from semblon.store import connect, init_db

    ready, note = probe_region_pack()
    if not ready:
        return {"status": "UNAVAILABLE", "reason": note, "cases": []}
    work = root or (ROOT / "docs" / "evidence" / "photo-region-work")
    work.mkdir(parents=True, exist_ok=True)
    store = work / "photo-region.sqlite"
    if store.exists():
        store.unlink()
    conn = connect(store)
    init_db(conn)
    _insert_run(conn)
    built = []
    for name, frac, view_bg, light_bg, dist_bg in CASES:
        source = _bgr(name)
        x, y, w, h = _crop_box(source, frac)
        crop = source[y : y + h, x : x + w].copy()
        view, view_box = _paste_warp(_bgr(view_bg), crop, corner="br")
        light, light_box = _paste_rect(_bgr(light_bg), _relight(crop), corner="bl")
        flat = np.full_like(crop, crop.mean(axis=(0, 1)))
        dist, dist_box = _paste_rect(_bgr(dist_bg), flat, corner="br")
        ids = {
            "query": f"{name}-query",
            "view": f"{name}-view",
            "light": f"{name}-light",
            "dist": f"{name}-dist",
        }
        _add(conn, work, ids["query"], source)
        _add(conn, work, ids["view"], view)
        _add(conn, work, ids["light"], light)
        _add(conn, work, ids["dist"], dist)
        built.append(
            {
                "name": name,
                "ids": ids,
                "query_box": [x, y, w, h],
                "view_box": list(view_box),
                "light_box": list(light_box),
                "dist_box": list(dist_box),
                "view_proposal_iou": round(_proposal_iou(view, view_box), 3),
                "light_proposal_iou": round(_proposal_iou(light, light_box), 3),
                "path": work / f"{ids['query']}.png",
            }
        )
    conn.commit()
    conn.close()
    cases = []
    failures = []
    for case in built:
        product = find_similar_region(
            store,
            image_path=case["path"],
            x=case["query_box"][0],
            y=case["query_box"][1],
            w=case["query_box"][2],
            h=case["query_box"][3],
            media_id=case["ids"]["query"],
            limit=8,
        )
        ranked = [item.get("media_id") for item in product.get("items") or []]

        def _rank(media_id: str) -> int | None:
            return ranked.index(media_id) + 1 if media_id in ranked else None

        def _item(media_id: str) -> dict | None:
            for item in product.get("items") or []:
                if item.get("media_id") == media_id:
                    return item
            return None

        view_id = case["ids"]["view"]
        light_id = case["ids"]["light"]
        dist_id = case["ids"]["dist"]
        view_hit = _item(view_id)
        light_hit = _item(light_id)
        dist_rank = _rank(dist_id)
        view_rank = _rank(view_id)
        light_rank = _rank(light_id)
        view_loc = False
        light_loc = False
        if view_hit and view_hit.get("match_box"):
            box = tuple(view_hit["match_box"])
            view_loc = _center_inside(box, tuple(case["view_box"])) or _iou(tuple(case["view_box"]), box) >= 0.15
        if light_hit and light_hit.get("match_box"):
            box = tuple(light_hit["match_box"])
            light_loc = _center_inside(box, tuple(case["light_box"])) or _iou(tuple(case["light_box"]), box) >= 0.15
        view_ahead = view_rank is not None and (dist_rank is None or view_rank < dist_rank)
        light_ahead = light_rank is not None and (dist_rank is None or light_rank < dist_rank)
        ok = bool(view_ahead and light_ahead and view_loc and light_loc and product.get("engine") == "dinov2-patch")
        row = {
            "name": case["name"],
            "engine": product.get("engine"),
            "understanding": product.get("understanding"),
            "status": product.get("status"),
            "ranked": ranked,
            "view_rank": view_rank,
            "light_rank": light_rank,
            "distractor_rank": dist_rank,
            "view_score": None if not view_hit else round(float(view_hit["score"]), 4),
            "light_score": None if not light_hit else round(float(light_hit["score"]), 4),
            "view_located": view_loc,
            "light_located": light_loc,
            "view_proposal_iou": case["view_proposal_iou"],
            "light_proposal_iou": case["light_proposal_iou"],
            "pass": ok,
        }
        if not ok:
            # Raw scores, including neighbours the floor dropped.
            from semblon.region_search import crop_bgr

            crop = crop_bgr(case["path"], *case["query_box"])
            raw = search_patches(
                store,
                crop,
                limit=12,
                exclude_media_id=case["ids"]["query"],
                keep_weak=True,
            )
            row["raw"] = [
                {
                    "media_id": item.get("media_id"),
                    "score": round(float(item.get("score") or 0), 4),
                    "coverage": round(float(item.get("coverage") or 0), 4),
                    "above_floor": bool(item.get("above_floor")),
                }
                for item in raw.get("items") or []
                if item.get("media_id") in {view_id, light_id, dist_id}
            ]
            failures.append(case["name"])
        cases.append(row)
        print(
            f"{case['name']}: view#{view_rank} light#{light_rank} dist#{dist_rank} "
            f"loc {view_loc}/{light_loc} proposal {case['view_proposal_iou']}/{case['light_proposal_iou']} "
            f"{'PASS' if ok else 'FAIL'}"
        )
    report = {
        "status": "PASS" if not failures else "FAIL",
        "method": "DINOv2 ViT-S/14 content patches, late interaction max-sim",
        "sources": "scikit-image photographs; homography viewpoint; gamma lighting; mean-colour distractor",
        "floors": {
            "token": 0.35,
            "score": 0.28,
            "coverage": 0.28,
        },
        "cases": cases,
        "failures": failures,
        "bar": "viewpoint and lighting both rank above the same-colour distractor and the match box meets the paste",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_eval()
    print(report.get("status"), "failures", report.get("failures"))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
