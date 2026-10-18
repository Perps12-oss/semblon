"""Non-identity observation providers and persistence.

Identity remains FaceKit on faces.* only. These items never vote on
compare(), DBSCAN, or identify.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from semblon.store import connect, init_db

APPEARANCE_PACK = "appearance/rgb8@1"
APPEARANCE_DIM = 24
OBJECT_PROVIDER = "opencv-contour"
NANODET_PROVIDER = "opencv-zoo-nanodet"
CLIP_PACK = "clip/openclip-vitb32@1"
CLIP_MODEL = "ViT-B-32"
CLIP_PRETRAINED = "openai"
OCR_PROVIDER = "tesseract"
POSE_PROVIDER = "mediapipe-pose"
_CLIP_CACHE = None
_POSE_CACHE = None


class ProviderUnavailable(RuntimeError):
    pass


def _clip_cache_dir() -> Path:
    override = os.environ.get("OPENCLIP_CACHE_DIR") or os.environ.get("CLIP_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "clip"


def _hf_hub_cache_dir() -> Path:
    override = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if override:
        return Path(override)
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _nonempty_file(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        if path.is_file() and path.stat().st_size > 0:
            return path
    except OSError:
        return None
    return None


def find_local_clip_weights() -> Path | None:
    """Locate ViT-B-32/openai weights on disk. Never downloads."""
    try:
        from open_clip.pretrained import get_pretrained_cfg
    except Exception:
        return None
    try:
        cfg = get_pretrained_cfg(CLIP_MODEL, CLIP_PRETRAINED) or {}
    except Exception:
        return None
    if not isinstance(cfg, dict) or not cfg:
        return None

    explicit = cfg.get("file")
    if explicit:
        found = _nonempty_file(Path(explicit))
        if found is not None:
            return found

    url = cfg.get("url") or ""
    if url:
        name = Path(urlparse(url).path).name
        if name:
            found = _nonempty_file(_clip_cache_dir() / name)
            if found is not None:
                return found

    hub = (cfg.get("hf_hub") or "").strip()
    if hub:
        if hub.endswith("/"):
            model_id = hub.rstrip("/")
            names = ["open_clip_pytorch_model.bin", "open_clip_model.safetensors", "pytorch_model.bin"]
        elif "/" in hub:
            model_id, filename = hub.rsplit("/", 1)
            names = [filename] if filename else ["open_clip_pytorch_model.bin", "open_clip_model.safetensors"]
        else:
            model_id, names = hub, ["open_clip_pytorch_model.bin", "open_clip_model.safetensors"]
        if model_id:
            root = _hf_hub_cache_dir() / f"models--{model_id.replace('/', '--')}"
            if root.is_dir():
                for name in names:
                    for hit in root.rglob(name):
                        found = _nonempty_file(hit)
                        if found is not None:
                            return found
    return None


def probe_ocr_status() -> tuple[bool, str | None]:
    """True only when pytesseract imports and tesseract is on PATH."""
    if shutil.which("tesseract") is None:
        return False, "unavailable: tesseract binary not on PATH"
    try:
        import pytesseract  # noqa: F401
    except Exception as e:
        return False, f"unavailable: {type(e).__name__}"
    return True, None


def probe_clip_status() -> tuple[bool, str | None]:
    """True only when open_clip+torch import and local ViT-B-32/openai weights exist.

    Does not call create_model_and_transforms and does not download weights.
    """
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401
    except Exception as e:
        return False, f"unavailable: {type(e).__name__}"
    weights = find_local_clip_weights()
    if weights is None:
        cache = _clip_cache_dir()
        return (
            False,
            f"unavailable: open_clip+torch present but ViT-B-32/{CLIP_PRETRAINED} weights missing "
            f"(checked {cache}; no download)",
        )
    return True, None


def probe_pose_status() -> tuple[bool, str | None]:
    """True only when mediapipe.solutions.pose exists (the API pose_landmarks uses)."""
    try:
        import mediapipe as mp
    except Exception as e:
        return False, f"unavailable: {type(e).__name__}"
    solutions = getattr(mp, "solutions", None)
    pose_api = getattr(solutions, "pose", None) if solutions is not None else None
    if pose_api is None:
        return False, "unavailable: mediapipe.solutions.pose missing"
    return True, None


def color_histogram(img) -> bytes:
    """8-bin RGB histogram, L2-normalised. Appearance space, not identity."""
    arr = np.asarray(img)
    if arr.ndim != 3 or arr.shape[2] < 3:
        vec = np.zeros(APPEARANCE_DIM, dtype=np.float32)
        return vec.tobytes()
    b, g, r = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    hist = []
    for ch in (r, g, b):
        h, _ = np.histogram(ch, bins=8, range=(0, 256), density=False)
        hist.extend(h.astype(np.float32))
    vec = np.asarray(hist, dtype=np.float32)
    n = float(np.linalg.norm(vec))
    if n > 0:
        vec = vec / n
    return vec.tobytes()


def contour_objects(img, *, min_area: int = 400, max_regions: int = 8) -> list[dict]:
    """Cheap OpenCV contours as object observations. Not a detector pack. Not identity."""
    import cv2

    arr = np.asarray(img)
    if arr.ndim != 3:
        return []
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thr = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape[:2]
    out = []
    scored = []
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < min_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if bw >= w * 0.98 and bh >= h * 0.98:
            continue
        scored.append((area, (float(x), float(y), float(x + bw), float(y + bh))))
    scored.sort(reverse=True)
    for area, bbox in scored[:max_regions]:
        out.append({"bbox": bbox, "score": min(1.0, area / float(max(w * h, 1))), "class": "region"})
    return out


def probe_nanodet_status() -> tuple[bool, str | None]:
    """True when BYO NanoDet pack is ready. Contours alone are not detector search."""
    from semblon.object_pack import probe_nanodet_status as _probe

    return _probe()


def optional_status() -> dict:
    """Honest availability of extra providers. Missing extras are not a crash.

    Status matches what the call path needs, not a bare import:
    OCR needs the tesseract binary; CLIP needs open_clip+torch+local weights;
    pose needs mediapipe.solutions.pose; NanoDet needs a BYO ONNX pack.
    Never downloads CLIP or NanoDet weights. Contour regions stay available
    without NanoDet but are not COCO object search.
    """
    notes: dict[str, str] = {}
    ocr, ocr_note = probe_ocr_status()
    if ocr_note:
        notes["ocr"] = ocr_note
    clip, clip_note = probe_clip_status()
    if clip_note:
        notes["clip"] = clip_note
    pose, pose_note = probe_pose_status()
    if pose_note:
        notes["pose"] = pose_note
    nanodet, nanodet_note = probe_nanodet_status()
    if nanodet_note:
        notes["nanodet"] = nanodet_note
    from semblon.region_encoder import probe_region_pack

    region_ready, region_note = probe_region_pack()
    if region_note:
        notes["region"] = region_note
    return {
        "facekit": True,
        "appearance": True,
        "object": True,  # contour region discovery (not COCO labels)
        "nanodet": nanodet,
        "region": region_ready,
        "ocr": ocr,
        "clip": clip,
        "pose": pose,
        "notes": notes,
        "identity": "facekit only",
        "note": "optional extras never write faces.person_id or embeddings.modality=face",
    }


# Always-on Home observers (non-identity extras that need no optional binaries).
BASE_HOME_OBSERVERS: tuple[str, ...] = ("face", "color", "object")
# Probe key → --observers token (observe_bgr accepts "ocr" or "text" for OCR).
OPTIONAL_PROBE_TO_OBSERVER: tuple[tuple[str, str], ...] = (
    ("region", "region"),
    ("ocr", "text"),
    ("clip", "clip"),
    ("pose", "pose"),
)


def resolve_product_observers(*, base: tuple[str, ...] | str | None = None) -> str:
    """Observer CSV for product ingest when MODALITY_PRODUCT is on.

    Appends text/clip/pose only when honesty probes say ready. Never votes identity.
    When the gate is off, returns the base list only. Clean installs without
    binaries/weights stay on base (no silent True).
    """
    from semblon.gates import MODALITY_PRODUCT, enabled

    if base is None:
        parts = list(BASE_HOME_OBSERVERS)
    elif isinstance(base, str):
        parts = [x.strip() for x in base.split(",") if x.strip()]
    else:
        parts = list(base)
    if not enabled(MODALITY_PRODUCT):
        return ",".join(parts)
    st = optional_status()
    seen = set(parts)
    for probe_key, obs_name in OPTIONAL_PROBE_TO_OBSERVER:
        if st.get(probe_key) and obs_name not in seen and probe_key not in seen:
            parts.append(obs_name)
            seen.add(obs_name)
    return ",".join(parts)


def modality_product_settings_lines() -> list[str]:
    """Rich Settings copy for optional modalities. Honest probes + product path."""
    from semblon.gates import MODALITY_PRODUCT, enabled, require_human_note

    st = optional_status()
    lines = [
        "Optional modalities: PRODUCTIZED (optional) — observation/retrieval only",
        f"optional ocr={st['ocr']} clip={st['clip']} pose={st['pose']}",
        st["identity"],
        st["note"],
    ]
    if not enabled(MODALITY_PRODUCT):
        lines.append(f"Modality product surfaces OFF. {require_human_note(MODALITY_PRODUCT)}")
        return lines
    lines.append(f"Product observers (this machine): {resolve_product_observers()}")
    notes = st.get("notes") or {}
    lines.append("Modality status:")
    for probe_key, obs_name in OPTIONAL_PROBE_TO_OBSERVER:
        if st.get(probe_key):
            lines.append(f"  {probe_key}: ready → observer '{obs_name}' in product defaults")
        else:
            note = notes.get(probe_key) or "unavailable"
            lines.append(f"  {probe_key}: {note}")
    lines.append(
        "Read paths: search --text (OCR); search --similar ITEM (CLIP/appearance). "
        "Pose is observation-only (no identity compare)."
    )
    lines.append(
        "OCR/CLIP/pose/region never write faces.person_id or embeddings.modality=face."
    )
    lines.append(
        "Stills opened here: jpg, jpeg, png, bmp, webp. "
        "Video opens as a sampled frame, not a player. "
        "PDF, HEIC, and TIFF are not opened in this install."
    )
    return lines


def ocr_image(img) -> dict | None:
    """OCR text. None = library missing. Never identity."""
    try:
        import cv2
        import pytesseract
    except Exception:
        return None
    try:
        arr = np.asarray(img)
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY) if arr.ndim == 3 else arr
        text = (pytesseract.image_to_string(gray) or "").strip()
        words: list[dict] = []
        try:
            from pytesseract import Output

            data = pytesseract.image_to_data(gray, output_type=Output.DICT)
            texts = data.get("text") or []
            confs = data.get("conf") or []
            lefts = data.get("left") or []
            tops = data.get("top") or []
            widths = data.get("width") or []
            heights = data.get("height") or []
            for raw, conf, left, top, width, height in zip(texts, confs, lefts, tops, widths, heights):
                token = str(raw or "").strip()
                try:
                    score = float(conf)
                except (TypeError, ValueError):
                    continue
                if score < 60 or len(token) < 2:
                    continue
                if width <= 0 or height <= 0:
                    continue
                words.append(
                    {
                        "text": token[:200],
                        "score": score / 100.0,
                        "bbox": (
                            float(left),
                            float(top),
                            float(left + width),
                            float(top + height),
                        ),
                    }
                )
        except Exception:
            words = []
        return {"text": text[:4000], "score": 1.0 if text else 0.0, "words": words[:40]}
    except Exception as e:  # noqa: BLE001 — optional extra must not crash ingest
        return {"error": type(e).__name__, "note": str(e)[:240]}


def clip_embed(img) -> dict | None:
    """Optional CLIP visual embedding. None = unavailable. Never modality=face."""
    global _CLIP_CACHE
    try:
        import open_clip
        import torch
        from PIL import Image
    except Exception:
        return None
    try:
        if _CLIP_CACHE is None:
            model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
            model.eval()
            _CLIP_CACHE = (model, preprocess)
        model, preprocess = _CLIP_CACHE
        arr = np.asarray(img)
        if arr.ndim != 3:
            return {"error": "bad-image", "note": "need BGR"}
        rgb = arr[:, :, ::-1].copy()
        with torch.no_grad():
            feat = model.encode_image(preprocess(Image.fromarray(rgb)).unsqueeze(0))
            feat = feat / feat.norm(dim=-1, keepdim=True)
        vec = feat.squeeze(0).detach().cpu().numpy().astype(np.float32)
        return {"embedding": vec.tobytes(), "pack_id": CLIP_PACK, "dim": int(vec.size)}
    except Exception as e:  # noqa: BLE001 — optional extra must not crash ingest
        return {"error": type(e).__name__, "note": str(e)[:240]}


def pose_landmarks(img) -> dict | None:
    """Optional pose landmarks. None = unavailable. Not a person."""
    global _POSE_CACHE
    try:
        import mediapipe as mp
    except Exception:
        return None
    try:
        arr = np.asarray(img)
        if arr.ndim != 3:
            return {"error": "bad-image", "note": "need BGR"}
        h, w = arr.shape[:2]
        rgb = arr[:, :, ::-1]
        if _POSE_CACHE is None:
            _POSE_CACHE = mp.solutions.pose.Pose(static_image_mode=True)
        res = _POSE_CACHE.process(rgb)
        if not res.pose_landmarks:
            return {"landmarks": [], "score": 0.0}
        lms = [
            {"i": i, "x": float(p.x), "y": float(p.y), "z": float(p.z), "v": float(p.visibility)}
            for i, p in enumerate(res.pose_landmarks.landmark)
        ]
        xs = [p["x"] for p in lms]
        ys = [p["y"] for p in lms]
        bbox = (min(xs) * w, min(ys) * h, max(xs) * w, max(ys) * h)
        return {"landmarks": lms[:33], "score": 1.0, "bbox": bbox}
    except Exception as e:  # noqa: BLE001 — optional extra must not crash ingest
        return {"error": type(e).__name__, "note": str(e)[:240]}


def _ocr_failure_payload(note: str, *, crash: str | None = None) -> dict:
    """OCR that did not produce text. Not an empty match."""
    from semblon.runtime_contract import invoke

    if crash:
        result, _ = invoke("ocr", model_state="AVAILABLE", run=lambda: {"crash": crash})
        legacy = "error"
    else:
        result, _ = invoke("ocr")
        legacy = "unavailable"
    return {
        "status": legacy,
        "note": note or result.reason,
        "contract_status": result.status,
        "reason": result.reason,
        "error_id": result.error_id,
    }


def _extra_failure_payload(capability: str, note: str, *, crash: str | None = None) -> dict:
    """CLIP/pose failure stamp. These are not the SigLIP capability."""
    status = "ERROR" if crash else "UNAVAILABLE"
    return {
        "status": "error" if crash else "unavailable",
        "note": note,
        "contract_status": status,
        "reason": note or f"{capability} did not run.",
        "error_id": f"{capability}.{status}",
    }


def persist_item(
    conn,
    *,
    observation_id: str,
    run_id: str,
    kind: str,
    provider: str,
    payload: dict,
    bbox=None,
    score=None,
    face_id=None,
    embedding: bytes | None = None,
    modality: str | None = None,
    pack_id: str | None = None,
    dim: int | None = None,
) -> str:
    item_id = uuid.uuid4().hex
    x1 = y1 = x2 = y2 = None
    if bbox is not None:
        x1, y1, x2, y2 = bbox
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json, face_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            item_id,
            observation_id,
            run_id,
            kind,
            provider,
            x1,
            y1,
            x2,
            y2,
            score,
            json.dumps(payload),
            face_id,
        ),
    )
    if embedding is not None:
        if not modality or not pack_id or not dim:
            raise ValueError("embedding requires modality, pack_id, dim")
        if modality == "face":
            raise ValueError("face identity embeddings stay on faces; not embeddings table")
        conn.execute(
            """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
               VALUES (?,?,?,?,?,?)""",
            (uuid.uuid4().hex, item_id, modality, pack_id, int(dim), embedding),
        )
    return item_id



def _circuit_paused(capability: str):
    """OPEN circuit. The provider is not called. Not an empty match."""
    from semblon.circuits import before_call

    return before_call(capability)


def _paused_payload(paused) -> dict:
    return {
        "status": "unavailable",
        "note": paused.reason,
        "contract_status": paused.status,
        "reason": paused.reason,
        "error_id": paused.error_id,
    }


def _circuit_note(capability: str, rec, *, matched: bool) -> None:
    """Record a live observer call. Missing models do not open the circuit. Crashes do."""
    from semblon.circuits import after_call
    from semblon.runtime_contract import ResultItem, StructuredResult

    if rec is None:
        result = StructuredResult(
            status="UNAVAILABLE",
            capability_id=capability,
            provider_id=capability,
            model_state="MISSING",
            provider_state="FAILED",
            reason=f"{capability} is not installed.",
            error_id=f"{capability}.MISSING",
        )
    elif isinstance(rec, dict) and rec.get("error"):
        result = StructuredResult(
            status="ERROR",
            capability_id=capability,
            provider_id=capability,
            model_state="AVAILABLE",
            provider_state="FAILED",
            reason=str(rec.get("note") or rec.get("error"))[:240],
            error_id=f"{capability}.ERROR",
        )
    elif matched:
        result = StructuredResult(
            status="SUCCESS",
            capability_id=capability,
            provider_id=capability,
            model_state="AVAILABLE",
            provider_state="READY",
            reason="ran",
            items=(ResultItem(id=f"{capability}-0", kind=capability, label=capability),),
        )
    else:
        result = StructuredResult(
            status="NO_RESULT",
            capability_id=capability,
            provider_id=capability,
            model_state="AVAILABLE",
            provider_state="READY",
            reason="ran, nothing matched",
        )
    after_call(result)


def observe_bgr(conn, *, observation_id: str, run_id: str, img, observers: tuple[str, ...]) -> dict:
    """Run non-identity observers. 'face' is ignored here (FaceKit owns faces)."""
    counts = {"appearance": 0, "object": 0, "text": 0, "pose": 0, "clip": 0}
    wanted = {o.strip() for o in observers if o.strip() and o.strip() != "face"}
    if "color" in wanted or "appearance" in wanted:
        blob = color_histogram(img)
        persist_item(
            conn,
            observation_id=observation_id,
            run_id=run_id,
            kind="appearance",
            provider="color-hist",
            payload={"space": "rgb8"},
            embedding=blob,
            modality="appearance",
            pack_id=APPEARANCE_PACK,
            dim=APPEARANCE_DIM,
        )
        counts["appearance"] += 1
    if "object" in wanted:
        # Contour regions — geometry only; never claim COCO labels.
        for obj in contour_objects(img):
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="object",
                provider=OBJECT_PROVIDER,
                payload={"class": obj["class"], "label": "region", "source": "contour"},
                bbox=obj["bbox"],
                score=obj["score"],
            )
            counts["object"] += 1
        # NanoDet COCO labels when BYO pack is ready; fail closed otherwise.
        nanodet_ready, _nanodet_note = probe_nanodet_status()
        if nanodet_ready:
            try:
                from semblon.object_nanodet import detect_objects

                for obj in detect_objects(img):
                    persist_item(
                        conn,
                        observation_id=observation_id,
                        run_id=run_id,
                        kind="object",
                        provider=NANODET_PROVIDER,
                        payload={
                            "class": obj["class"],
                            "label": obj["label"],
                            "class_id": obj["class_id"],
                            "source": "nanodet",
                            "identity": "not facekit",
                        },
                        bbox=obj["bbox"],
                        score=obj["score"],
                    )
                    counts["object"] += 1
            except Exception as exc:  # noqa: BLE001 — observation must not crash ingest
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="object",
                    provider=NANODET_PROVIDER,
                    payload={
                        "error": str(exc)[:500],
                        "contract_status": "UNAVAILABLE",
                        "identity": "not facekit",
                    },
                    score=0.0,
                )
        # Missing pack: no NanoDet rows. search_object probes the pack and reports UNAVAILABLE.
        # Contour regions above remain honest geometry, not detector labels.
    if "region" in wanted:
        from semblon.region_encoder import index_image_regions

        try:
            indexed = index_image_regions(
                conn, observation_id=observation_id, run_id=run_id, img=img
            )
        except Exception:  # noqa: BLE001 — colour and objects must still commit
            indexed = {"region": 0, "scene": 0}
        counts["clip"] += (
            int(indexed.get("region") or 0)
            + int(indexed.get("scene") or 0)
            + int(indexed.get("patch") or 0)
        )
    if "text" in wanted or "ocr" in wanted:
        paused = _circuit_paused("ocr")
        if paused is not None:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="text",
                provider=OCR_PROVIDER,
                payload=_paused_payload(paused),
                score=0.0,
            )
        else:
            rec = ocr_image(img)
            if rec is None:
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="text",
                    provider=OCR_PROVIDER,
                    payload=_ocr_failure_payload(
                        optional_status()["notes"].get("ocr", "unavailable")
                    ),
                    score=0.0,
                )
                _circuit_note("ocr", None, matched=False)
            elif rec.get("error"):
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="text",
                    provider=OCR_PROVIDER,
                    payload=_ocr_failure_payload(rec.get("note") or rec["error"], crash=rec["error"]),
                    score=0.0,
                )
                _circuit_note("ocr", rec, matched=False)
            else:
                text_read = rec.get("text") or ""
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="text",
                    provider=OCR_PROVIDER,
                    payload={
                        "text": text_read,
                        "identity": "not facekit",
                        "contract_status": "SUCCESS" if text_read.strip() else "NO_RESULT",
                    },
                    score=rec.get("score"),
                )
                counts["text"] += 1
                for word in rec.get("words") or []:
                    box = word.get("bbox")
                    token = str(word.get("text") or "").strip()
                    if not token or not box:
                        continue
                    persist_item(
                        conn,
                        observation_id=observation_id,
                        run_id=run_id,
                        kind="text",
                        provider=OCR_PROVIDER,
                        payload={
                            "text": token,
                            "identity": "not facekit",
                            "contract_status": "SUCCESS",
                            "role": "word",
                        },
                        bbox=tuple(box),
                        score=word.get("score"),
                    )
                    counts["text"] += 1
                _circuit_note("ocr", rec, matched=bool(text_read.strip()))
    if "clip" in wanted:
        paused = _circuit_paused("clip")
        if paused is not None:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="clip",
                provider="open-clip",
                payload=_paused_payload(paused),
                score=0.0,
            )
        else:
            rec = clip_embed(img)
            if rec is None:
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="clip",
                    provider="open-clip",
                    payload=_extra_failure_payload(
                        "clip", optional_status()["notes"].get("clip", "unavailable")
                    ),
                    score=0.0,
                )
                _circuit_note("clip", None, matched=False)
            elif rec.get("error"):
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="clip",
                    provider="open-clip",
                    payload=_extra_failure_payload(
                        "clip", rec.get("note") or rec["error"], crash=rec["error"]
                    ),
                    score=0.0,
                )
                _circuit_note("clip", rec, matched=False)
            else:
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="clip",
                    provider="open-clip",
                    payload={"space": "clip", "identity": "not facekit"},
                    embedding=rec["embedding"],
                    modality="clip",
                    pack_id=rec["pack_id"],
                    dim=rec["dim"],
                )
                counts["clip"] += 1
                _circuit_note("clip", rec, matched=True)
    if "pose" in wanted:
        paused = _circuit_paused("pose")
        if paused is not None:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="pose",
                provider=POSE_PROVIDER,
                payload=_paused_payload(paused),
                score=0.0,
            )
        else:
            rec = pose_landmarks(img)
            if rec is None:
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="pose",
                    provider=POSE_PROVIDER,
                    payload=_extra_failure_payload(
                        "pose", optional_status()["notes"].get("pose", "unavailable")
                    ),
                    score=0.0,
                )
                _circuit_note("pose", None, matched=False)
            elif rec.get("error"):
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="pose",
                    provider=POSE_PROVIDER,
                    payload=_extra_failure_payload(
                        "pose", rec.get("note") or rec["error"], crash=rec["error"]
                    ),
                    score=0.0,
                )
                _circuit_note("pose", rec, matched=False)
            else:
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="pose",
                    provider=POSE_PROVIDER,
                    payload={"landmarks": rec.get("landmarks") or [], "identity": "not facekit"},
                    bbox=rec.get("bbox"),
                    score=rec.get("score"),
                )
                counts["pose"] += 1
                _circuit_note("pose", rec, matched=True)
    return counts


def ensure_face_item(conn, *, face_id: str, observation_id: str, run_id: str, bbox=None, score=None, status: str = "ok") -> str:
    """Dual-write a FaceKit face as an observation_item. No identity embedding here."""
    row = conn.execute(
        "SELECT item_id FROM observation_items WHERE face_id=? AND kind='face'",
        (face_id,),
    ).fetchone()
    if row:
        return row["item_id"] if not isinstance(row, tuple) else row[0]
    return persist_item(
        conn,
        observation_id=observation_id,
        run_id=run_id,
        kind="face",
        provider="facekit",
        payload={"status": status, "identity": "faces table only"},
        bbox=bbox,
        score=score,
        face_id=face_id,
    )


def snapshot_groups_from_clusters(conn, run_id: str) -> dict:
    """observation_groups from DBSCAN clusters. Group ≠ person."""
    conn.execute(
        """DELETE FROM group_members WHERE group_id IN
           (SELECT group_id FROM observation_groups WHERE run_id=? AND kind='face')""",
        (run_id,),
    )
    conn.execute(
        "DELETE FROM observation_groups WHERE run_id=? AND kind='face'",
        (run_id,),
    )
    clusters = conn.execute(
        """SELECT cluster_id, strategy, face_count FROM clusters
           WHERE run_id=? AND status != 'merged'""",
        (run_id,),
    ).fetchall()
    n_groups = 0
    n_members = 0
    for c in clusters:
        faces = conn.execute(
            "SELECT face_id, observation_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2, det_score, status FROM faces WHERE cluster_id=?",
            (c["cluster_id"],),
        ).fetchall()
        item_ids = []
        for f in faces:
            bbox = (f["bbox_x1"], f["bbox_y1"], f["bbox_x2"], f["bbox_y2"])
            iid = ensure_face_item(
                conn,
                face_id=f["face_id"],
                observation_id=f["observation_id"],
                run_id=run_id,
                bbox=bbox,
                score=f["det_score"],
                status=f["status"],
            )
            item_ids.append(iid)
        gid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO observation_groups(group_id, run_id, kind, strategy, member_count, status)
               VALUES (?,?,?,?,?,?)""",
            (gid, run_id, "face", c["strategy"], len(item_ids), "auto"),
        )
        for iid in item_ids:
            conn.execute(
                "INSERT OR IGNORE INTO group_members(group_id, item_id) VALUES (?,?)",
                (gid, iid),
            )
        n_groups += 1
        n_members += len(item_ids)
    conn.commit()
    return {"groups": n_groups, "members": n_members, "note": "cluster group is not a person"}


