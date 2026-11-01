"""Selection retrieval. One crop runs the local doors and merges them.

Doors:
- region / image similarity (crop embedding, colour only when that is the engine)
- OCR / BM25 search over stored text observations
- object-label search over stored detector labels
- optional language-aligned SigLIP list (same kind)

Each hit keeps the basis that found it. Identity is not a door.
Nothing here writes the store.
"""

from __future__ import annotations

from pathlib import Path

from semblon.query_spec import (
    DOOR_KIND,
    DOOR_LOOK,
    DOOR_OBJECT,
    DOOR_TEXT,
    MODE_KIND,
    QuerySpec,
    mode_label,
    parse_query_spec,
)
from semblon.rank_fusion import feature_rerank, reciprocal_rank_fusion

_TEXT_BASIS = "Text in photos (OCR substring)"
_OBJECT_BASIS = "COCO object detection (NanoDet)"
_KIND_BASIS = "Same kind"
_SKIPPED = "SKIPPED"
_NO_QUERY = "NO_QUERY"
_OBJECT_SKIP_LABELS = {"region", "user_region", "barcode"}
_SIGLIP_PACK = "siglip/local@1"
_SIGLIP_MODALITY = "siglip"


def retrieve_selection(
    store: Path,
    *,
    crop,
    observations: list[dict] | None = None,
    limit: int = 10,
    selection_kind: str | None = None,
    cancelled=None,
    query_spec=None,
    region_rec: dict | None = None,
    media_id: str | None = None,
    parts: list[dict] | None = None,
    selected_region_bbox: dict | None = None,
) -> dict:
    """Run region, text, object, and optional language retrieval, then fuse."""
    spec = parse_query_spec(query_spec)
    kind = str(selection_kind or "").strip().lower()
    cap = max(1, int(limit))
    obs = [row for row in (observations or []) if isinstance(row, dict)]
    channels: list[dict] = []
    grouped: dict[str, dict] = {}
    ranked: dict[str, list[str]] = {}

    if _stopped(cancelled):
        return _empty("CANCELLED", "Selection retrieval was cancelled.", channels, spec, parts)

    _take_region(
        store,
        crop=crop,
        kind=kind,
        limit=cap,
        cancelled=cancelled,
        channels=channels,
        grouped=grouped,
        ranked=ranked,
        region_rec=region_rec,
        spec=spec,
    )
    if _stopped(cancelled):
        return _empty("CANCELLED", "Selection retrieval was cancelled.", channels, spec, parts)
    _take_text(
        store,
        crop=crop,
        observations=obs,
        kind=kind,
        limit=cap,
        channels=channels,
        grouped=grouped,
        ranked=ranked,
        spec=spec,
        exclude_media_id=media_id,
    )
    if _stopped(cancelled):
        return _empty("CANCELLED", "Selection retrieval was cancelled.", channels, spec, parts)
    _take_objects(
        store,
        crop=crop,
        observations=obs,
        selected_region_bbox=selected_region_bbox,
        limit=cap,
        channels=channels,
        grouped=grouped,
        ranked=ranked,
        spec=spec,
        exclude_media_id=media_id,
    )
    if _stopped(cancelled):
        return _empty("CANCELLED", "Selection retrieval was cancelled.", channels, spec, parts)
    _take_kind(
        store,
        crop=crop,
        limit=cap,
        cancelled=cancelled,
        channels=channels,
        grouped=grouped,
        ranked=ranked,
        spec=spec,
        exclude_media_id=media_id,
    )
    return _merged(
        channels,
        grouped,
        ranked,
        limit=cap,
        selection_kind=kind,
        spec=spec,
        parts=parts,
    )


def _stopped(cancelled) -> bool:
    return cancelled is not None and bool(cancelled())


def _empty(status: str, reason: str, channels: list[dict], spec: QuerySpec, parts) -> dict:
    return {
        "kind": "selection_retrieval",
        "status": status,
        "reason": reason,
        "count": 0,
        "items": [],
        "channels": channels,
        "similarity_basis": _join_bases(channels, []),
        "strip_label": _strip_label_from_channels(spec, channels),
        "engine": "selection",
        "query_spec": spec.as_public(),
        "parts": list(parts or []),
        "note": "A selection match is not a named person.",
    }


