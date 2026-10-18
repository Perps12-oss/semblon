"""Generated textured-object check. Not photographs and not an owner-photo study.

Renders a few objects with noise texture, a lighting gradient, and an affine
change, indexes them with the production observer, and queries a tight crop.
Writes docs/evidence/visual-discovery-eval-rendered.json.

    .venv-312\\Scripts\\python.exe tools\\eval_rendered_regions.py
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


def _texture(shape, seed: int, tint) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 40, size=(24, 24, 1), dtype=np.uint8)
    import cv2

    noise = cv2.resize(small, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
    if noise.ndim == 2:
        noise = noise[:, :, None]
    base = np.zeros((shape[0], shape[1], 3), dtype=np.uint8)
    base[:, :] = tint
    return cv2.add(base, np.repeat(noise, 3, axis=2))


def _paint(canvas, mask, texture) -> None:
    canvas[mask] = texture[mask]


def _object(kind: str, *, angle: float, light: float, seed: int) -> np.ndarray:
    import cv2

    canvas = _texture((180, 180), seed + 7, (90, 80, 70))
    layer = np.zeros_like(canvas)
    mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
    if kind == "mug":
        cv2.ellipse(mask, (90, 96), (28, 36), 0, 0, 360, 255, -1)
        cv2.ellipse(mask, (122, 96), (16, 10), 0, -80, 80, 255, 6)
    elif kind == "tile":
        cv2.rectangle(mask, (48, 70), (132, 112), 255, -1)
    else:
        raise ValueError(kind)
    texture = _texture(canvas.shape[:2], seed, (40, 70, 160))
    yy = np.linspace(0.75, light, canvas.shape[0], dtype=np.float32)[:, None]
    texture = np.clip(texture.astype(np.float32) * yy[:, :, None], 0, 255).astype(np.uint8)
    _paint(layer, mask > 0, texture)
    matrix = cv2.getRotationMatrix2D((90, 90), angle, 1.0)
    warped = cv2.warpAffine(layer, matrix, (180, 180))
    wmask = cv2.warpAffine(mask, matrix, (180, 180))
    _paint(canvas, wmask > 0, warped)
    return canvas


def _tight(image: np.ndarray) -> tuple[int, int, int, int]:
    corner = image[0, 0].astype(np.int16)
    diff = np.abs(image.astype(np.int16) - corner).sum(axis=2)
    ys, xs = np.where(diff > 50)
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
    root = ROOT / "docs" / "evidence"
    work = root / "visual-discovery-rendered"
    work.mkdir(parents=True, exist_ok=True)
    specs = [
        ("mug0.png", "mug", 0, 1.05, 1, "mug"),
        ("mug1.png", "mug", 16, 0.85, 1, "mug"),
        ("mug2.png", "mug", -12, 1.2, 2, "mug"),
        ("tile0.png", "tile", 0, 1.0, 1, "tile"),
        ("tile1.png", "tile", 8, 0.9, 3, "tile"),
    ]
    rows = []
    for name, kind, angle, light, seed, group in specs:
        image = _object(kind, angle=angle, light=light, seed=seed)
        path = work / name
        ok, buf = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError(name)
        path.write_bytes(buf.tobytes())
        rows.append({"name": name, "path": path, "group": group})
    store = root / "visual-discovery-rendered.sqlite"
    if store.exists():
        store.unlink()
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "rendered", 384, "l2", "{}", "{}", "x64", "emulated"),
    )
    images = {}
    t0 = time.perf_counter()
    for index, row in enumerate(rows):
        image = cv2.imdecode(np.frombuffer(row["path"].read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        images[row["name"]] = image
        media_id = f"m{index}"
        row["media_id"] = media_id
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(row["path"]), media_id, 180, 180, 0, image.nbytes),
        )
        conn.execute(
            "INSERT INTO observations VALUES (?,?,?,?,?)",
            (f"o{index}", media_id, None, None, "r1"),
        )
        observe_bgr(conn, observation_id=f"o{index}", run_id="r1", img=image, observers=("region",))
    conn.commit()
    conn.close()
    index_s = time.perf_counter() - t0
    queries = [row for row in rows if row["group"] == "mug"]
    hits = 0
    tile_top1 = 0
    details = []
    for query in queries:
        x, y, w, h = _tight(images[query["name"]])
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
        similar = rec["similar"]
        ranked = []
        for item in similar.get("items") or []:
            match = next(row for row in rows if row["media_id"] == item["media_id"])
            ranked.append({"name": match["name"], "group": match["group"], "score": item["score"]})
        if any(item["group"] == "mug" for item in ranked):
            hits += 1
        if ranked and ranked[0]["group"] == "tile":
            tile_top1 += 1
        details.append({"query": query["name"], "basis": similar.get("similarity_basis"), "ranked": ranked})
    report = {
        "corpus": "generated-textured-objects",
        "not": "photographs or an owner-photo study",
        "model": f"{MODEL_FAMILY} onnx {POOL}",
        "floor": REGION_SCORE_FLOOR,
        "queries": len(queries),
        "mug_hit_at_5": round(hits / max(1, len(queries)), 3),
        "tile_top1": tile_top1,
        "index_seconds": round(index_s, 3),
        "details": details,
    }
    out = root / "visual-discovery-eval-rendered.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
