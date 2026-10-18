"""Synthetic region-retrieval eval. Not a real-world photo benchmark.

Builds a small generated corpus, indexes it with the production observer,
and queries crops through remember_and_find. Prints Recall@5, Precision@5,
a colour-confuser false-positive count, and latency.

    .venv-312\\Scripts\\python.exe tools\\eval_visual_discovery.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _glyph(canvas, origin, scale, colour, kind: str) -> None:
    import cv2

    ox, oy = origin
    if kind == "mark":
        # Asymmetric mark: tall stem, short foot, offset dot. Not a circle.
        cv2.rectangle(canvas, (ox, oy), (ox + int(8 * scale), oy + int(36 * scale)), colour, -1)
        cv2.rectangle(
            canvas,
            (ox, oy + int(28 * scale)),
            (ox + int(26 * scale), oy + int(36 * scale)),
            colour,
            -1,
        )
        cv2.circle(canvas, (ox + int(22 * scale), oy + int(8 * scale)), max(2, int(4 * scale)), colour, -1)
    elif kind == "disc":
        cv2.circle(canvas, (ox + int(16 * scale), oy + int(16 * scale)), max(6, int(14 * scale)), colour, -1)
    elif kind == "bar":
        cv2.rectangle(
            canvas,
            (ox, oy + int(12 * scale)),
            (ox + int(40 * scale), oy + int(22 * scale)),
            colour,
            -1,
        )


def _scene(kind: str, *, angle: float, scale: float, background, colour, shift=(0, 0)) -> np.ndarray:
    import cv2

    canvas = np.full((160, 160, 3), background, dtype=np.uint8)
    layer = np.zeros_like(canvas)
    _glyph(layer, (50 + shift[0], 46 + shift[1]), scale, colour, kind)
    matrix = cv2.getRotationMatrix2D((80, 80), angle, 1.0)
    warped = cv2.warpAffine(layer, matrix, (160, 160), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    mask = warped.sum(axis=2) > 0
    canvas[mask] = warped[mask]
    return canvas


def _write(folder: Path, name: str, image: np.ndarray) -> Path:
    import cv2

    path = folder / name
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(name)
    path.write_bytes(buf.tobytes())
    return path


def build_corpus(folder: Path) -> list[dict]:
    folder.mkdir(parents=True, exist_ok=True)
    specs = [
        ("a0.png", "mark", 0, 1.0, (245, 245, 245), (40, 50, 210), (0, 0), "mark"),
        ("a1.png", "mark", 18, 1.05, (230, 235, 220), (30, 40, 190), (6, -4), "mark"),
        ("a2.png", "mark", -25, 0.85, (30, 30, 30), (80, 90, 230), (-8, 6), "mark"),
        ("a3.png", "mark", 8, 1.2, (200, 180, 160), (20, 30, 160), (4, 8), "mark"),
        ("b0.png", "disc", 0, 1.0, (245, 245, 245), (40, 50, 210), (0, 0), "disc"),
        ("b1.png", "disc", 15, 0.9, (30, 30, 30), (30, 40, 190), (8, 0), "disc"),
        ("c0.png", "bar", 0, 1.0, (245, 245, 245), (40, 50, 210), (0, 0), "bar"),
        ("c1.png", "bar", -10, 1.1, (180, 200, 210), (50, 60, 200), (0, 4), "bar"),
        ("small.png", "mark", 0, 0.45, (250, 250, 250), (40, 50, 210), (30, -20), "mark"),
    ]
    rows = []
    for name, kind, angle, scale, background, colour, shift, group in specs:
        path = _write(folder, name, _scene(kind, angle=angle, scale=scale, background=background, colour=colour, shift=shift))
        rows.append({"name": name, "path": path, "group": group, "role": "positive" if group == "mark" else "confuser"})
    # Clutter: the mark plus a disc.
    clutter = _scene("mark", angle=5, scale=0.7, background=(250, 248, 240), colour=(40, 50, 210), shift=(-20, 10))
    _glyph(clutter, (100, 90), 0.8, (40, 160, 40), "disc")
    rows.append(
        {
            "name": "clutter.png",
            "path": _write(folder, "clutter.png", clutter),
            "group": "mark",
            "role": "positive",
        }
    )
    return rows


def _crop_box(image: np.ndarray) -> tuple[int, int, int, int]:
    """Tight box around non-background pixels. Falls back to the center."""
    gray = image.reshape(-1, 3).astype(np.int16)
    # Background is the corner colour.
    corner = image[0, 0].astype(np.int16)
    diff = np.abs(image.astype(np.int16) - corner).sum(axis=2)
    ys, xs = np.where(diff > 40)
    if len(xs) < 10:
        return 40, 40, 80, 80
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    return x1, y1, max(8, x2 - x1), max(8, y2 - y1)


def main() -> int:
    import cv2

    from semblon.observers import observe_bgr
    from semblon.region_encoder import MODEL_FAMILY, POOL, REGION_SCORE_FLOOR, probe_region_pack
    from semblon.region_search import remember_and_find
    from semblon.store import connect, init_db

    ready, note = probe_region_pack()
    if not ready:
        print(json.dumps({"status": "UNAVAILABLE", "note": note}))
        return 2
    root = Path(__file__).resolve().parents[1] / "docs" / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    work = root / "visual-discovery-corpus"
    if work.exists():
        for child in work.glob("*"):
            if child.is_file():
                child.unlink()
    rows = build_corpus(work)
    store = root / "visual-discovery-eval.sqlite"
    if store.exists():
        store.unlink()
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "eval", 384, "l2", "{}", "{}", "x64", "emulated"),
    )
    images = {}
    t_index = time.perf_counter()
    for index, row in enumerate(rows):
        image = cv2.imdecode(np.frombuffer(row["path"].read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        images[row["name"]] = image
        media_id = f"m{index}"
        row["media_id"] = media_id
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(row["path"]), media_id, 160, 160, 0, image.nbytes),
        )
        conn.execute(
            "INSERT INTO observations VALUES (?,?,?,?,?)",
            (f"o{index}", media_id, None, None, "r1"),
        )
        observe_bgr(conn, observation_id=f"o{index}", run_id="r1", img=image, observers=("region", "color"))
    conn.commit()
    conn.close()
    index_s = time.perf_counter() - t_index

    by_name = {row["name"]: row for row in rows}
    queries = [row for row in rows if row["group"] == "mark"]
    hits = 0
    precision_num = 0
    precision_den = 0
    colour_false = 0
    region_false_top1 = 0
    latencies = []
    details = []
    for query in queries:
        image = images[query["name"]]
        x, y, w, h = _crop_box(image)
        started = time.perf_counter()
        rec = remember_and_find(
            store,
            media_id=query["media_id"],
            image_path=query["path"],
            x=x,
            y=y,
            w=w,
            h=h,
            limit=5,
        )
        latencies.append(time.perf_counter() - started)
        similar = rec["similar"]
        ranked = []
        for item in similar.get("items") or []:
            match = next(row for row in rows if row["media_id"] == item["media_id"])
            ranked.append({"name": match["name"], "group": match["group"], "score": item["score"]})
        positives = [item for item in ranked if item["group"] == "mark"]
        if positives:
            hits += 1
        if ranked and ranked[0]["group"] != "mark":
            region_false_top1 += 1
        if any(item["group"] == "bar" for item in ranked[:1]):
            colour_false += 1
        precision_num += len(positives)
        precision_den += len(ranked)
        details.append(
            {
                "query": query["name"],
                "basis": similar.get("similarity_basis"),
                "status": similar.get("status"),
                "ranked": ranked,
            }
        )
    other_marks = 0
    other_marks_hit = 0
    for detail, query in zip(details, queries):
        wanted = {
            row["name"]
            for row in rows
            if row["group"] == "mark" and row["name"] != query["name"]
        }
        got = {item["name"] for item in detail["ranked"] if item["group"] == "mark"}
        other_marks += len(wanted)
        other_marks_hit += len(got & wanted)
    n = max(1, len(queries))
    report = {
        "corpus": "synthetic-glyphs",
        "not": "real-world photo eval",
        "model": f"{MODEL_FAMILY} onnx {POOL} letterbox-224 imagenet",
        "pool": POOL,
        "floor": REGION_SCORE_FLOOR,
        "queries": len(queries),
        "recall_at_5": round(hits / n, 3),
        "other_mark_recall_at_5": round(other_marks_hit / other_marks, 3) if other_marks else None,
        "precision_at_5": round(precision_num / precision_den, 3) if precision_den else None,
        "returned": precision_den,
        "top1_not_mark": region_false_top1,
        "top1_colour_bar": colour_false,
        "index_seconds": round(index_s, 3),
        "query_latency_s_mean": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "query_latency_s_max": round(max(latencies), 3) if latencies else None,
        "details": details,
    }
    pool = POOL
    out = root / "visual-discovery-eval.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