def _add_hit(grouped: dict[str, dict], item: dict, basis: str, door: str) -> None:
    media_id = str(item.get("media_id") or "").strip()
    if not media_id:
        return
    raw_score = item.get("score")
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None
    if score is None:
        score = 1.0
    norm = item.get("match_norm") if isinstance(item.get("match_norm"), (list, tuple)) else None
    row = grouped.get(media_id)
    if row is None:
        grouped[media_id] = {
            "media_id": media_id,
            "score": score,
            "bases": [basis],
            "door_scores": {door: score},
            "match_norm": list(norm) if norm and len(norm) == 4 else [0.0, 0.0, 0.0, 0.0],
        }
        return
    if basis not in row["bases"]:
        row["bases"].append(basis)
    row["door_scores"][door] = max(float(row["door_scores"].get(door) or 0.0), score)
    if score > float(row["score"]):
        row["score"] = score
    if norm and len(norm) == 4 and not any(float(v) > 0 for v in row["match_norm"]):
        row["match_norm"] = [float(v) for v in norm]


def _region_basis_fallback() -> str:
    return "Similar look"


def _strip_label_from_channels(spec: QuerySpec, channels: list[dict]) -> str:
    """Strip label must not hide Colour only behind Similar look."""
    if spec.mode == MODE_KIND:
        return mode_label(spec.mode)
    for channel in channels:
        door = str(channel.get("door") or "")
        if door not in {DOOR_LOOK, "region"}:
            continue
        if channel.get("status") in {_SKIPPED, _NO_QUERY}:
            continue
        basis = str(channel.get("similarity_basis") or "").strip()
        engine = str(channel.get("engine") or "").lower()
        if not basis:
            continue
        lowered = basis.lower()
        if "colour" in lowered or "color" in lowered or "color-hist" in engine:
            return "Colour only"
        return basis
    return _region_basis_fallback()


def _take_region(store, *, crop, kind, limit, cancelled, channels, grouped, ranked, region_rec, spec) -> None:
    if kind == "text":
        channels.append(
            {
                "door": "region",
                "status": _SKIPPED,
                "similarity_basis": _region_basis_fallback(),
                "reason": "Text-only selection does not run visual similarity.",
                "count": 0,
            }
        )
        return
    if isinstance(region_rec, dict):
        rec = region_rec
    else:
        from semblon.region_search import find_similar_crop

        rec = find_similar_crop(
            store,
            crop=crop,
            limit=limit,
            selection_kind="region",
            observed_text="",
            cancelled=cancelled,
        )
    basis = str(rec.get("similarity_basis") or _region_basis_fallback())
    items = [item for item in (rec.get("items") or []) if isinstance(item, dict)]
    order: list[str] = []
    for item in items:
        media_id = str(item.get("media_id") or "")
        _add_hit(grouped, item, basis, DOOR_LOOK)
        if media_id and media_id not in order:
            order.append(media_id)
    ranked[DOOR_LOOK] = order
    channels.append(
        {
            "door": "region",
            "status": str(rec.get("status") or "NO_RESULT"),
            "similarity_basis": basis,
            "reason": str(rec.get("reason") or ""),
            "error_id": rec.get("error_id"),
            "count": len(items),
            "understanding": str(rec.get("understanding") or ""),
            "engine": str(rec.get("engine") or ""),
        }
    )


def _text_tokens(observations: list[dict], crop, kind: str, spec: QuerySpec) -> tuple[list[str], str]:
    from semblon.region_search import _ocr_crop_text, _text_query_token

    chunks: list[str] = []
    for item in observations:
        if str(item.get("kind") or "") != "text":
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        role = str(payload.get("role") or "ocr")
        if role not in {"ocr", "text"}:
            continue
        text = str(payload.get("text") or "").strip()
        if text:
            chunks.append(text)
    source = "observation"
    if not chunks and crop is not None and kind in {"", "region", "text", "text_priority", "visual"}:
        source = "crop"
        read = str(_ocr_crop_text(crop) or "").strip()
        if read:
            chunks.append(read)
    if spec.modifier:
        chunks.append(spec.modifier)
        source = source or "modifier"
    tokens: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        token = _text_query_token(chunk)
        key = token.lower()
        if token and key not in seen:
            seen.add(key)
            tokens.append(token)
        elif not token and chunk.strip() and chunk.strip().lower() not in seen:
            seen.add(chunk.strip().lower())
            tokens.append(chunk.strip())
    return tokens, source


