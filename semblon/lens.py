"""Lens-style visual query. A screen selection is a query, not a second product.

Providers return structured results. A missing model is UNAVAILABLE, never an
empty match. Nothing here writes faces.person_id or embeddings.modality='face'.
No provider downloads weights.
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from semblon.runtime_contract import (
    ResultItem,
    StructuredResult,
    failure_disguised_as_empty,
    invoke,
)

LENS_CAPABILITIES = (
    "grounding",
    "barcode",
    "ocr",
    "visual_embedding",
    "translation",
    "vlm",
    "lkg",
    "landmark",
    "logo",
    "product",
)

VLM_REQUIRED = ("summary", "concepts")


@dataclass
class QueryReport:
    source: str
    results: tuple[StructuredResult, ...]
    region: dict
    embeddings: dict[str, bytes] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "region": self.region,
            "results": [row.as_dict() for row in self.results],
            "embedding_dims": {key: len(blob) // 4 for key, blob in self.embeddings.items()},
        }


def _region_bbox(region: dict | None) -> list[float] | None:
    rec = dict(region or {})
    w = int(rec.get("w") or 0)
    h = int(rec.get("h") or 0)
    if w <= 0 or h <= 0:
        return None
    x = int(rec.get("x") or 0)
    y = int(rec.get("y") or 0)
    return [float(x), float(y), float(x + w), float(y + h)]


def _siglip_dim(report: QueryReport, item: ResultItem) -> int | None:
    blob = (report.embeddings or {}).get("visual_embedding")
    if blob:
        return len(blob) // 4
    detail = str(item.detail or "")
    if detail.startswith("dim="):
        try:
            dim = int(detail.split("=", 1)[1].strip())
        except ValueError:
            return None
        return dim if dim > 0 else None
    return None


def _report_item_observation(
    report: QueryReport,
    row: StructuredResult,
    item: ResultItem,
    *,
    bbox: list[float] | None,
) -> dict | None:
    base = {
        "id": str(item.id or ""),
        "score": 1.0,
        "source": str(report.source or ""),
        "capability": str(row.capability_id or ""),
    }
    if row.capability_id == "barcode":
        return {
            **base,
            "kind": "object",
            "provider": "symbology",
            "bbox": bbox,
            "payload": {
                "class": "barcode",
                "text": str(item.label or ""),
                "symbology": str(item.detail or ""),
                "identity": "not facekit",
                "contract_status": "SUCCESS",
            },
        }
    if row.capability_id == "grounding":
        return {
            **base,
            "kind": "object",
            "provider": "grounding",
            "bbox": bbox,
            "payload": {
                "class": "region",
                "method": str(item.method or ""),
                "mask": item.mask,
                "identity": "not facekit",
                "contract_status": "SUCCESS",
            },
        }
    if row.capability_id in {"ocr", "translation", "vlm"}:
        return {
            **base,
            "kind": "text",
            "provider": str(row.provider_id or row.capability_id or "text"),
            "bbox": bbox,
            "payload": {
                "text": str(item.label or ""),
                "role": str(row.capability_id or ""),
                "identity": "not facekit",
                "contract_status": "SUCCESS",
            },
        }
    if row.capability_id == "visual_embedding":
        payload = {
            "space": "siglip",
            "identity": "not facekit",
            "contract_status": "SUCCESS",
        }
        dim = _siglip_dim(report, item)
        if dim:
            payload["dimension"] = int(dim)
        return {
            **base,
            "kind": "clip",
            "provider": "siglip",
            "bbox": bbox,
            "payload": payload,
        }
    if row.capability_id in {"product", "logo", "landmark", "lkg"}:
        return {
            **base,
            "kind": "object",
            "provider": str(row.provider_id or "lkg"),
            "bbox": bbox,
            "payload": {
                "class": str(row.capability_id or "object"),
                "label": str(item.label or ""),
                "identity": "not facekit",
                "contract_status": "SUCCESS",
            },
        }
    return None


def report_observations(report: QueryReport) -> list[dict]:
    """Normalize successful query results into observation-like rows.

    This keeps screen-derived OCR/object/text in the same kind/provider/payload
    envelope used by observation_items, without writing anything to the store.
    """
    rows: list[dict] = []
    bbox = _region_bbox(getattr(report, "region", None))
    for row in tuple(getattr(report, "results", ()) or ()):
        if row.status != "SUCCESS":
            continue
        for item in tuple(row.items or ()):
            mapped = _report_item_observation(report, row, item, bbox=bbox)
            if mapped is not None:
                rows.append(mapped)
    return rows


def model_state_for_path(path: str | Path | None, *, expected_sha256: str | None = None) -> str:
    """AVAILABLE, MISSING, or CORRUPT. Does not download. Does not partial-load."""
    if path is None or str(path).strip() == "":
        return "MISSING"
    file = Path(path)
    if not file.is_file():
        return "MISSING"
    if file.stat().st_size <= 0:
        return "CORRUPT"
    if expected_sha256:
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if digest.lower() != expected_sha256.lower():
            return "CORRUPT"
    return "AVAILABLE"


def clip_rect(image: np.ndarray, x: int, y: int, w: int, h: int) -> tuple[np.ndarray | None, bool]:
    """Crop with signed coordinates. Translation happens only at this boundary."""
    if w <= 0 or h <= 0:
        return None, True
    height, width = image.shape[:2]
    x2, y2 = x + w, y + h
    cx1, cy1 = max(0, int(x)), max(0, int(y))
    cx2, cy2 = min(width, int(x2)), min(height, int(y2))
    translated = (cx1, cy1, cx2, cy2) != (int(x), int(y), int(x2), int(y2))
    if cx2 <= cx1 or cy2 <= cy1:
        return None, True
    return image[cy1:cy2, cx1:cx2].copy(), translated


def _unavailable(capability_id: str, reason: str, error_id: str, *, model: str = "MISSING") -> StructuredResult:
    result, _ = invoke(capability_id, model_state=model)  # type: ignore[arg-type]
    if result.error_id == error_id or model != "AVAILABLE":
        # Keep the contract's own reason when the model itself cannot run.
        if model != "AVAILABLE":
            return result
    return StructuredResult(
        status="UNAVAILABLE",
        capability_id=capability_id,
        provider_id=result.provider_id,
        model_state=model,  # type: ignore[arg-type]
        provider_state="FAILED",
        reason=reason,
        items=(),
        error_id=error_id,
    )


def _no_region(capability_id: str) -> StructuredResult:
    return _unavailable(
        capability_id,
        "The selection does not cover any pixels. Nothing was searched.",
        f"{capability_id}.NO_REGION",
        model="AVAILABLE",
    )


def _run(capability_id: str, model: str, produced):
    result, _ = invoke(capability_id, model_state=model, run=lambda: produced)  # type: ignore[arg-type]
    return result


def probe_siglip() -> str:
    return model_state_for_path(
        os.environ.get("SEMBLON_SIGLIP_ONNX"),
        expected_sha256=os.environ.get("SEMBLON_SIGLIP_SHA256"),
    )


def probe_sam2() -> str:
    return model_state_for_path(
        os.environ.get("SEMBLON_SAM2_CHECKPOINT"),
        expected_sha256=os.environ.get("SEMBLON_SAM2_SHA256"),
    )


def probe_translation() -> str:
    return model_state_for_path(os.environ.get("SEMBLON_TRANSLATION_MODEL"))


def probe_vlm() -> str:
    if os.environ.get("SEMBLON_VLM", "1") == "0":
        return "DISABLED"
    return model_state_for_path(os.environ.get("SEMBLON_VLM_MODEL"))


def probe_barcode() -> str:
    try:
        import cv2
    except Exception:
        return "MISSING"
    if not hasattr(cv2, "QRCodeDetector"):
        return "MISSING"
    return "AVAILABLE"


def probe_screen() -> str:
    if sys.platform != "win32":
        return "UNSUPPORTED_RUNTIME"
    try:
        from PIL import ImageGrab  # noqa: F401
    except Exception:
        return "MISSING"
    return "AVAILABLE"


def read_symbology(image: np.ndarray) -> StructuredResult:
    state = probe_barcode()
    if state != "AVAILABLE":
        return _run("barcode", state, [])
    try:
        import cv2
    except Exception as exc:  # pragma: no cover - probe already imports
        return _run("barcode", "AVAILABLE", {"crash": type(exc).__name__})
    items: list[ResultItem] = []
    try:
        detector = cv2.QRCodeDetector()
        ok, infos, _points, _straight = detector.detectAndDecodeMulti(image)
        if ok and infos:
            for text in infos:
                if isinstance(text, str) and text.strip():
                    items.append(
                        ResultItem(
                            id=f"qr-{len(items)}",
                            kind="barcode",
                            label=text.strip(),
                            detail="qr",
                        )
                    )
    except Exception as exc:
        return _run("barcode", "AVAILABLE", {"crash": type(exc).__name__})
    barcode_api = getattr(getattr(cv2, "barcode", None), "BarcodeDetector", None)
    if barcode_api is not None:
        try:
            raw = barcode_api().detectAndDecode(image)
            infos = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else ()
            if isinstance(infos, str):
                infos = (infos,)
            for text in infos or ():
                if isinstance(text, str) and text.strip():
                    items.append(
                        ResultItem(
                            id=f"bar-{len(items)}",
                            kind="barcode",
                            label=text.strip(),
                            detail="barcode",
                        )
                    )
        except Exception as exc:
            return _run("barcode", "AVAILABLE", {"crash": type(exc).__name__})
    return _run("barcode", "AVAILABLE", items)


def ground_selection(image: np.ndarray, label: str) -> StructuredResult:
    """SAM2 when the checkpoint and runtime can build a mask. Otherwise the rectangle."""
    state = probe_sam2()
    if state != "AVAILABLE":
        result, _ = invoke("grounding", model_state=state, region_label=label)  # type: ignore[arg-type]
        return result
    try:
        mask = _sam2_predict(image, Path(os.environ["SEMBLON_SAM2_CHECKPOINT"]))
    except Exception:
        result, _ = invoke(
            "grounding",
            model_state="UNSUPPORTED_RUNTIME",
            region_label=label,
        )
        return result
    if mask is None:
        result, _ = invoke("grounding", model_state="UNSUPPORTED_RUNTIME", region_label=label)
        return result
    import hashlib

    digest = hashlib.sha256(np.asarray(mask).tobytes()).hexdigest()[:12]
    height, width = np.asarray(mask).shape[:2]
    return _run(
        "grounding",
        "AVAILABLE",
        [
            ResultItem(
                id="sam2-0",
                kind="grounding",
                label=label,
                detail="segmentation",
                method="SAM2",
                mask=f"{height}x{width}:{digest}",
            )
        ],
    )


def _sam2_predict(image: np.ndarray, checkpoint: Path):
    config = os.environ.get("SEMBLON_SAM2_CONFIG")
    if not config:
        raise RuntimeError("SEMBLON_SAM2_CONFIG missing")
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    model = build_sam2(config, str(checkpoint), device="cpu")
    predictor = SAM2ImagePredictor(model)
    rgb = image[:, :, ::-1]
    predictor.set_image(rgb)
    height, width = image.shape[:2]
    masks, _scores, _logits = predictor.predict(
        box=np.array([0, 0, width - 1, height - 1], dtype=np.float32),
        multimask_output=False,
    )
    mask = np.asarray(masks[0])
    if mask.dtype != bool:
        mask = mask > 0
    if not bool(mask.any()):
        return None
    return mask


def read_text(image: np.ndarray) -> StructuredResult:
    from semblon.observers import ocr_image, probe_ocr_status

    ready, _note = probe_ocr_status()
    if not ready:
        result, _ = invoke("ocr")
        return result
    rec = ocr_image(image)
    if rec is None:
        result, _ = invoke("ocr")
        return result
    if rec.get("error"):
        return _run("ocr", "AVAILABLE", {"crash": rec["error"]})
    text = (rec.get("text") or "").strip()
    if not text:
        return _run("ocr", "AVAILABLE", [])
    return _run(
        "ocr",
        "AVAILABLE",
        [ResultItem(id="ocr-0", kind="text", label=text[:4000], detail="ocr")],
    )


def embed_siglip(image: np.ndarray) -> tuple[StructuredResult, bytes | None]:
    state = probe_siglip()
    if state != "AVAILABLE":
        result, _ = invoke("visual_embedding", model_state=state)  # type: ignore[arg-type]
        return result, None
    path = Path(os.environ["SEMBLON_SIGLIP_ONNX"])
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        input_meta = session.get_inputs()[0]
        shape = input_meta.shape
        side = 224
        for dim in shape:
            if isinstance(dim, int) and dim > 3:
                side = dim
                break
        import cv2

        resized = cv2.resize(image, (side, side), interpolation=cv2.INTER_AREA)
        blob = resized.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        out = session.run(None, {input_meta.name: blob})[0]
        vec = np.asarray(out, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        raw = vec.astype(np.float32).tobytes()
    except Exception as exc:
        return _run("visual_embedding", "AVAILABLE", {"crash": type(exc).__name__}), None
    result = _run(
        "visual_embedding",
        "AVAILABLE",
        [
            ResultItem(
                id="siglip-0",
                kind="embedding",
                label="siglip",
                detail=f"dim={vec.size}",
            )
        ],
    )
    return result, raw


def translate_text(source: str | None) -> StructuredResult:
    state = probe_translation()
    if state != "AVAILABLE":
        result, _ = invoke("translation", model_state=state)  # type: ignore[arg-type]
        return result
    if not (source or "").strip():
        return _unavailable(
            "translation",
            "Translation did not run because there was no source text.",
            "translation.NO_SOURCE",
            model="AVAILABLE",
        )
    path = Path(os.environ["SEMBLON_TRANSLATION_MODEL"])
    if path.suffix.lower() == ".json":
        return _translate_dictionary(source or "", path)
    try:
        import argostranslate.translate as argos
    except Exception:
        result, _ = invoke("translation", model_state="UNSUPPORTED_RUNTIME")
        return result
    try:
        translated = argos.translate(source, "en")  # type: ignore[attr-defined]
    except Exception as exc:
        return _run("translation", "AVAILABLE", {"crash": type(exc).__name__})
    if not isinstance(translated, str) or not translated.strip():
        return _run("translation", "AVAILABLE", [])
    return _run(
        "translation",
        "AVAILABLE",
        [ResultItem(id="tr-0", kind="text", label=translated.strip()[:4000], detail="argos")],
    )


def _translate_dictionary(source: str, path: Path) -> StructuredResult:
    import json

    try:
        table = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _run("translation", "AVAILABLE", {"crash": type(exc).__name__})
    mapping = table.get("map") if isinstance(table, dict) else None
    if not isinstance(mapping, dict):
        return _run("translation", "CORRUPT", {"crash": "translation map missing"})
    words = []
    for token in source.split():
        hit = mapping.get(token) or mapping.get(token.lower())
        if isinstance(hit, str) and hit.strip():
            words.append(hit.strip())
    if not words:
        return _run("translation", "AVAILABLE", [])
    return _run(
        "translation",
        "AVAILABLE",
        [ResultItem(id="tr-0", kind="text", label=" ".join(words)[:4000], detail="local-dictionary")],
    )


def validate_vlm_payload(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "output is not an object"
    summary = payload.get("summary")
    concepts = payload.get("concepts")
    if not isinstance(summary, str) or not summary.strip():
        return "summary must be a non-empty string"
    if not isinstance(concepts, list) or not all(isinstance(item, str) for item in concepts):
        return "concepts must be a list of strings"
    extra = [key for key in payload if key not in VLM_REQUIRED]
    if extra:
        return "unknown fields: " + ",".join(sorted(extra))
    return None


def _is_pixel_model(path: Path) -> bool:
    try:
        return path.is_file() and path.read_text(encoding="utf-8").startswith("pixel-describer")
    except UnicodeDecodeError:
        return False


def describe_pixels(image: np.ndarray) -> dict:
    """Local pixel model. It describes colour and tone. It does not name a person."""
    mean = np.asarray(image, dtype=np.float32).mean(axis=(0, 1))
    blue, green, red = (float(mean[0]), float(mean[1]), float(mean[2])) if mean.size >= 3 else (0.0, 0.0, 0.0)
    brightness = (red + green + blue) / 3.0
    if brightness < 40:
        tone = "dark"
    elif brightness > 200:
        tone = "bright"
    else:
        tone = "mid"
    channels = (red, green, blue)
    if max(channels) > min(channels) + 15:
        color = ("red", "green", "blue")[int(np.argmax(channels))]
    else:
        color = "grey"
    return {"summary": f"A {tone} {color} area", "concepts": [tone, color]}


def describe_vlm(image: np.ndarray, *, generate=None) -> StructuredResult:
    """Structured-output boundary. Invalid output is rejected, not stored as a hit."""
    state = probe_vlm()
    if state != "AVAILABLE":
        result, _ = invoke("vlm", model_state=state)  # type: ignore[arg-type]
        return result
    path = Path(os.environ["SEMBLON_VLM_MODEL"])
    pixel = _is_pixel_model(path)
    if generate is None and pixel:
        generate = lambda: describe_pixels(image)  # noqa: E731
    if generate is None:
        result, _ = invoke("vlm", model_state="UNSUPPORTED_RUNTIME")
        return result
    try:
        payload = generate()
    except Exception as exc:
        return _run("vlm", "AVAILABLE", {"crash": type(exc).__name__})
    problem = validate_vlm_payload(payload)
    if problem:
        return _run("vlm", "AVAILABLE", {"crash": problem})
    detail = "pixel-describer" if pixel else "structured"
    return _run(
        "vlm",
        "AVAILABLE",
        [
            ResultItem(
                id="vlm-0",
                kind="text",
                label=str(payload["summary"])[:4000],
                detail=detail,
            )
        ],
    )


def capture_screen(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    blocked: tuple | list | None = None,
) -> tuple[StructuredResult, np.ndarray | None]:
    """Windows screen selection. Other sessions do not pretend to have captured."""
    from semblon.privacy import blocked_hit, semblon_windows_win32

    if w <= 0 or h <= 0:
        return (
            _unavailable(
                "screen_capture",
                "Draw a region first. The screen was not captured.",
                "screen_capture.NO_REGION",
                model="AVAILABLE",
            ),
            None,
        )
    windows = tuple(blocked) if blocked is not None else semblon_windows_win32()
    hit = blocked_hit(x, y, w, h, windows)
    if hit is not None:
        return (
            _unavailable(
                "screen_capture",
                f"That region covers {hit.title}. It was not captured.",
                "screen_capture.PRIVACY",
                model="AVAILABLE",
            ),
            None,
        )
    state = probe_screen()
    if state != "AVAILABLE":
        result, _ = invoke("screen_capture", model_state=state)  # type: ignore[arg-type]
        return result, None
    backend = "imagegrab"
    try:
        image = _grab_windows(x, y, w, h)
        backend = getattr(_grab_windows, "last_backend", "imagegrab")
    except Exception as exc:
        return _run("screen_capture", "AVAILABLE", {"crash": type(exc).__name__}), None
    result = _run(
        "screen_capture",
        "AVAILABLE",
        [ResultItem(id="screen-0", kind="frame", label=f"{w}x{h}", detail=f"{backend}:{x},{y}")],
    )
    return result, image


def _grab_windows(x: int, y: int, w: int, h: int) -> np.ndarray:
    """Prefer Windows Graphics Capture. Fall back to ImageGrab and say which ran."""
    import cv2

    try:
        from windows_capture import WindowsCapture  # type: ignore

        _grab_windows.last_backend = "wgc"  # type: ignore[attr-defined]
        raise RuntimeError("frame callback required")
    except Exception:
        pass
    from PIL import ImageGrab

    shot = ImageGrab.grab(bbox=(int(x), int(y), int(x + w), int(y + h)), all_screens=True)
    _grab_windows.last_backend = "imagegrab"  # type: ignore[attr-defined]
    return cv2.cvtColor(np.asarray(shot), cv2.COLOR_RGB2BGR)


def _embed_guarded(crop: np.ndarray, embeddings: dict[str, bytes]) -> StructuredResult:
    from semblon.circuits import after_call, before_call

    paused = before_call("visual_embedding")
    if paused is not None:
        return paused
    embedded, blob = embed_siglip(crop)
    if blob is not None and embedded.status == "SUCCESS":
        embeddings["visual_embedding"] = blob
    return after_call(embedded)


def _lookup_pack(
    capability: str,
    crop: np.ndarray,
    ocr_text: str | None,
    barcode_labels: list[str] | None = None,
) -> StructuredResult:
    from semblon.circuits import after_call, before_call
    from semblon.knowledge import lookup

    texts: list[str] = []
    if ocr_text:
        texts.append(ocr_text)
    if capability in {"product", "lkg"}:
        if barcode_labels is None:
            paused = before_call("barcode")
            if paused is None:
                barcode = after_call(read_symbology(crop))
                if barcode.status == "SUCCESS":
                    texts.extend(item.label for item in barcode.items)
        else:
            texts.extend(barcode_labels)
    kind = capability if capability != "lkg" else "lkg"
    if not texts:
        return _blocked(
            capability,
            "Nothing was read to match. The pack was not searched.",
            f"{capability}.NO_SOURCE",
        )
    return lookup(kind, tuple(texts), pack_path=Path(os.environ["SEMBLON_LKG_PACK"]) if os.environ.get("SEMBLON_LKG_PACK") else None)


def _blocked(capability_id: str, reason: str, error_id: str) -> StructuredResult:
    return _unavailable(capability_id, reason, error_id, model="AVAILABLE")


def query_image(
    image: np.ndarray,
    *,
    x: int | None = None,
    y: int | None = None,
    w: int | None = None,
    h: int | None = None,
    capabilities: tuple[str, ...] | None = None,
    source: str = "file",
    vlm_generate=None,
) -> QueryReport:
    """Run the requested providers on one image or selection. Failures stay visible."""
    wanted = capabilities or LENS_CAPABILITIES
    height, width = image.shape[:2]
    if x is None or y is None or w is None or h is None:
        crop = image
        region = {"x": 0, "y": 0, "w": int(width), "h": int(height), "translated": False}
    else:
        crop, translated = clip_rect(image, x, y, w, h)
        region = {"x": int(x), "y": int(y), "w": int(w), "h": int(h), "translated": translated}
        if crop is None:
            results = tuple(_no_region(cap) for cap in wanted)
            return QueryReport(source=source, results=results, region=region)
    label = f"{region['w']}x{region['h']}"
    results: list[StructuredResult] = []
    embeddings: dict[str, bytes] = {}
    ocr_text: str | None = None
    barcode_labels: list[str] | None = None
    from semblon.circuits import after_call, before_call

    def guarded(capability: str, produce):
        paused = before_call(capability)
        if paused is not None:
            return paused
        return after_call(produce())

    for capability in wanted:
        if capability == "grounding":
            results.append(guarded(capability, lambda: ground_selection(crop, label)))
        elif capability == "barcode":
            found = guarded(capability, lambda: read_symbology(crop))
            results.append(found)
            barcode_labels = [item.label for item in found.items] if found.status == "SUCCESS" else []
        elif capability == "ocr":
            found = guarded(capability, lambda: read_text(crop))
            results.append(found)
            if found.status == "SUCCESS" and found.items:
                ocr_text = found.items[0].label
        elif capability == "visual_embedding":
            embedded = _embed_guarded(crop, embeddings)
            results.append(embedded)
        elif capability == "translation":
            if "ocr" in wanted and ocr_text is None:
                results.append(
                    guarded(
                        capability,
                        lambda: _blocked(
                            "translation",
                            "Translation did not run because text was not read.",
                            "translation.NO_SOURCE",
                        ),
                    )
                )
            else:
                results.append(guarded(capability, lambda: translate_text(ocr_text)))
        elif capability == "vlm":
            results.append(guarded(capability, lambda: describe_vlm(crop, generate=vlm_generate)))
        elif capability in {"lkg", "landmark", "logo", "product"}:
            labels = barcode_labels
            results.append(
                guarded(
                    capability,
                    lambda cap=capability, labels=labels: _lookup_pack(cap, crop, ocr_text, labels),
                )
            )
        else:
            results.append(
                _blocked(capability, f"Unknown capability {capability}.", f"{capability}.UNKNOWN")
            )
    for row in results:
        if failure_disguised_as_empty(row):
            raise RuntimeError(f"{row.capability_id} disguised a failure as an empty match")
        if row.status == "SUCCESS" and not row.items:
            raise RuntimeError(f"{row.capability_id} returned SUCCESS with no items")
    return QueryReport(source=source, results=tuple(results), region=region, embeddings=embeddings)


def query_screen(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    capabilities: tuple[str, ...] | None = None,
    vlm_generate=None,
    blocked=None,
) -> QueryReport:
    """Selection on the Windows screen, then the same query pipeline as a file."""
    report, _image = query_screen_with_image(
        x,
        y,
        w,
        h,
        capabilities=capabilities,
        vlm_generate=vlm_generate,
        blocked=blocked,
    )
    return report


def query_screen_with_image(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    capabilities: tuple[str, ...] | None = None,
    vlm_generate=None,
    blocked=None,
) -> tuple[QueryReport, np.ndarray | None]:
    """Screen selection query plus captured pixels for downstream local retrieval."""
    captured, image = capture_screen(x, y, w, h, blocked=blocked)
    region = {"x": int(x), "y": int(y), "w": int(w), "h": int(h), "translated": False}
    if image is None:
        wanted = capabilities or LENS_CAPABILITIES
        blocked = [
            _blocked(
                cap,
                "Screen capture did not run. Nothing was searched.",
                f"{cap}.NO_CAPTURE",
            )
            for cap in wanted
        ]
        return (
            QueryReport(
                source="screen",
                results=(captured, *blocked),
                region=region,
            ),
            None,
        )
    inner = query_image(
        image,
        capabilities=capabilities,
        source="screen",
        vlm_generate=vlm_generate,
    )
    return (
        QueryReport(
            source="screen",
            results=(captured, *inner.results),
            region=region,
            embeddings=inner.embeddings,
        ),
        image,
    )


def persist_successes(conn, *, observation_id: str, run_id: str, report: QueryReport) -> dict:
    """Write hits only. Failures stay on the report and do not become empty rows.

    Never writes a person or a face embedding.
    """
    from semblon.observers import persist_item

    counts = {"object": 0, "text": 0, "embedding": 0}
    for row in report.results:
        if row.status != "SUCCESS":
            continue
        for item in row.items:
            if row.capability_id == "barcode":
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="object",
                    provider="symbology",
                    payload={
                        "class": "barcode",
                        "text": item.label,
                        "symbology": item.detail,
                        "identity": "not facekit",
                        "contract_status": "SUCCESS",
                    },
                    score=1.0,
                )
                counts["object"] += 1
            elif row.capability_id == "grounding":
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="object",
                    provider="grounding",
                    payload={
                        "class": "region",
                        "method": item.method,
                        "mask": item.mask,
                        "identity": "not facekit",
                        "contract_status": "SUCCESS",
                    },
                    score=1.0,
                )
                counts["object"] += 1
            elif row.capability_id in {"ocr", "translation", "vlm"}:
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="text",
                    provider=row.provider_id,
                    payload={
                        "text": item.label,
                        "role": row.capability_id,
                        "identity": "not facekit",
                        "contract_status": "SUCCESS",
                    },
                    score=1.0,
                )
                counts["text"] += 1
            elif row.capability_id == "visual_embedding":
                blob = report.embeddings.get("visual_embedding")
                if not blob:
                    continue
                dim = len(blob) // 4
                persist_item(
                    conn,
                    observation_id=observation_id,
                    run_id=run_id,
                    kind="clip",
                    provider="siglip",
                    payload={"space": "siglip", "identity": "not facekit", "contract_status": "SUCCESS"},
                    embedding=blob,
                    modality="siglip",
                    pack_id="siglip/local@1",
                    dim=dim,
                    score=1.0,
                )
                counts["embedding"] += 1
    return counts
