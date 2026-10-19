"""Selection retrieval. One crop runs the local doors and merges them.

Doors:
- region / image similarity (crop embedding, colour only when that is the engine)
- OCR substring search over stored text observations
- object-label search over stored detector labels

Each hit keeps the basis that found it. Ranked lists fuse with Reciprocal
Rank Fusion, then a cheap rescore when extra signals exist. Identity is
not a door. Nothing here writes the store.
"""

from __future__ import annotations

from pathlib import Path

_TEXT_BASIS = "Text in photos (OCR substring)"
_OBJECT_BASIS = "COCO object detection (NanoDet)"
_SKIPPED = "SKIPPED"
_NO_QUERY = "NO_QUERY"
_OBJECT_SKIP_LABELS = {"region", "user_region", "barcode"}


def retrieve_selection(
    store: Path,
    *,
    crop,
    observations: list[dict] | None = None,
    limit: int = 10,
    selection_kind: str | None = None,
    cancelled=None,
) -> dict:
    """Run region, text, and object retrieval for one selection, then merge."""
    kind = str(selection_kind or "").strip().lower()
    cap = max(1, int(limit))
    obs = [row for row in (observations or []) if isinstance(row, dict)]
    channels: list[dict] = []

    if _stopped(cancelled):
        return _empty("CANCELLED", "Selection retrieval was cancelled.", channels)

    _take_region(
        store,
        crop=crop,
        kind=kind,
        limit=cap,
        cancelled=cancelled,
        channels=channels,
    )
    if _stopped(cancelled):
        return _empty("CANCELLED", "Selection retrieval was cancelled.", channels)
    _take_text(
        store,
        crop=crop,
        observations=obs,
        kind=kind,
        limit=cap,
        channels=channels,
    )
    if _stopped(cancelled):
        return _empty("CANCELLED", "Selection retrieval was cancelled.", channels)
    _take_objects(
        store,
        observations=obs,
        limit=cap,
        channels=channels,
    )
    return _merged(channels, limit=cap, selection_kind=kind)


def _stopped(cancelled) -> bool:
    return cancelled is not None and bool(cancelled())


def _empty(status: str, reason: str, channels: list[dict]) -> dict:
    return {
        "kind": "selection_retrieval",
        "status": status,
        "reason": reason,
        "count": 0,
        "items": [],
        "channels": channels,
        "similarity_basis": _basis_label(channels, []),
        "engine": "selection",
        "note": "A selection match is not a named person.",
    }


def _channel_item(item: dict, basis: str) -> dict | None:
    media_id = str(item.get("media_id") or "").strip()
    if not media_id:
        return None
    if str(item.get("modality") or "") == "face":
        return None
    raw_score = item.get("score")
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None
    if score is None:
        score = 1.0
    norm = item.get("match_norm") if isinstance(item.get("match_norm"), (list, tuple)) else None
    return {
        "media_id": media_id,
        "score": score,
        "similarity_basis": basis,
        "match_norm": list(norm) if norm and len(norm) == 4 else [0.0, 0.0, 0.0, 0.0],
    }


def _region_basis_fallback() -> str:
    return "Similar look"


def _take_region(store, *, crop, kind, limit, cancelled, channels) -> None:
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
    packed = [row for item in items if (row := _channel_item(item, basis))]
    channels.append(
        {
            "door": "region",
            "status": str(rec.get("status") or "NO_RESULT"),
            "similarity_basis": basis,
            "reason": str(rec.get("reason") or ""),
            "error_id": rec.get("error_id"),
            "count": len(packed),
            "items": packed,
            "understanding": str(rec.get("understanding") or ""),
            "engine": str(rec.get("engine") or ""),
        }
    )


def _text_tokens(observations: list[dict], crop, kind: str) -> tuple[list[str], str]:
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
    tokens: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        token = _text_query_token(chunk)
        key = token.lower()
        if token and key not in seen:
            seen.add(key)
            tokens.append(token)
    return tokens, source


def _take_text(store, *, crop, observations, kind, limit, channels) -> None:
    from semblon.observers import probe_ocr_status
    from semblon.search import SearchError, search_text

    tokens, source = _text_tokens(observations, crop, kind)
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
            if isinstance(item, dict):
                row = _channel_item(item, _TEXT_BASIS)
                if row is not None:
                    found.append(row)
    status = _fold_status(statuses)
    channels.append(
        {
            "door": "text",
            "status": status,
            "similarity_basis": _TEXT_BASIS,
            "reason": reason,
            "error_id": error_id if status in {"UNAVAILABLE", "ERROR"} else None,
            "count": len({str(item.get("media_id") or "") for item in found if item.get("media_id")}),
            "items": found,
            "query": " ".join(tokens),
        }
    )


def _object_labels(observations: list[dict]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for item in observations:
        if str(item.get("kind") or "") != "object":
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        label = str(payload.get("label") or payload.get("class") or "").strip()
        if not label or label.lower() in _OBJECT_SKIP_LABELS:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def _take_objects(store, *, observations, limit, channels) -> None:
    from semblon.search import SearchError, search_object

    labels = _object_labels(observations)
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
            if isinstance(item, dict):
                row = _channel_item(item, basis)
                if row is not None:
                    found.append(row)
    status = _fold_status(statuses)
    channels.append(
        {
            "door": "object",
            "status": status,
            "similarity_basis": _OBJECT_BASIS,
            "reason": reason,
            "error_id": error_id if status in {"UNAVAILABLE", "ERROR"} else None,
            "count": len({str(item.get("media_id") or "") for item in found if item.get("media_id")}),
            "items": found,
            "query": " ".join(labels),
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


def _basis_label(channels: list[dict], items: list[dict]) -> str:
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


def _merged(channels: list[dict], *, limit: int, selection_kind: str) -> dict:
    from semblon.retrieval_fuse import fuse_hits

    packed_channels: dict[str, list[dict]] = {}
    for channel in channels:
        if channel.get("status") in {_SKIPPED, _NO_QUERY}:
            continue
        door = str(channel.get("door") or "").strip()
        if not door:
            continue
        packed_channels[door] = [
            item for item in (channel.get("items") or []) if isinstance(item, dict)
        ]
    fused = fuse_hits(
        packed_channels,
        text_priority=selection_kind == "text_priority",
        limit=limit,
    )
    packed = []
    for item in fused:
        bases = [str(b) for b in item.get("bases") or [] if b]
        packed.append(
            {
                "media_id": item["media_id"],
                "score": float(item["score"]),
                "rrf": float(item.get("rrf") or 0.0),
                "match_norm": item["match_norm"],
                "bases": bases,
                "similarity_basis": " · ".join(bases),
                "why": "selection retrieval (RRF); not a person",
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
        "similarity_basis": _basis_label(channels, packed),
        "engine": "selection",
        "understanding": understanding,
        "selection_kind": selection_kind,
        "note": "A selection match is not a named person.",
    }