def snapshot_memory_graph(store: Path, run_id: str | None = None) -> dict:
    """Copy S6 together/events into relationship/event rows. confirmed=0. Not identity."""
    from semblon.memory import MemoryError, events, together

    p = Path(store)
    conn = connect(p)
    init_db(conn)
    try:
        tog = together(p, run_id=run_id)
        ev = events(p, run_id=run_id)
    except MemoryError:
        tog = {"items": []}
        ev = {"bursts": [], "days": [], "folders": []}
    rid = run_id or ""
    if not rid:
        row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        rid = row["run_id"] if row else "unknown"
    conn.execute("DELETE FROM relationships WHERE confirmed=0 AND run_id=?", (rid,))
    conn.execute("DELETE FROM events WHERE confirmed=0 AND run_id=?", (rid,))
    n_rel = 0
    for item in tog.get("items") or []:
        ids = item.get("person_ids") or []
        if len(ids) < 2:
            continue
        conn.execute(
            """INSERT INTO relationships(relationship_id, run_id, kind, src_person_id, evidence_json, confirmed)
               VALUES (?,?,?,?,?,0)""",
            (
                uuid.uuid4().hex,
                rid,
                "together",
                ids[0],
                json.dumps(
                    {
                        "person_ids": ids,
                        "names": item.get("names"),
                        "media_id": item.get("media_id"),
                        "source_type": item.get("source_type"),
                    }
                ),
            ),
        )
        n_rel += 1
    n_ev = 0
    for burst in ev.get("bursts") or []:
        conn.execute(
            """INSERT INTO events(event_id, run_id, label, t_start, t_end, folder, evidence_json, confirmed)
               VALUES (?,?,?,?,?,?,?,0)""",
            (
                uuid.uuid4().hex,
                rid,
                "burst",
                burst.get("when"),
                burst.get("until"),
                burst.get("folder"),
                json.dumps(burst),
            ),
        )
        n_ev += 1
    conn.commit()
    conn.close()
    return {"relationships": n_rel, "events": n_ev, "confirmed": 0, "note": "S6 snapshot; not identity"}