def _take_text(store, *, crop, observations, kind, limit, channels, grouped, ranked, spec, exclude_media_id) -> None:
    from semblon.observers import probe_ocr_status
    from semblon.search import SearchError, search_text

    tokens, source = _text_tokens(observations, crop, kind, spec)
    if not tokens:
        ready, note = probe_ocr_status()
        if source == "crop" and not ready:
            channels.append(
                {
                    "door": "text",
                    "status": "UNAVAILABLE",
                    "similarity_basis": _TEXT_BASIS,
                    "reason": note or "Text reading is not installed.",
                    "error_id": "ocr.MISSING",
                    "count": 0,
                }
            )
            return
        channels.append(
            {
                "door": "text",
                "status": _NO_QUERY,
                "similarity_basis": _TEXT_BASIS,
                "reason": "No readable text in the selection.",
                "count": 0,
            }
        )
        return
    found: list[dict] = []
    statuses: list[str] = []
    reason = ""
    error_id = None
    order: list[str] = []
    for token in tokens:
        try:
            rec = search_text(store, token, limit=limit)
        except SearchError as exc:
            statuses.append("UNAVAILABLE")
            reason = str(exc)
            error_id = "ocr.NO_STORE"
            continue
        statuses.append(str(rec.get("status") or "NO_RESULT"))
        reason = str(rec.get("reason") or reason)
        error_id = rec.get("error_id") or error_id
        for item in rec.get("items") or []:
            if not isinstance(item, dict):
                continue
            if exclude_media_id and str(item.get("media_id") or "") == str(exclude_media_id):
                continue
            found.append(item)
            _add_hit(grouped, item, _TEXT_BASIS, DOOR_TEXT)
            media_id = str(item.get("media_id") or "")
            if media_id and media_id not in order:
                order.append(media_id)
    ranked[DOOR_TEXT] = order
    status = _fold_status(statuses)
    channels.append(
        {
            "door": "text",
            "status": status,
            "similarity_basis": _TEXT_BASIS,
            "reason": reason,
            "error_id": error_id if status in {"UNAVAILABLE", "ERROR"} else None,
            "count": len({str(item.get("media_id") or "") for item in found if item.get("media_id")}),
            "query": " ".join(tokens),
        }
    )


def _object_labels(
    observations: list[dict],
    crop,
    spec: QuerySpec,
    *,
    selected_region_bbox: dict | None = None,
) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()

    def _add(label: str) -> None:
        text = str(label or "").strip()
        key = text.lower()
        if not text or key in _OBJECT_SKIP_LABELS or key in seen:
            return
        seen.add(key)
        labels.append(text)

    selected_box = None
    if isinstance(selected_region_bbox, dict):
        try:
            x = float(selected_region_bbox["x"])
            y = float(selected_region_bbox["y"])
            w = float(selected_region_bbox["w"])
            h = float(selected_region_bbox["h"])
            if w > 0 and h > 0:
                selected_box = (x, y, x + w, y + h)
        except (KeyError, TypeError, ValueError):
            selected_box = None

    for item in observations:
        if str(item.get("kind") or "") != "object":
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        provider = str(item.get("provider") or "")
        # Only the user box matching this exact selection may contribute a
        # saved human name. Other object labels remain class hints, not names.
        if provider == "user_box" and selected_box is not None:
            bbox = item.get("bbox")
            try:
                candidate_box = tuple(float(v) for v in bbox)
            except (TypeError, ValueError):
                candidate_box = ()
            # Exact pixel box only (tiny float slack). A 1px drift is a
            # different region and must not inherit another region's name.
            if len(candidate_box) == 4 and all(
                abs(a - b) <= 1e-3 for a, b in zip(candidate_box, selected_box)
            ):
                _add(str(payload.get("named") or ""))
            # Named text stays gated above. Class/label hints still flow.
        _add(str(payload.get("label") or payload.get("class") or ""))
    if not labels and crop is not None:
        try:
            from semblon.object_nanodet import detect_objects
            from semblon.object_pack import probe_nanodet_status
        except Exception:
            detect_objects = None
            probe_nanodet_status = None
        if detect_objects is not None and probe_nanodet_status is not None:
            ready, _note = probe_nanodet_status()
            if ready:
                try:
                    for hit in detect_objects(crop) or []:
                        if isinstance(hit, dict):
                            _add(str(hit.get("label") or hit.get("class") or ""))
                except Exception:
                    pass
    if spec.modifier and spec.mode == MODE_KIND:
        _add(spec.modifier)
    return labels


