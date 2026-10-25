"""Local region encoder. DINOv2 ViT-S/14 ONNX when the pack is installed.

Same preprocess, dimension, and versioned pack_id for query crops and the
index. A session or run that exceeds ``ENCODE_TIMEOUT_S`` is abandoned and
later calls fail closed so colour can be labelled as colour.

The earlier session-init hang on this machine was a lock deadlock in this
module, not the ONNX graph. Load stays outside that lock. Measured embed
time after the fix is about two seconds for the first call and under one
second after that, on emulated x64.

Never downloads. Never writes faces.person_id or embeddings.modality='face'.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from pathlib import Path

import numpy as np

# onnx-community/dinov2-small (Apache-2.0). CLS token, not a face embedding.
# SHA-256 of the bytes fetched 2026-10-17 (88,532,934 bytes).
WEIGHT_NAME = "dinov2-vits14.onnx"
PIN_NAME = "semblon-region-pack-pin.json"
SOURCE_COMMIT = "ef1fb1005bfd7768839d18080f7038b403506f87"
SOURCE_URL = (
    "https://huggingface.co/onnx-community/dinov2-small/resolve/"
    + SOURCE_COMMIT
    + "/onnx/model.onnx"
)
KNOWN_SHA256 = {
    WEIGHT_NAME: "f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a",
}

MODEL_FAMILY = "dinov2-vits14"
PACK_VERSION = "1"
INPUT_SIZE = 224
OUTPUT_DIM = 384
POOL = "cls"
ENCODE_TIMEOUT_S = 15.0
# ImageNet mean/std. Letterbox keeps the whole crop (not a center crop).
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
# BGR pad so normalized padding is ~0.
_PAD_BGR = (104, 116, 124)

MODALITY_REGION = "region"
MODALITY_SCENE = "scene"
# One vector per content patch of the whole frame. Not a proposal box.
# Never 'face'. compare_space refuses that modality; this one is a different pack.
MODALITY_PATCH = "region_patch"
PROVIDER = "dinov2-vits14"
# Late-interaction floors for patch max-sim. Chosen on the photographic
# eval in docs/evidence/photo-region-eval.json, not on glyphs and not on identity.
PATCH_TOKEN_FLOOR = 0.35
PATCH_SCORE_FLOOR = 0.28
PATCH_COVERAGE_FLOOR = 0.28
# Cosine on L2 CLS vectors. On the synthetic glyph corpus, floor 0.45 let
# colour-similar different shapes into the list (precision@5 0.633). Floor
# 0.76 drops that band (precision@5 0.857, recall@5 still 1.0, no colour-bar
# top1). A clutter crop that also contains a second object can still rank
# that object first. Chosen on this corpus, not a photo confirmation.
# See docs/evidence/visual-discovery-eval.json.
REGION_SCORE_FLOOR = 0.76
COLOUR_SCORE_FLOOR = 0.85
SCENE_SCORE_FLOOR = 0.50
MAX_REGION_BOXES = 6
# Whole frame plus overlapping windows. The ONNX input is fixed at 224,
# so a small object in a large photo is only a few full-frame patches.
# Windows are not detector proposals: they cover the picture on a grid.
MAX_PATCH_WINDOWS = 9

LABEL_SIMILAR = "Similar look"
LABEL_COLOUR = "Colour only"
LABEL_TEXT = "Text in the selection"
LABEL_FACE = "Same face"
LABEL_UNKNOWN = "Unknown region"

_SESSION = None
_SESSION_KEY: tuple[str, str] | None = None
_PROBE: tuple[str, int, int, bool, str | None] | None = None
_DEAD = False
_LOCK = threading.Lock()
# Separate from _LOCK. Holding _LOCK across session.run deadlocked startup.
_LANE = threading.Lock()
_LANE_META = threading.Lock()
_INTERACTIVE = threading.Event()
_INTERACTIVE_DEPTH = 0
# Indexing yields this long per image, then takes the lane again.
_YIELD_CAP_S = 3.0


class RegionPackError(RuntimeError):
    pass


def region_pack_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    env = (os.environ.get("SEMBLON_REGION_PACK") or "").strip()
    if env:
        return Path(env)
    return Path.home() / ".semblon" / "models" / "region"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_pin(root: Path, digest: str) -> None:
    payload = {
        "sha256": digest,
        "file": WEIGHT_NAME,
        "model": MODEL_FAMILY,
        "source_url": SOURCE_URL,
        "source_commit": SOURCE_COMMIT,
        "license": "Apache-2.0",
        "upstream": "facebookresearch/dinov2 ViT-S/14 via onnx-community/dinov2-small",
        "preprocess": "letterbox-224-imagenet-cls-l2",
        "timeout_s": ENCODE_TIMEOUT_S,
    }
    (Path(root) / PIN_NAME).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def pack_id_for(digest: str) -> str:
    """Family + version + weight hash. The hash is the compare key, not the family name."""
    return f"region/{MODEL_FAMILY}@{PACK_VERSION}/{digest[:16]}/{POOL}"


def pack_id_patches(digest: str) -> str:
    """Same weights as the CLS pack. Patch tokens are a different compare space."""
    return f"region/{MODEL_FAMILY}@{PACK_VERSION}/{digest[:16]}/patch"


def probe_region_pack(root: Path | None = None) -> tuple[bool, str | None]:
    """True only when the ONNX and pin agree with the known digest. Never downloads."""
    global _PROBE
    home = region_pack_dir(root)
    onnx = home / WEIGHT_NAME
    try:
        stat = onnx.stat()
        stamp = (str(home.resolve()), int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        stamp = (str(home), 0, 0)
    with _LOCK:
        if _PROBE is not None and _PROBE[:3] == stamp:
            return _PROBE[3], _PROBE[4]
    def remember(ok: bool, note: str | None) -> tuple[bool, str | None]:
        global _PROBE
        with _LOCK:
            _PROBE = (*stamp, ok, note)
        return ok, note

    if not onnx.is_file():
        return remember(
            False,
            (
                f"unavailable: region encoder missing ({WEIGHT_NAME}). "
                "Run tools/fetch_region_pack.py or place the pinned ONNX under "
                "~/.semblon/models/region/. Colour fallback stays labelled colour."
            ),
        )
    if onnx.stat().st_size < 1024:
        return remember(False, "unavailable: region ONNX looks truncated")
    try:
        digest = _sha256_file(onnx).lower()
    except OSError as exc:
        return remember(False, f"unavailable: region ONNX unreadable ({exc.__class__.__name__})")
    expected = KNOWN_SHA256.get(WEIGHT_NAME, "").lower()
    if not expected or digest != expected:
        return remember(False, "unavailable: region ONNX hash does not match the pinned pack")
    pin = home / PIN_NAME
    if not pin.is_file():
        return remember(False, f"unavailable: region pack pin missing ({PIN_NAME})")
    try:
        pin_data = json.loads(pin.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return remember(False, "unavailable: region pack pin is unreadable")
    if not isinstance(pin_data, dict):
        return remember(False, "unavailable: region pack pin is invalid")
    pin_sha = str(pin_data.get("sha256") or "").strip().lower()
    if pin_sha != digest:
        return remember(False, "unavailable: region pack pin does not match the ONNX")
    return remember(True, None)


def active_pack(root: Path | None = None) -> tuple[str, int] | None:
    """(pack_id, dim) when the pinned pack is present and has not timed out."""
    if _DEAD:
        return None
    ready, _note = probe_region_pack(root)
    if not ready:
        return None
    return pack_id_for(KNOWN_SHA256[WEIGHT_NAME]), OUTPUT_DIM


def _begin_interactive() -> None:
    global _INTERACTIVE_DEPTH
    with _LANE_META:
        _INTERACTIVE_DEPTH += 1
        _INTERACTIVE.set()


def _end_interactive() -> None:
    global _INTERACTIVE_DEPTH
    with _LANE_META:
        _INTERACTIVE_DEPTH = max(0, _INTERACTIVE_DEPTH - 1)
        if _INTERACTIVE_DEPTH == 0:
            _INTERACTIVE.clear()


def _lane_enter(
    *,
    interactive: bool,
    cancelled=None,
    yield_budget: list[float] | None,
) -> None:
    """One ONNX forward at a time. Indexing waits briefly for a Lens search."""
    if interactive:
        _begin_interactive()
    try:
        while True:
            if cancelled is not None and cancelled():
                raise RegionPackError("cancelled")
            if (
                not interactive
                and _INTERACTIVE.is_set()
                and yield_budget is not None
                and yield_budget[0] < _YIELD_CAP_S
            ):
                start = time.monotonic()
                _INTERACTIVE.wait(0.05)
                yield_budget[0] += time.monotonic() - start
                continue
            if not _LANE.acquire(timeout=0.05):
                continue
            if (
                not interactive
                and _INTERACTIVE.is_set()
                and yield_budget is not None
                and yield_budget[0] < _YIELD_CAP_S
            ):
                _LANE.release()
                continue
            return
    except BaseException:
        if interactive:
            _end_interactive()
        raise


def _lane_leave(*, interactive: bool) -> None:
    _LANE.release()
    if interactive:
        _end_interactive()


def _bounded(fn, *, seconds: float = ENCODE_TIMEOUT_S):
    """Run fn on a daemon thread. A hang is remembered and never retried."""
    global _DEAD, _SESSION, _SESSION_KEY
    if _DEAD:
        raise RegionPackError("region encoder timed out; colour fallback is in use")
    box: dict = {}

    def work() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001 — caller decides colour fallback
            box["error"] = exc
        finally:
            box["done"] = True

    thread = threading.Thread(target=work, name="semblon-region-encoder", daemon=True)
    thread.start()
    thread.join(seconds)
    if not box.get("done"):
        with _LOCK:
            _DEAD = True
            _SESSION = None
            _SESSION_KEY = None
        raise RegionPackError("region encoder timed out")
    if "error" in box:
        err = box["error"]
        if isinstance(err, RegionPackError):
            raise err
        raise RegionPackError(str(err) or "region encoder failed") from err
    return box.get("value")


def _session(root: Path | None = None):
    global _SESSION, _SESSION_KEY
    home = region_pack_dir(root)
    key = (str(home.resolve()), KNOWN_SHA256[WEIGHT_NAME])
    with _LOCK:
        if _SESSION is not None and _SESSION_KEY == key:
            return _SESSION
    # Probe takes the same lock. Do not call it while the lock is held.
    ready, note = probe_region_pack(home)
    if not ready:
        raise RegionPackError(note or "region pack unavailable")

    def load():
        import onnxruntime as ort

        return ort.InferenceSession(
            str(home / WEIGHT_NAME),
            providers=["CPUExecutionProvider"],
        )

    session = _bounded(load)
    with _LOCK:
        if _DEAD:
            raise RegionPackError("region encoder timed out; colour fallback is in use")
        if _SESSION is not None and _SESSION_KEY == key:
            return _SESSION
        _SESSION = session
        _SESSION_KEY = key
        return session


def letterbox_geometry(height: int, width: int, size: int = INPUT_SIZE) -> tuple[int, int, int, int]:
    """Content rectangle on the square canvas: x0, y0, resized width, resized height."""
    if height < 1 or width < 1:
        raise RegionPackError("region has no pixels")
    scale = float(size) / float(max(height, width))
    resized_w = max(1, min(size, int(round(width * scale))))
    resized_h = max(1, min(size, int(round(height * scale))))
    x0 = (size - resized_w) // 2
    y0 = (size - resized_h) // 2
    return x0, y0, resized_w, resized_h


def letterbox_bgr(image: np.ndarray, size: int = INPUT_SIZE) -> np.ndarray:
    """Fit the whole crop inside a square. Same pixels in, same canvas out."""
    import cv2

    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise RegionPackError("region encoder needs a BGR image")
    arr = arr[:, :, :3]
    height, width = arr.shape[:2]
    x0, y0, resized_w, resized_h = letterbox_geometry(height, width, size)
    resized = cv2.resize(arr, (resized_w, resized_h), interpolation=cv2.INTER_CUBIC)
    canvas = np.full((size, size, 3), _PAD_BGR, dtype=np.uint8)
    canvas[y0 : y0 + resized_h, x0 : x0 + resized_w] = resized
    return canvas


def _tensor(image_bgr: np.ndarray) -> np.ndarray:
    canvas = letterbox_bgr(image_bgr)
    rgb = canvas[:, :, ::-1].astype(np.float32) / 255.0
    rgb = (rgb - IMAGENET_MEAN) / IMAGENET_STD
    return np.transpose(rgb, (2, 0, 1))[None, ...].astype(np.float32)


def _pool(hidden, *, pool: str) -> np.ndarray:
    """CLS token (index 0) or mean of patch tokens. L2-normalised."""
    array = np.asarray(hidden, dtype=np.float32)
    if array.ndim == 3:
        array = array[0]
    if array.ndim != 2 or array.shape[-1] != OUTPUT_DIM:
        raise RegionPackError(f"unexpected encoder shape {array.shape}")
    if pool == "mean":
        vec = array[1:].mean(axis=0) if array.shape[0] > 1 else array[0]
    else:
        vec = array[0]
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return vec


def _l2(vec: np.ndarray) -> np.ndarray:
    out = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(out))
    if norm > 0:
        out = out / norm
    return out


def _token_matrices(outputs, count: int) -> list[np.ndarray]:
    """One token matrix per batch row. CLS stays at column 0."""
    hidden = None
    for value in outputs:
        arr = np.asarray(value)
        if arr.ndim >= 2 and arr.shape[-1] == OUTPUT_DIM:
            hidden = arr
            break
    if hidden is None:
        raise RegionPackError("region encoder returned no 384-d hidden state")
    array = np.asarray(hidden, dtype=np.float32)
    if array.ndim == 2:
        if count != 1 or array.shape[-1] != OUTPUT_DIM:
            raise RegionPackError(f"unexpected encoder shape {array.shape}")
        return [array]
    if array.ndim != 3 or int(array.shape[0]) != int(count) or array.shape[-1] != OUTPUT_DIM:
        raise RegionPackError(f"unexpected encoder shape {array.shape}")
    return [np.asarray(array[index], dtype=np.float32) for index in range(int(count))]


def _run_hidden(session, tensor: np.ndarray, count: int) -> list[np.ndarray]:
    input_name = session.get_inputs()[0].name
    try:
        outputs = session.run(None, {input_name: tensor})
    except RegionPackError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface a pack failure, do not invent a vector
        raise RegionPackError(f"region encoder failed: {exc.__class__.__name__}") from exc
    return _token_matrices(outputs, count)


def _hidden_now(
    image_bgr: np.ndarray,
    root: Path | None,
    *,
    interactive: bool = False,
    cancelled=None,
    yield_budget: list[float] | None = None,
) -> np.ndarray:
    """Token matrix (CLS at row 0, then patches). One forward. Not normalised."""
    if cancelled is not None and cancelled():
        raise RegionPackError("cancelled")
    session = _session(root)
    tensor = _tensor(image_bgr)
    if cancelled is not None and cancelled():
        raise RegionPackError("cancelled")
    _lane_enter(interactive=interactive, cancelled=cancelled, yield_budget=yield_budget)
    try:
        if cancelled is not None and cancelled():
            raise RegionPackError("cancelled")
        rows = _run_hidden(session, tensor, 1)
    finally:
        _lane_leave(interactive=interactive)
    return rows[0]


def encode_images(
    images: list[np.ndarray],
    root: Path | None = None,
    *,
    interactive: bool = False,
    cancelled=None,
    yield_budget: list[float] | None = None,
) -> list[np.ndarray]:
    """One forward for every still-window and proposal. Same pixels as separate calls.

    The pinned graph takes ``batch_size``. A failed batch falls back to one row
    at a time inside the same call, so indexing does not depend on the batch path.
    """

    def run() -> list[np.ndarray]:
        if cancelled is not None and cancelled():
            raise RegionPackError("cancelled")
        if not images:
            raise RegionPackError("region encoder needs an image")
        session = _session(root)
        tensors = [_tensor(image) for image in images]
        batch = np.concatenate(tensors, axis=0)
        if cancelled is not None and cancelled():
            raise RegionPackError("cancelled")
        _lane_enter(interactive=interactive, cancelled=cancelled, yield_budget=yield_budget)
        try:
            if cancelled is not None and cancelled():
                raise RegionPackError("cancelled")
            try:
                return _run_hidden(session, batch, len(images))
            except RegionPackError as exc:
                if "cancelled" in str(exc):
                    raise
                rows: list[np.ndarray] = []
                for tensor in tensors:
                    if cancelled is not None and cancelled():
                        raise RegionPackError("cancelled")
                    rows.extend(_run_hidden(session, tensor, 1))
                return rows
        finally:
            _lane_leave(interactive=interactive)

    return _bounded(run)


def _embed_now(
    image_bgr: np.ndarray,
    root: Path | None,
    *,
    pool: str,
    interactive: bool = False,
    cancelled=None,
    yield_budget: list[float] | None = None,
) -> bytes:
    hidden = _hidden_now(
        image_bgr,
        root,
        interactive=interactive,
        cancelled=cancelled,
        yield_budget=yield_budget,
    )
    vec = _pool(hidden, pool=pool)
    if vec.size != OUTPUT_DIM:
        raise RegionPackError(f"region encoder dim {vec.size} != {OUTPUT_DIM}")
    return vec.tobytes()


def content_patch_records(
    image_bgr: np.ndarray,
    root: Path | None = None,
    *,
    interactive: bool = False,
    cancelled=None,
    yield_budget: list[float] | None = None,
) -> tuple[bytes, list[dict]]:
    """CLS bytes plus every content patch of this frame.

    Padding patches from letterbox are dropped. Each record's bbox is in
    original-image pixels (x1, y1, x2, y2). One ONNX forward covers the
    whole picture, so a later query can hit a place that was never a proposal.
    """

    def run() -> tuple[bytes, list[dict]]:
        if cancelled is not None and cancelled():
            raise RegionPackError("cancelled")
        hidden = _hidden_now(
            image_bgr,
            root,
            interactive=interactive,
            cancelled=cancelled,
            yield_budget=yield_budget,
        )
        return _split_content_patches(image_bgr, hidden)

    return _bounded(run)


def _split_content_patches(image: np.ndarray, hidden: np.ndarray) -> tuple[bytes, list[dict]]:
    tokens = np.asarray(hidden, dtype=np.float32)
    if tokens.ndim != 2 or tokens.shape[0] < 2 or tokens.shape[1] != OUTPUT_DIM:
        raise RegionPackError(f"unexpected encoder shape {getattr(tokens, 'shape', None)}")
    cls = _l2(tokens[0]).astype(np.float32).tobytes()
    patches = tokens[1:]
    grid = int(round(math.sqrt(patches.shape[0])))
    if grid < 2 or grid * grid != patches.shape[0]:
        raise RegionPackError(f"patch count {patches.shape[0]} is not a square grid")
    height, width = int(image.shape[0]), int(image.shape[1])
    x0, y0, resized_w, resized_h = letterbox_geometry(height, width)
    cell = float(INPUT_SIZE) / float(grid)
    scale_x = float(width) / float(resized_w)
    scale_y = float(height) / float(resized_h)
    records: list[dict] = []
    for index in range(patches.shape[0]):
        gy, gx = divmod(index, grid)
        cx = (gx + 0.5) * cell
        cy = (gy + 0.5) * cell
        if cx < x0 or cy < y0 or cx >= x0 + resized_w or cy >= y0 + resized_h:
            continue
        px1 = max(gx * cell, float(x0))
        py1 = max(gy * cell, float(y0))
        px2 = min((gx + 1) * cell, float(x0 + resized_w))
        py2 = min((gy + 1) * cell, float(y0 + resized_h))
        ox1 = (px1 - x0) * scale_x
        oy1 = (py1 - y0) * scale_y
        ox2 = (px2 - x0) * scale_x
        oy2 = (py2 - y0) * scale_y
        if ox2 - ox1 < 1 or oy2 - oy1 < 1:
            continue
        records.append(
            {
                "blob": _l2(patches[index]).astype(np.float32).tobytes(),
                "bbox": (float(ox1), float(oy1), float(ox2), float(oy2)),
                "gx": int(gx),
                "gy": int(gy),
                "grid": int(grid),
            }
        )
    if not records:
        raise RegionPackError("no content patches")
    return cls, records


def embed_bgr(
    image_bgr: np.ndarray,
    root: Path | None = None,
    *,
    pool: str | None = None,
    interactive: bool = False,
    cancelled=None,
    yield_budget: list[float] | None = None,
) -> bytes:
    """L2-normalised float32 bytes. Raises RegionPackError when the pack cannot run."""
    chosen = pool or POOL
    if chosen not in {"cls", "mean"}:
        raise RegionPackError(f"unknown region pool {chosen}")
    return _bounded(
        lambda: _embed_now(
            image_bgr,
            root,
            pool=chosen,
            interactive=interactive,
            cancelled=cancelled,
            yield_budget=yield_budget,
        )
    )


def crop_box(image: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray:
    height, width = image.shape[:2]
    x1 = max(0, min(width - 1, int(round(box[0]))))
    y1 = max(0, min(height - 1, int(round(box[1]))))
    x2 = max(0, min(width, int(round(box[2]))))
    y2 = max(0, min(height, int(round(box[3]))))
    if x2 <= x1 or y2 <= y1:
        raise RegionPackError("region has no pixels")
    return image[y1:y2, x1:x2].copy()


def proposal_boxes(image: np.ndarray) -> list[tuple[float, float, float, float]]:
    """Detected crops plus one center proposal when detection is thin. Bounded."""
    from semblon.observers import contour_objects

    height, width = image.shape[:2]
    boxes: list[tuple[float, float, float, float]] = []
    seen: list[tuple[float, float, float, float]] = []

    def _add(box: tuple[float, float, float, float]) -> None:
        x1, y1, x2, y2 = box
        if x2 - x1 < 8 or y2 - y1 < 8:
            return
        area = (x2 - x1) * (y2 - y1)
        if area >= 0.95 * width * height:
            return
        for other in seen:
            if _iou(box, other) > 0.8:
                return
        seen.append(box)
        boxes.append(box)

    try:
        from semblon.object_nanodet import detect_objects
        from semblon.object_pack import probe_nanodet_status

        if probe_nanodet_status()[0]:
            for obj in detect_objects(image):
                _add(tuple(float(v) for v in obj["bbox"]))
    except Exception:
        pass
    for obj in contour_objects(image, min_area=64, max_regions=MAX_REGION_BOXES):
        _add(tuple(float(v) for v in obj["bbox"]))
    if len(boxes) < 2:
        margin_x = width * 0.2
        margin_y = height * 0.2
        _add((margin_x, margin_y, width - margin_x, height - margin_y))
    return boxes[:MAX_REGION_BOXES]


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def patch_windows(image: np.ndarray) -> list[tuple[np.ndarray, int, int]]:
    """Full frame, then a coarse grid of overlapping windows. Bounded."""
    height, width = image.shape[:2]
    windows = [(image, 0, 0)]
    if min(height, width) < 64:
        return windows
    for fraction in (0.62, 0.40):
        tile_h = max(48, int(round(height * fraction)))
        tile_w = max(48, int(round(width * fraction)))
        if tile_h >= height - 8 and tile_w >= width - 8:
            continue
        ys = [0, max(0, height - tile_h)]
        xs = [0, max(0, width - tile_w)]
        pairs = [(y0, x0) for y0 in ys for x0 in xs]
        for y0, x0 in pairs:
                if len(windows) >= MAX_PATCH_WINDOWS:
                    return windows
                crop = image[y0 : y0 + tile_h, x0 : x0 + tile_w]
                if crop.size == 0:
                    continue
                windows.append((crop, int(x0), int(y0)))
    return windows


DEPTH_FULL = "full"
DEPTH_FRAME = "frame"
DEPTH_DETAIL = "detail"


def index_image_regions(
    conn,
    *,
    observation_id: str,
    run_id: str,
    img,
    depth: str = DEPTH_FULL,
    interactive: bool = False,
    cancelled=None,
) -> dict:
    """Persist region crops and one whole-frame vector. No-op when the pack is missing.

    Whole-frame uses modality ``scene``. Crops use modality ``region``.
    A region query must not scan scene rows.

    ``depth`` splits the work. ``frame`` encodes the whole picture once, which is
    enough to browse and search coarsely. ``detail`` adds the overlapping windows
    and proposed crops on top of an earlier ``frame`` pass. ``full`` does both.
    """
    from semblon.observers import persist_item

    if depth not in {DEPTH_FULL, DEPTH_FRAME, DEPTH_DETAIL}:
        raise ValueError(f"unknown depth: {depth}")
    ready, note = probe_region_pack()
    counts = {"region": 0, "scene": 0, "patch": 0, "ready": ready, "jobs": 0, "depth": depth}
    if not ready:
        return {**counts, "note": note}
    image = np.asarray(img)
    if image.ndim != 3 or image.shape[2] < 3:
        return {**counts, "note": "skipped: not a colour image"}
    try:
        digest = KNOWN_SHA256[WEIGHT_NAME]
        pack = pack_id_for(digest)
        patch_pack = pack_id_patches(digest)
        yield_budget = [0.0]
        jobs: list[tuple[str, np.ndarray, tuple]] = []
        windows = patch_windows(image)
        if depth in {DEPTH_FULL, DEPTH_FRAME}:
            jobs.append(("frame", windows[0][0], (0, 0)))
        if depth in {DEPTH_FULL, DEPTH_DETAIL}:
            for window, x_off, y_off in windows[1:]:
                jobs.append(("window", window, (int(x_off), int(y_off))))
            for box in proposal_boxes(image):
                try:
                    jobs.append(("proposal", crop_box(image, box), tuple(float(v) for v in box)))
                except RegionPackError:
                    continue
        counts["jobs"] = len(jobs)
        if not jobs:
            if depth == DEPTH_DETAIL:
                return counts
            return {**counts, "note": "region encoder needs an image"}
        try:
            hidden_rows = encode_images(
                [job[1] for job in jobs],
                interactive=interactive,
                cancelled=cancelled,
                yield_budget=yield_budget,
            )
        except RegionPackError as exc:
            return {**counts, "note": str(exc)}
        except Exception as exc:  # noqa: BLE001 — a bad encoder must not roll back colour ingest
            return {**counts, "note": f"region encoder failed: {exc.__class__.__name__}"}
        if len(hidden_rows) != len(jobs):
            return {**counts, "note": "region encoder returned the wrong batch"}
        for (kind, view, payload), hidden in zip(jobs, hidden_rows):
            if kind in {"frame", "window"}:
                x_off, y_off = payload
                try:
                    scene, patches = _split_content_patches(view, hidden)
                except RegionPackError:
                    continue
                if kind == "frame":
                    persist_item(
                        conn,
                        observation_id=observation_id,
                        run_id=run_id,
                        kind="clip",
                        provider=PROVIDER,
                        payload={
                            "role": "scene",
                            "space": MODEL_FAMILY,
                            "preprocess": "letterbox-224-imagenet-cls-l2",
                            "identity": "not facekit",
                            "display": False,
                        },
                        embedding=scene,
                        modality=MODALITY_SCENE,
                        pack_id=pack,
                        dim=int(len(scene) // 4),
                    )
                    counts["scene"] += 1
                for record in patches:
                    x1, y1, x2, y2 = record["bbox"]
                    extra = {}
                    if x_off or y_off:
                        extra["window"] = [x_off, y_off]
                    persist_item(
                        conn,
                        observation_id=observation_id,
                        run_id=run_id,
                        kind="clip",
                        provider=PROVIDER,
                        payload={
                            "role": "region_patch",
                            "space": MODEL_FAMILY,
                            "preprocess": "letterbox-224-imagenet-patch-l2",
                            "grid": record["grid"],
                            "gx": record["gx"],
                            "gy": record["gy"],
                            "identity": "not facekit",
                            "display": False,
                            **extra,
                        },
                        bbox=(
                            float(x1 + x_off),
                            float(y1 + y_off),
                            float(x2 + x_off),
                            float(y2 + y_off),
                        ),
                        embedding=record["blob"],
                        modality=MODALITY_PATCH,
                        pack_id=patch_pack,
                        dim=int(len(record["blob"]) // 4),
                    )
                    counts["patch"] += 1
                continue
            blob = _pool(hidden, pool=POOL).astype(np.float32).tobytes()
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="clip",
                provider=PROVIDER,
                payload={
                    "role": "region",
                    "space": MODEL_FAMILY,
                    "preprocess": "letterbox-224-imagenet-cls-l2",
                    "identity": "not facekit",
                    "display": False,
                },
                bbox=payload,
                embedding=blob,
                modality=MODALITY_REGION,
                pack_id=pack,
                dim=int(len(blob) // 4),
            )
            counts["region"] += 1
    except RegionPackError as exc:
        return {**counts, "note": str(exc)}
    return counts


def reset_session_for_tests() -> None:
    global _SESSION, _SESSION_KEY, _PROBE, _DEAD, _INTERACTIVE_DEPTH
    with _LOCK:
        _SESSION = None
        _SESSION_KEY = None
        _PROBE = None
        _DEAD = False
    with _LANE_META:
        _INTERACTIVE_DEPTH = 0
        _INTERACTIVE.clear()
