"""Deterministic synthetic corpus for small-object recall.

Every picture is drawn by this file. There are no external photographs and
nothing here is a picture of a real object. An "instance" is one generated
sprite, scaled and transformed into several pictures. Relevance is that
instance id, not a similarity score and not a shared category.

Size bands are the selection box's area as a percentage of the picture:
very small below 0.1, small 0.1–0.5, medium-small 0.5–1, larger control 1–3.
They are labels for the evaluation, not search thresholds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

SEED = 20261025
CANVAS_W = 960
CANVAS_H = 640
GENERATOR = "semblon-small-object-corpus-1"

BANDS = ("very_small", "small", "medium_small", "larger")


def _band_or_none(area_frac: float) -> str | None:
    pct = float(area_frac) * 100.0
    if pct < 0.1:
        return "very_small"
    if pct < 0.5:
        return "small"
    if pct < 1.0:
        return "medium_small"
    if pct <= 3.0:
        return "larger"
    return None


def size_band(area_frac: float) -> str:
    band = _band_or_none(area_frac)
    if band is None:
        pct = float(area_frac) * 100.0
        raise ValueError(f"box is {pct:.3f}% of the picture, outside the labelled bands")
    return band


def _stripe_sprite(stripe_seed: int, dot_seed: int, category: str, colors=None):
    rng = np.random.default_rng(stripe_seed)
    if category == "tag":
        height, width = 168, 368
    elif category == "shard":
        height, width = 336, 152
    else:
        height = width = 256
    if colors is None:
        first = rng.integers(15, 235, size=3)
        second = rng.integers(15, 235, size=3)
    else:
        first, second = colors
    angle = float(rng.uniform(0.0, np.pi))
    freq = int(rng.integers(7, 15))
    yy, xx = np.indices((height, width))
    coord = xx * np.cos(angle) + yy * np.sin(angle)
    stripe = (np.floor(coord / freq).astype(np.int32) % 2) == 0
    image = np.zeros((height, width, 3), np.uint8)
    image[stripe] = np.asarray(first, np.uint8)
    image[~stripe] = np.asarray(second, np.uint8)
    dots = np.random.default_rng(dot_seed)
    for _ in range(7):
        center = (int(dots.integers(10, width - 10)), int(dots.integers(10, height - 10)))
        color = tuple(int(v) for v in dots.integers(0, 255, size=3))
        cv2.circle(image, center, int(dots.integers(6, 18)), color, -1)
    mask = np.zeros((height, width), np.uint8)
    if category == "medallion":
        cv2.circle(mask, (width // 2, height // 2), width // 2 - 2, 255, -1)
    elif category == "tile":
        cv2.rectangle(mask, (10, 10), (width - 10, height - 10), 255, -1)
    elif category == "tag":
        radius = height // 2 - 4
        cv2.rectangle(mask, (radius, 4), (width - radius, height - 4), 255, -1)
        cv2.circle(mask, (radius, height // 2), radius, 255, -1)
        cv2.circle(mask, (width - radius, height // 2), radius, 255, -1)
    elif category == "shard":
        points = np.array(
            [[width // 2, 2], [width - 2, height // 2], [width // 2, height - 2], [2, height // 2]],
            np.int32,
        )
        cv2.fillConvexPoly(mask, points, 255)
    else:
        raise ValueError(category)
    image[mask == 0] = 0
    return image, mask, (np.asarray(first, np.int32), np.asarray(second, np.int32))


def _transform(image, mask, scale: float, rotation: float, shear: float):
    scaled = cv2.resize(
        image,
        (max(4, int(round(image.shape[1] * scale))), max(4, int(round(image.shape[0] * scale)))),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
    )
    smask = cv2.resize(
        mask,
        (scaled.shape[1], scaled.shape[0]),
        interpolation=cv2.INTER_NEAREST,
    )
    height, width = scaled.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
    matrix[0, 1] += shear
    # Room for rotation and shear so the sprite is not clipped by the warp itself.
    pad = int(max(width, height) * (0.6 + abs(shear)))
    canvas = np.zeros((height + 2 * pad, width + 2 * pad, 3), np.uint8)
    cmask = np.zeros((height + 2 * pad, width + 2 * pad), np.uint8)
    canvas[pad : pad + height, pad : pad + width] = scaled
    cmask[pad : pad + height, pad : pad + width] = smask
    matrix[0, 2] += pad
    matrix[1, 2] += pad
    out_w = width + 2 * pad
    out_h = height + 2 * pad
    warped = cv2.warpAffine(canvas, matrix, (out_w, out_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    wmask = cv2.warpAffine(cmask, matrix, (out_w, out_h), flags=cv2.INTER_NEAREST, borderValue=0)
    ys, xs = np.where(wmask > 0)
    if len(xs) == 0:
        raise RuntimeError("transform erased the sprite")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return warped[y0:y1, x0:x1], wmask[y0:y1, x0:x1]


def _lighting(image, mask, gain: float, bias: int):
    lit = np.clip(image.astype(np.float32) * gain + bias, 0, 255).astype(np.uint8)
    lit[mask == 0] = 0
    return lit


def _background(rng: np.random.Generator, clutter: str):
    top = rng.integers(70, 190, size=3)
    bottom = rng.integers(30, 160, size=3)
    ramp = np.linspace(0.0, 1.0, CANVAS_H, dtype=np.float32)[:, None, None]
    image = (top * (1.0 - ramp) + bottom * ramp).astype(np.uint8)
    image = np.broadcast_to(image, (CANVAS_H, CANVAS_W, 3)).copy()
    noise = rng.integers(-10, 11, size=image.shape, dtype=np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    blobs = {"low": 6, "medium": 22, "high": 55}[clutter]
    for _ in range(blobs):
        center = (int(rng.integers(0, CANVAS_W)), int(rng.integers(0, CANVAS_H)))
        axes = (int(rng.integers(12, 90)), int(rng.integers(8, 48)))
        color = tuple(int(v) for v in rng.integers(0, 255, size=3))
        cv2.ellipse(image, center, axes, int(rng.integers(0, 180)), 0, 360, color, -1)
    return image


def _anchor(place: str, sprite_w: int, sprite_h: int, rng: np.random.Generator):
    if place == "center":
        return CANVAS_W // 2, CANVAS_H // 2
    if place == "edge":
        # Most of the sprite stays inside, a slice is past the left border.
        return int(sprite_w * 0.32), CANVAS_H // 2
    if place == "corner":
        return int(sprite_w * 0.38), int(sprite_h * 0.38)
    if place == "offcenter":
        return int(CANVAS_W * 0.68), int(CANVAS_H * 0.36)
    if place == "lower":
        return int(CANVAS_W * 0.55), int(CANVAS_H * 0.72)
    # Distractors and fillers: stay away from the middle so they do not cover the subject.
    return int(rng.integers(sprite_w, CANVAS_W - sprite_w // 2)), int(
        rng.integers(sprite_h, CANVAS_H - sprite_h // 2)
    )


def _blit(canvas, sprite, mask, cx: int, cy: int):
    height, width = sprite.shape[:2]
    x0, y0 = int(cx - width / 2), int(cy - height / 2)
    laid = np.zeros(canvas.shape[:2], np.uint8)
    src_x0 = max(0, -x0)
    src_y0 = max(0, -y0)
    dst_x0 = max(0, x0)
    dst_y0 = max(0, y0)
    src_x1 = min(width, CANVAS_W - x0)
    src_y1 = min(height, CANVAS_H - y0)
    if src_x1 <= src_x0 or src_y1 <= src_y0:
        return laid
    part = mask[src_y0:src_y1, src_x0:src_x1] > 0
    view = canvas[dst_y0 : dst_y0 + part.shape[0], dst_x0 : dst_x0 + part.shape[1]]
    sprite_view = sprite[src_y0:src_y1, src_x0:src_x1]
    view[part] = sprite_view[part]
    laid[dst_y0 : dst_y0 + part.shape[0], dst_x0 : dst_x0 + part.shape[1]][part] = 255
    return laid


def _aabb(mask: np.ndarray):
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    x, y = int(xs.min()), int(ys.min())
    w, h = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    return x, y, w, h


def _compose_once(spec: dict, sprites: dict, scale: float, rng: np.random.Generator):
    subject = sprites[spec["instance_id"]]
    image, mask = _transform(
        subject["image"], subject["mask"], scale, spec.get("rotation", 0.0), spec.get("shear", 0.0)
    )
    image = _lighting(image, mask, spec.get("light", 1.0), spec.get("bias", 0))
    canvas = _background(rng, spec.get("clutter", "low"))
    for extra in spec.get("distractors") or []:
        other = sprites[extra["instance_id"]]
        oimg, omask = _transform(
            other["image"], other["mask"], extra["scale"], extra.get("rotation", 0.0), 0.0
        )
        ox, oy = extra["xy"]
        _blit(canvas, oimg, omask, ox, oy)
    cx, cy = _anchor(spec.get("place", "center"), image.shape[1], image.shape[0], rng)
    laid = _blit(canvas, image, mask, cx, cy)
    before = canvas.copy()
    cover = 0.0
    occ = float(spec.get("occlusion", 0.0))
    if occ > 0 and laid.any():
        box = _aabb(laid)
        attempt = 0
        while cover < occ - 0.05 and attempt < 8 and box is not None:
            attempt += 1
            bw = max(4, int(box[2] * rng.uniform(0.35, 0.7)))
            bh = max(4, int(box[3] * rng.uniform(0.25, 0.55)))
            center = (
                int(box[0] + rng.integers(0, max(1, box[2]))),
                int(box[1] + rng.integers(0, max(1, box[3]))),
            )
            color = tuple(int(v) for v in rng.integers(20, 80, size=3))
            cv2.ellipse(canvas, center, (bw // 2, bh // 2), int(rng.integers(0, 90)), 0, 360, color, -1)
            changed = np.any(canvas != before, axis=2) & (laid > 0)
            cover = float(changed.sum()) / float(max(1, (laid > 0).sum()))
    if spec.get("reflection"):
        # A faded copy directly under the subject. It is not a second instance.
        ref = cv2.flip(image, 0)
        rmask = cv2.flip(mask, 0)
        ref = np.clip(ref.astype(np.float32) * 0.35, 0, 255).astype(np.uint8)
        _blit(canvas, ref, rmask, cx, min(CANVAS_H - 1, cy + image.shape[0] // 2))
    if spec.get("jpeg"):
        ok, buf = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), int(spec["jpeg"])])
        if not ok:
            raise RuntimeError("jpeg encode failed")
        canvas = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    box = _aabb(laid)
    if box is None:
        raise RuntimeError(f"{spec['photo_id']} lost its subject")
    visible = int((laid > 0).sum())
    return canvas, box, visible, int(round(cover * visible))


def _fit_scale(spec: dict, sprites: dict):
    target = float(spec["area_frac"])
    lo, hi = 0.02, 1.2
    chosen = None
    for _ in range(18):
        mid = (lo + hi) / 2.0
        rng = np.random.default_rng(spec["render_seed"])
        try:
            _canvas, box, _visible, _occluded = _compose_once(spec, sprites, mid, rng)
        except RuntimeError:
            lo = mid
            continue
        frac = (box[2] * box[3]) / float(CANVAS_W * CANVAS_H)
        chosen = mid
        band = _band_or_none(frac)
        if band == spec["band"] and abs(frac - target) / target <= 0.12:
            return mid
        if band is None or frac > target:
            hi = mid
        else:
            lo = mid
    if chosen is None:
        raise RuntimeError(f"{spec['photo_id']} could not be placed in {spec['band']}")
    return chosen


def build_sprites():
    medallion, mmask, mcolors = _stripe_sprite(1101, 1102, "medallion")
    other, omask, _ocolors = _stripe_sprite(2201, 2202, "medallion")
    tag, tmask, tcolors = _stripe_sprite(3301, 3302, "tag")
    near, nmask, _ncolors = _stripe_sprite(3301, 9902, "tag", colors=tcolors)
    shard, smask, _scolors = _stripe_sprite(4401, 4402, "shard")
    return {
        "inst-medallion": {"image": medallion, "mask": mmask, "category": "medallion", "colors": mcolors},
        "inst-medallion-other": {"image": other, "mask": omask, "category": "medallion", "colors": None},
        "inst-tag": {"image": tag, "mask": tmask, "category": "tag", "colors": tcolors},
        "inst-tag-near": {"image": near, "mask": nmask, "category": "tag", "colors": tcolors},
        "inst-shard": {"image": shard, "mask": smask, "category": "shard", "colors": None},
    }


def _photo_specs():
    """Declarative pictures. Query rows carry the size band they must land in."""
    specs = []
    number = 1

    def add(**kwargs):
        nonlocal number
        kwargs["photo_id"] = f"p{number:02d}"
        kwargs["render_seed"] = SEED + number * 1009
        specs.append(kwargs)
        number += 1

    bands = (
        ("very_small", 0.00055),
        ("small", 0.0024),
        ("medium_small", 0.0072),
        ("larger", 0.018),
    )
    for instance in ("inst-medallion", "inst-tag", "inst-shard"):
        for band, frac in bands:
            add(
                instance_id=instance,
                role="query",
                band=band,
                area_frac=frac,
                place="center",
                rotation=0.0,
                shear=0.0,
                occlusion=0.0,
                light=1.0,
                bias=0,
                clutter="low",
                jpeg=None,
                reflection=False,
                variant="clean-center",
            )
    for instance in ("inst-medallion", "inst-tag"):
        add(
            instance_id=instance,
            role="query",
            band="small",
            area_frac=0.0024,
            place="edge",
            rotation=0.0,
            shear=0.0,
            occlusion=0.0,
            light=1.0,
            bias=0,
            clutter="low",
            jpeg=None,
            reflection=False,
            variant="clean-edge",
        )
        add(
            instance_id=instance,
            role="query",
            band="small",
            area_frac=0.0026,
            place="center",
            rotation=0.0,
            shear=0.0,
            occlusion=0.45,
            light=0.85,
            bias=-6,
            clutter="high",
            jpeg=48,
            reflection=False,
            variant="occluded-clutter",
            distractors="category",
        )
        add(
            instance_id=instance,
            role="query",
            band="medium_small",
            area_frac=0.0075,
            place="offcenter",
            rotation=32.0,
            shear=0.22,
            occlusion=0.15,
            light=0.62,
            bias=-10,
            clutter="medium",
            jpeg=None,
            reflection=False,
            variant="viewpoint-dim",
        )
        add(
            instance_id=instance,
            role="query",
            band="larger",
            area_frac=0.016,
            place="lower",
            rotation=6.0,
            shear=0.0,
            occlusion=0.0,
            light=1.05,
            bias=4,
            clutter="low",
            jpeg=38,
            reflection=True,
            variant="recompressed-reflection",
        )
    # Same-category and near-copy pictures that are not the queried instances.
    add(
        instance_id="inst-medallion-other",
        role="category_distractor",
        band="small",
        area_frac=0.003,
        place="offcenter",
        rotation=10.0,
        shear=0.0,
        occlusion=0.0,
        light=1.0,
        bias=0,
        clutter="medium",
        jpeg=None,
        reflection=False,
        variant="distractor",
    )
    add(
        instance_id="inst-medallion-other",
        role="category_distractor",
        band="medium_small",
        area_frac=0.008,
        place="center",
        rotation=0.0,
        shear=0.0,
        occlusion=0.2,
        light=0.8,
        bias=0,
        clutter="high",
        jpeg=55,
        reflection=False,
        variant="distractor",
    )
    add(
        instance_id="inst-tag-near",
        role="visual_distractor",
        band="small",
        area_frac=0.0028,
        place="lower",
        rotation=-12.0,
        shear=0.05,
        occlusion=0.0,
        light=1.0,
        bias=0,
        clutter="medium",
        jpeg=None,
        reflection=False,
        variant="distractor",
    )
    add(
        instance_id="inst-tag-near",
        role="visual_distractor",
        band="larger",
        area_frac=0.015,
        place="center",
        rotation=0.0,
        shear=0.0,
        occlusion=0.0,
        light=0.9,
        bias=0,
        clutter="low",
        jpeg=42,
        reflection=True,
        variant="distractor",
    )
    add(instance_id=None, role="unrelated", variant="empty", clutter="low", render_only=True)
    add(instance_id=None, role="unrelated", variant="empty", clutter="high", render_only=True)
    return specs


def _difficulties(spec: dict, box, occlusion_frac: float) -> list[str]:
    labels = []
    if spec.get("place") in {"edge", "corner"}:
        labels.append("edge")
    if occlusion_frac >= 0.25:
        labels.append("occlusion")
    if abs(float(spec.get("rotation") or 0)) >= 20 or abs(float(spec.get("shear") or 0)) >= 0.15:
        labels.append("viewpoint")
    if float(spec.get("light") or 1) <= 0.75 or float(spec.get("light") or 1) >= 1.1:
        labels.append("lighting")
    if spec.get("clutter") == "high":
        labels.append("clutter")
    if spec.get("jpeg"):
        labels.append("compression")
    if spec.get("reflection"):
        labels.append("reflection")
    category = spec.get("category")
    if category == "tag":
        labels.append("wide")
    elif category == "shard":
        labels.append("tall")
    x, y, w, h = box
    if x < 8 or y < 8 or x + w > CANVAS_W - 8 or y + h > CANVAS_H - 8:
        if "edge" not in labels:
            labels.append("edge")
    return labels


def _distractor_placement(spec: dict, sprites: dict):
    if spec.get("distractors") != "category":
        return []
    # A different instance of the same broad family, sitting off to the side.
    if spec["instance_id"] == "inst-medallion":
        other = "inst-medallion-other"
    elif spec["instance_id"] == "inst-tag":
        other = "inst-tag-near"
    else:
        other = "inst-medallion-other"
    sprite = sprites[other]
    return [
        {
            "instance_id": other,
            "scale": 0.22,
            "rotation": 8.0,
            "xy": (int(CANVAS_W * 0.82), int(CANVAS_H * 0.78)),
            "role": "visual_distractor" if other == "inst-tag-near" else "category_distractor",
            "category": sprite["category"],
        }
    ]


def generate(root: Path, seed: int = SEED) -> dict:
    """Write PNGs and a ground-truth manifest. Same seed, same bytes."""
    if seed != SEED:
        raise ValueError("this corpus has one published seed; pass SEED or omit it")
    root = Path(root)
    library = root / "lib"
    library.mkdir(parents=True, exist_ok=True)
    sprites = build_sprites()
    photos = []
    for spec in _photo_specs():
        spec = dict(spec)
        spec["category"] = sprites[spec["instance_id"]]["category"] if spec.get("instance_id") else None
        if spec.get("render_only"):
            rng = np.random.default_rng(spec["render_seed"])
            canvas = _background(rng, spec.get("clutter", "low"))
            objects = []
            box = None
            occlusion_frac = 0.0
        else:
            spec["distractors"] = _distractor_placement(spec, sprites)
            scale = _fit_scale(spec, sprites)
            rng = np.random.default_rng(spec["render_seed"])
            canvas, box, visible, occluded = _compose_once(spec, sprites, scale, rng)
            frac = (box[2] * box[3]) / float(CANVAS_W * CANVAS_H)
            landed = size_band(frac)
            if landed != spec["band"]:
                raise RuntimeError(
                    f"{spec['photo_id']} landed in {landed} at {frac * 100:.3f}% "
                    f"instead of {spec['band']}"
                )
            occlusion_frac = (occluded / visible) if visible else 0.0
            objects = [
                {
                    "instance_id": spec["instance_id"],
                    "category": spec["category"],
                    "role": "instance",
                    "bbox": list(box),
                    "area_frac": (box[2] * box[3]) / float(CANVAS_W * CANVAS_H),
                    "size_band": size_band((box[2] * box[3]) / float(CANVAS_W * CANVAS_H)),
                    "occlusion_frac": round(occlusion_frac, 3),
                    "rotation_deg": spec.get("rotation", 0.0),
                    "shear": spec.get("shear", 0.0),
                    "place": spec.get("place"),
                    "light": spec.get("light", 1.0),
                    "jpeg_quality": spec.get("jpeg"),
                    "reflection": bool(spec.get("reflection")),
                    "clutter": spec.get("clutter"),
                    "variant": spec.get("variant"),
                }
            ]
            for extra in spec["distractors"]:
                objects.append(
                    {
                        "instance_id": extra["instance_id"],
                        "category": extra["category"],
                        "role": extra["role"],
                        "note": "Not the queried instance.",
                    }
                )
        name = f"{spec['photo_id']}.png"
        ok, buf = cv2.imencode(".png", canvas)
        if not ok:
            raise RuntimeError(f"png encode failed for {name}")
        blob = buf.tobytes()
        (library / name).write_bytes(blob)
        photos.append(
            {
                "photo_id": spec["photo_id"],
                "file": name,
                "role": spec["role"],
                "variant": spec.get("variant"),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "width": CANVAS_W,
                "height": CANVAS_H,
                "objects": objects,
                "occlusion_frac": round(occlusion_frac, 3) if not spec.get("render_only") else 0.0,
                "difficulties": [] if spec.get("render_only") or box is None else _difficulties(spec, box, occlusion_frac),
            }
        )
    by_instance: dict[str, list[str]] = {}
    for photo in photos:
        for obj in photo["objects"]:
            if obj.get("role") == "instance":
                by_instance.setdefault(obj["instance_id"], []).append(photo["photo_id"])
    queries = []
    for photo in photos:
        subject = next((obj for obj in photo["objects"] if obj.get("role") == "instance"), None)
        if subject is None or photo["role"] != "query":
            continue
        relevant = [pid for pid in by_instance[subject["instance_id"]] if pid != photo["photo_id"]]
        category_ids = []
        visual_ids = []
        for other in photos:
            if other["photo_id"] == photo["photo_id"]:
                continue
            roles = {obj.get("role") for obj in other["objects"]}
            ids = {obj.get("instance_id") for obj in other["objects"]}
            if subject["instance_id"] in ids and "instance" in roles:
                continue
            if other["role"] == "category_distractor" and other["objects"] and other["objects"][0]["category"] == subject["category"]:
                category_ids.append(other["photo_id"])
            if other["role"] == "visual_distractor" and subject["category"] == "tag":
                visual_ids.append(other["photo_id"])
            for obj in other["objects"]:
                if obj.get("role") == "category_distractor" and obj.get("category") == subject["category"]:
                    if other["photo_id"] not in category_ids:
                        category_ids.append(other["photo_id"])
                if obj.get("role") == "visual_distractor" and subject["instance_id"] == "inst-tag":
                    if other["photo_id"] not in visual_ids:
                        visual_ids.append(other["photo_id"])
        regions = {}
        for pid in relevant:
            host = next(item for item in photos if item["photo_id"] == pid)
            match = next(obj for obj in host["objects"] if obj.get("instance_id") == subject["instance_id"] and obj.get("bbox"))
            regions[pid] = list(match["bbox"])
        queries.append(
            {
                "query_id": f"q-{photo['photo_id']}-{subject['size_band']}",
                "photo_id": photo["photo_id"],
                "instance_id": subject["instance_id"],
                "category": subject["category"],
                "bbox": list(subject["bbox"]),
                "area_frac": subject["area_frac"],
                "size_band": subject["size_band"],
                "variant": photo["variant"],
                "difficulties": list(photo["difficulties"]),
                "occlusion_frac": photo["occlusion_frac"],
                "relevant_photo_ids": relevant,
                "relevant_regions": regions,
                "category_distractor_photo_ids": category_ids,
                "visual_distractor_photo_ids": visual_ids,
                "split": "unassigned",
                "rationale": (
                    f"{subject['instance_id']} is one generated sprite. "
                    f"The relevant pictures are the other composites of that same sprite. "
                    f"Same category ({subject['category']}) or a near copy with different dots "
                    f"is not the same instance and is not relevant."
                ),
            }
        )
    _assign_splits(queries)
    manifest = {
        "generator": GENERATOR,
        "seed": SEED,
        "canvas": [CANVAS_W, CANVAS_H],
        "license": (
            "Procedural pictures produced by tools/small_object_corpus.py. "
            "No external dataset, no owner photographs, no redistributed photographs."
        ),
        "relevance": "same generated sprite (instance id), not category and not embedding score",
        "size_bands_percent_of_picture": {
            "very_small": "<0.1",
            "small": "0.1-0.5",
            "medium_small": "0.5-1",
            "larger": "1-3",
        },
        "limitation": (
            "Synthetic stand-ins, not natural categories. Small on purpose so a miss is informative. "
            "Not a substitute for an owner archive or for Windows ARM64."
        ),
        "photos": photos,
        "queries": queries,
        "counts": {
            "photos": len(photos),
            "queries": len(queries),
            "instances": sorted({q["instance_id"] for q in queries}),
        },
    }
    validate(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _assign_splits(queries: list[dict]) -> None:
    """Alternate within each size band. Chosen from ids only, before any score."""
    grouped: dict[str, list[dict]] = {}
    for query in queries:
        grouped.setdefault(query["size_band"], []).append(query)
    for rows in grouped.values():
        rows.sort(key=lambda query: query["query_id"])
        if len(rows) < 2:
            raise ValueError(f"{rows[0]['size_band']} needs two queries so both splits exist")
        for index, query in enumerate(rows):
            query["split"] = "dev" if index % 2 == 0 else "heldout"


def validate(manifest: dict) -> None:
    photos = {photo["photo_id"]: photo for photo in manifest["photos"]}
    if len(photos) != len(manifest["photos"]):
        raise ValueError("duplicate photo id")
    seen_files = set()
    for photo in manifest["photos"]:
        if photo["file"] in seen_files:
            raise ValueError("duplicate file")
        seen_files.add(photo["file"])
        if photo["width"] != CANVAS_W or photo["height"] != CANVAS_H:
            raise ValueError("canvas changed")
    queries = manifest["queries"]
    if not queries:
        raise ValueError("no queries")
    bands_present = set()
    flags = set()
    for query in queries:
        bands_present.add(query["size_band"])
        photo = photos[query["photo_id"]]
        if query["photo_id"] in query["relevant_photo_ids"]:
            raise ValueError(f"{query['query_id']} lists its own picture")
        if not query["relevant_photo_ids"]:
            raise ValueError(f"{query['query_id']} has no relevant picture")
        band = size_band(query["area_frac"])
        if band != query["size_band"]:
            raise ValueError(f"{query['query_id']} band {query['size_band']} does not match {query['area_frac']}")
        x, y, w, h = query["bbox"]
        if w < 8 or h < 8 or x < 0 or y < 0 or x + w > CANVAS_W or y + h > CANVAS_H:
            raise ValueError(f"{query['query_id']} box is outside the picture or too small")
        expected = (w * h) / float(CANVAS_W * CANVAS_H)
        if abs(expected - query["area_frac"]) > 1e-9:
            raise ValueError(f"{query['query_id']} area does not match the box")
        for pid in query["relevant_photo_ids"]:
            host = photos[pid]
            match = [
                obj
                for obj in host["objects"]
                if obj.get("instance_id") == query["instance_id"] and obj.get("role") == "instance"
            ]
            if len(match) != 1:
                raise ValueError(f"{query['query_id']} relevant {pid} is not that instance")
            if pid not in query["relevant_regions"]:
                raise ValueError(f"{query['query_id']} missing region for {pid}")
        for pid in query["category_distractor_photo_ids"] + query["visual_distractor_photo_ids"]:
            if pid in query["relevant_photo_ids"]:
                raise ValueError(f"{query['query_id']} distractor {pid} is also relevant")
            host = photos[pid]
            if any(obj.get("instance_id") == query["instance_id"] and obj.get("role") == "instance" for obj in host["objects"]):
                raise ValueError(f"{query['query_id']} distractor {pid} contains the instance")
        if query["split"] not in {"dev", "heldout"}:
            raise ValueError("split")
        flags.update(query["difficulties"])
        if not query["rationale"]:
            raise ValueError("missing rationale")
    missing = [band for band in BANDS if band not in bands_present]
    if missing:
        raise ValueError(f"missing bands {missing}")
    for needed in ("occlusion", "edge", "viewpoint", "lighting", "clutter", "compression", "wide", "tall"):
        if needed not in flags:
            raise ValueError(f"no query labelled {needed}")
    dev = [q for q in queries if q["split"] == "dev"]
    held = [q for q in queries if q["split"] == "heldout"]
    if not dev or not held:
        raise ValueError("empty split")
    if {q["size_band"] for q in dev} != set(BANDS) or {q["size_band"] for q in held} != set(BANDS):
        raise ValueError("a split is missing a size band")
    if set(q["query_id"] for q in dev) & set(q["query_id"] for q in held):
        raise ValueError("split overlap")


def checksum(manifest: dict) -> str:
    lines = [f"{photo['photo_id']} {photo['sha256']}" for photo in manifest["photos"]]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