def _take_objects(
    store, *, crop, observations, selected_region_bbox=None, limit, channels,
    grouped, ranked, spec, exclude_media_id
) -> None:
    from semblon.search import SearchError, search_object

    labels = _object_labels(
        observations, crop, spec, selected_region_bbox=selected_region_bbox
    )
    if not labels:
        channels.append(
            {
                "door": "object",
                "status": _NO_QUERY,
                "similarity_basis": _OBJECT_BASIS,
                "reason": "No object label in the selection.",
                "count": 0,
            }
        )
        return
    found: list[dict] = []
    statuses: list[str] = []
    reason = ""
    error_id = None
    order: list[str] = []
    for label in labels:
        try:
            rec = search_object(store, label, limit=limit)
        except SearchError as exc:
            statuses.append("UNAVAILABLE")
            reason = str(exc)
            error_id = "object.NO_STORE"
            continue
        statuses.append(str(rec.get("status") or "NO_RESULT"))
        reason = str(rec.get("reason") or reason)
        error_id = rec.get("error_id") or error_id
        basis = str(rec.get("similarity_basis") or _OBJECT_BASIS)
        for item in rec.get("items") or []:
            if not isinstance(item, dict):
                continue
            if exclude_media_id and str(item.get("media_id") or "") == str(exclude_media_id):
                continue
            found.append(item)
            _add_hit(grouped, item, basis, DOOR_OBJECT)
            media_id = str(item.get("media_id") or "")
            if media_id and media_id not in order:
                order.append(media_id)
    ranked[DOOR_OBJECT] = order
    status = _fold_status(statuses)
    channels.append(
        {
            "door": "object",
            "status": status,
            "similarity_basis": _OBJECT_BASIS,
            "reason": reason,
            "error_id": error_id if status in {"UNAVAILABLE", "ERROR"} else None,
            "count": len({str(item.get("media_id") or "") for item in found if item.get("media_id")}),
            "query": " ".join(labels),
        }
    )