def persist_derived_tracks(store: Path, run_id: str, conn=None) -> dict:
    """Write derived S7 tracks into the tracks table. Not identity. Re-runnable."""
    from semblon.tracks import TracksError, derive_tracks

    p = Path(store)
    own = conn is None
    if own:
        conn = connect(p)
        init_db(conn)
    try:
        rec = derive_tracks(p, run_id, prefer_persisted=False)
    except TracksError:
        if own:
            conn.close()
        return {"tracks": 0, "note": "no derived tracks"}
    conn.execute(
        "DELETE FROM track_members WHERE track_id IN (SELECT track_id FROM tracks WHERE run_id=?)",
        (run_id,),
    )
    conn.execute("DELETE FROM tracks WHERE run_id=?", (run_id,))
    n = 0
    for t in rec.get("tracks") or []:
        tid = t.get("track_id") or uuid.uuid4().hex
        conn.execute(
            """INSERT INTO tracks(track_id, media_id, run_id, kind, t_ms_start, t_ms_end, item_count, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                tid,
                t["media_id"],
                run_id,
                "face",
                t.get("t_ms_start"),
                t.get("t_ms_end"),
                int(t.get("face_count") or len(t.get("face_ids") or [])),
                "derived",
            ),
        )
        members = list(t.get("members") or [])
        if not members:
            # Fallback for payloads without member objects.
            for fid in t.get("face_ids") or []:
                row = conn.execute(
                    """
                    SELECT f.face_id, f.observation_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
                           f.det_score, o.t_ms
                    FROM faces f
                    JOIN observations o ON o.observation_id = f.observation_id
                    WHERE f.face_id=? AND f.run_id=?
                    """,
                    (fid, run_id),
                ).fetchone()
                if row is None:
                    continue
                members.append(
                    {
                        "face_id": row["face_id"],
                        "observation_id": row["observation_id"],
                        "bbox": (row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]),
                        "score": row["det_score"],
                        "t_ms": row["t_ms"],
                    }
                )
        for m in members:
            fid = m.get("face_id")
            oid = m.get("observation_id")
            if not fid or not oid:
                continue
            iid = ensure_face_item(
                conn,
                face_id=fid,
                observation_id=oid,
                run_id=run_id,
                bbox=m.get("bbox"),
                score=m.get("score"),
                status="ok",
            )
            conn.execute(
                "INSERT OR IGNORE INTO track_members(track_id, item_id, t_ms) VALUES (?,?,?)",
                (tid, iid, m.get("t_ms")),
            )
        n += 1
    conn.commit()
    if own:
        conn.close()
    return {"tracks": n, "note": "derived snapshot; track id is not person id"}
