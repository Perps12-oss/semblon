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
import os
import threading
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
PROVIDER = "dinov2-vits14"
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
    if not onnx.is_file():
        return False, (
            f"unavailable: region encoder missing ({WEIGHT_NAME}). "
            "Run tools/fetch_region_pack.py or place the pinned ONNX under "
            "~/.semblon/models/region/. Colour fallback stays labelled colour."
        )
    if onnx.stat().st_size < 1024:
        return False, "unavailable: region ONNX looks truncated"
    try:
        digest = _sha256_file(onnx).lower()
    except OSError as exc:
        return False, f"unavailable: region ONNX unreadable ({exc.__class__.__name__})"
    expected = KNOWN_SHA256.get(WEIGHT_NAME, "").lower()
    if not expected or digest != expected:
        return False, "unavailable: region ONNX hash does not match the pinned pack"
    pin = home / PIN_NAME
    if not pin.is_file():
        return False, f"unavailable: region pack pin missing ({PIN_NAME})"
    try:
        pin_data = json.loads(pin.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False, "unavailable: region pack pin is unreadable"
    if not isinstance(pin_data, dict):
        return False, "unavailable: region pack pin is invalid"
    pin_sha = str(pin_data.get("sha256") or "").strip().lower()
    if pin_sha != digest:
        return False, "unavailable: region pack pin does not match the ONNX"
    with _LOCK:
        _PROBE = (*stamp, True, None)
    return True, None


def active_pack(root: Path | None = None) -> tuple[str, int] | None:
    """(pack_id, dim) when the pinned pack is present and has not timed out."""
    if _DEAD:
        return None
    ready, _note = probe_region_pack(root)
    if not ready:
        return None
    return pack_id_for(KNOWN_SHA256[WEIGHT_NAME]), OUTPUT_DIM


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
        raise box["error"]
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


def letterbox_bgr(image: np.ndarray, size: int = INPUT_SIZE) -> np.ndarray:
    """Fit the whole crop inside a square. Same pixels in, same canvas out."""
    import cv2

    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise RegionPackError("region encoder needs a BGR image")
    arr = arr[:, :, :3]
    height, width = arr.shape[:2]
    if height < 1 or width < 1:
        raise RegionPackError("region has no pixels")
    scale = float(size) / float(max(height, width))
    resized_w = max(1, int(round(width * scale)))
    resized_h = max(1, int(round(height * scale)))
    resized_w = min(size, resized_w)
    resized_h = min(size, resized_h)
    resized = cv2.resize(arr, (resized_w, resized_h), interpolation=cv2.INTER_CUBIC)
    canvas = np.full((size, size, 3), _PAD_BGR, dtype=np.uint8)
    x0 = (size - resized_w) // 2
    y0 = (size - resized_h) // 2
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


def _embed_now(image_bgr: np.ndarray, root: Path | None, *, pool: str) -> bytes:
    session = _session(root)
    tensor = _tensor(image_bgr)
    input_name = session.get_inputs()[0].name
    try:
        outputs = session.run(None, {input_name: tensor})
    except Exception as exc:  # noqa: BLE001 — surface a pack failure, do not invent a vector
        raise RegionPackError(f"region encoder failed: {exc.__class__.__name__}") from exc
    hidden = None
    for value in outputs:
        arr = np.asarray(value)
        if arr.ndim >= 2 and arr.shape[-1] == OUTPUT_DIM:
            hidden = arr
            break
    if hidden is None:
        raise RegionPackError("region encoder returned no 384-d hidden state")
    vec = _pool(hidden, pool=pool)
    if vec.size != OUTPUT_DIM:
        raise RegionPackError(f"region encoder dim {vec.size} != {OUTPUT_DIM}")
    return vec.tobytes()


def embed_bgr(image_bgr: np.ndarray, root: Path | None = None, *, pool: str | None = None) -> bytes:
    """L2-normalised float32 bytes. Raises RegionPackError when the pack cannot run."""
    chosen = pool or POOL
    if chosen not in {"cls", "mean"}:
        raise RegionPackError(f"unknown region pool {chosen}")
    return _bounded(lambda: _embed_now(image_bgr, root, pool=chosen))


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


def index_image_regions(conn, *, observation_id: str, run_id: str, img) -> dict:
    """Persist region crops and one whole-frame vector. No-op when the pack is missing.

    Whole-frame uses modality ``scene``. Crops use modality ``region``.
    A region query must not scan scene rows.
    """
    from semblon.observers import persist_item

    ready, note = probe_region_pack()
    counts = {"region": 0, "scene": 0, "ready": ready}
    if not ready:
        return {**counts, "note": note}
    image = np.asarray(img)
    if image.ndim != 3 or image.shape[2] < 3:
        return {**counts, "note": "skipped: not a colour image"}
    try:
        digest = KNOWN_SHA256[WEIGHT_NAME]
        pack = pack_id_for(digest)
        try:
            scene = embed_bgr(image)
        except RegionPackError as exc:
            return {**counts, "note": str(exc)}
        except Exception as exc:  # noqa: BLE001 — a bad encoder must not roll back colour ingest
            return {**counts, "note": f"region encoder failed: {exc.__class__.__name__}"}
        dim = int(len(scene) // 4)
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
            dim=dim,
        )
        counts["scene"] += 1
        for box in proposal_boxes(image):
            try:
                crop = crop_box(image, box)
                blob = embed_bgr(crop)
            except RegionPackError:
                continue
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
                bbox=box,
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
    global _SESSION, _SESSION_KEY, _PROBE, _DEAD
    with _LOCK:
        _SESSION = None
        _SESSION_KEY = None
        _PROBE = None
        _DEAD = False