def _take_kind(store, *, crop, limit, cancelled, channels, grouped, ranked, spec, exclude_media_id) -> None:
    from semblon.lens import embed_siglip, probe_siglip

    state = probe_siglip()
    if state != "AVAILABLE" or crop is None:
        channels.append(
            {
                "door": "kind",
                "status": _SKIPPED,
                "similarity_basis": _KIND_BASIS,
                "reason": "Same-kind search is not installed.",
                "count": 0,
            }
        )
        return
    try:
        _report, blob = embed_siglip(crop)
    except Exception:
        blob = None
    if blob is None:
        channels.append(
            {
                "door": "kind",
                "status": _SKIPPED,
                "similarity_basis": _KIND_BASIS,
                "reason": "Same-kind search could not read this area.",
                "count": 0,
            }
        )
        return
    from semblon.region_search import search_vector

    rec = search_vector(
        store,
        blob=blob,
        modality=_SIGLIP_MODALITY,
        pack_id=_SIGLIP_PACK,
        dim=max(1, len(blob) // 4),
        limit=limit,
        exclude_media_id=exclude_media_id,
        cancelled=cancelled,
    )
    status = str(rec.get("status") or "NO_RESULT")
    if status == "UNAVAILABLE":
        channels.append(
            {
                "door": "kind",
                "status": _SKIPPED,
                "similarity_basis": _KIND_BASIS,
                "reason": "Semblon has not looked closely at these photos for same-kind search yet.",
                "count": 0,
            }
        )
        return
    items = [item for item in (rec.get("items") or []) if isinstance(item, dict)]
    order: list[str] = []
    for item in items:
        _add_hit(grouped, item, _KIND_BASIS, DOOR_KIND)
        media_id = str(item.get("media_id") or "")
        if media_id and media_id not in order:
            order.append(media_id)
    ranked[DOOR_KIND] = order
    channels.append(
        {
            "door": "kind",
            "status": status,
            "similarity_basis": _KIND_BASIS,
            "reason": str(rec.get("reason") or ""),
            "count": len(order),
        }
    )


def _fold_status(statuses: list[str]) -> str:
    if any(status == "SUCCESS" for status in statuses):
        return "SUCCESS"
    if any(status == "NO_RESULT" for status in statuses):
        return "NO_RESULT"
    if any(status == "ERROR" for status in statuses):
        return "ERROR"
    return "UNAVAILABLE"


def _join_bases(channels: list[dict], items: list[dict]) -> str:
    ordered: list[str] = []
    for item in items:
        for basis in item.get("bases") or []:
            if basis and basis not in ordered:
                ordered.append(str(basis))
    if ordered:
        return " · ".join(ordered)
    for channel in channels:
        if channel.get("status") in {_SKIPPED, _NO_QUERY}:
            continue
        basis = str(channel.get("similarity_basis") or "")
        if basis and basis not in ordered:
            ordered.append(basis)
    return " · ".join(ordered) or _region_basis_fallback()


def _merged(
    channels: list[dict],
    grouped: dict[str, dict],
    ranked: dict[str, list[str]],
    *,
    limit: int,
    selection_kind: str,
    spec: QuerySpec,
    parts,
) -> dict:
    weights = {
        DOOR_LOOK: 1.35 if spec.mode != MODE_KIND else 0.65,
        DOOR_KIND: 1.35 if spec.mode == MODE_KIND else 0.65,
        DOOR_TEXT: 1.15 if spec.modifier or selection_kind == "text_priority" else 1.0,
        DOOR_OBJECT: 1.0,
    }
    fused = reciprocal_rank_fusion(ranked, weights=weights)
    for media_id, score in fused.items():
        row = grouped.get(media_id)
        if row is None:
            continue
        row["rrf"] = score
    pool = list(grouped.values())
    if selection_kind == "text_priority":
        for row in pool:
            bases = [str(b).lower() for b in row.get("bases") or []]
            if any("text" in basis for basis in bases):
                row["rrf"] = float(row.get("rrf") or 0.0) + 0.02
    reranked = feature_rerank(pool, spec=spec, limit=max(limit, 20))
    items = reranked[:limit]
    packed = []
    for item in items:
        bases = [str(b) for b in item.get("bases") or [] if b]
        packed.append(
            {
                "media_id": item["media_id"],
                "score": float(item.get("score") or 0.0),
                "rrf": float(item.get("rrf") or 0.0),
                "match_norm": item.get("match_norm") or [0.0, 0.0, 0.0, 0.0],
                "bases": bases,
                "door_scores": item.get("door_scores") or {},
                "similarity_basis": " · ".join(bases) if len(bases) > 1 else (bases[0] if bases else _strip_label_from_channels(spec, channels)),
                "why": "selection retrieval; not a person",
            }
        )
    ran = [c for c in channels if c.get("status") not in {_SKIPPED, _NO_QUERY}]
    if packed:
        status = "SUCCESS"
        reason = "Merged selection matches from the local library."
        error_id = None
    elif any(c.get("status") == "UNAVAILABLE" for c in ran):
        status = "UNAVAILABLE"
        reason = next(
            (str(c.get("reason") or "") for c in ran if c.get("status") == "UNAVAILABLE" and c.get("reason")),
            "Nothing was searched.",
        )
        error_id = next((c.get("error_id") for c in ran if c.get("status") == "UNAVAILABLE" and c.get("error_id")), None)
    elif any(c.get("status") == "NO_RESULT" for c in ran):
        status = "NO_RESULT"
        reason = "Searched the selection and nothing matched."
        error_id = None
    elif any(c.get("status") == "ERROR" for c in ran):
        status = "ERROR"
        reason = next((str(c.get("reason") or "") for c in ran if c.get("status") == "ERROR"), "Selection retrieval failed.")
        error_id = next((c.get("error_id") for c in ran if c.get("error_id")), None)
    else:
        status = "UNAVAILABLE"
        reason = "Nothing was searched."
        error_id = None
    understanding = ""
    for channel in channels:
        text = str(channel.get("understanding") or "").strip()
        if text:
            understanding = text
            break
    return {
        "kind": "selection_retrieval",
        "status": status,
        "reason": reason,
        "error_id": error_id,
        "count": len(packed),
        "items": packed,
        "channels": channels,
        "similarity_basis": _join_bases(channels, packed),
        "strip_label": _strip_label_from_channels(spec, channels),
        "engine": "selection",
        "understanding": understanding,
        "selection_kind": selection_kind,
        "query_spec": spec.as_public(),
        "parts": list(parts or []),
        "note": "A selection match is not a named person.",
    }
