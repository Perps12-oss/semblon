"""Local knowledge pack. A missing pack is not an empty library. Never a person."""

from __future__ import annotations

import json
from pathlib import Path

from semblon.runtime_contract import ResultItem, StructuredResult, invoke


class PackError(ValueError):
    pass


def load_pack(path: Path | None) -> dict | None:
    if path is None or not Path(path).is_file():
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise PackError("knowledge pack must be an object with entries")
    return data


def match_pack(pack: dict, *, kind: str, texts: tuple[str, ...]) -> list[ResultItem]:
    wanted = kind
    needles = tuple(text.strip().lower() for text in texts if text and text.strip())
    items: list[ResultItem] = []
    for entry in pack.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("kind") != wanted:
            continue
        match = entry.get("match") or {}
        keys = []
        for field in ("text", "barcode", "label"):
            value = match.get(field)
            if isinstance(value, str) and value.strip():
                keys.append(value.strip().lower())
        if not keys or not needles:
            continue
        if any(key in needle or needle in key for key in keys for needle in needles):
            items.append(
                ResultItem(
                    id=str(entry.get("id") or f"{kind}-{len(items)}"),
                    kind=kind,
                    label=str(entry.get("label") or ""),
                    detail=str(entry.get("provenance") or "local pack"),
                )
            )
    return items


def lookup(kind: str, texts: tuple[str, ...], *, pack_path: Path | None) -> StructuredResult:
    capability = {"product": "product", "logo": "logo", "landmark": "landmark"}.get(kind, "lkg")
    try:
        pack = load_pack(pack_path)
    except PackError as exc:
        result, _ = invoke(capability, model_state="CORRUPT", run=lambda: {"crash": str(exc)})
        return result
    if pack is None:
        result, _ = invoke(capability)
        return result
    items = match_pack(pack, kind=kind if capability != "lkg" else kind, texts=texts)
    if capability == "lkg":
        items = []
        for entry_kind in ("product", "logo", "landmark"):
            items.extend(match_pack(pack, kind=entry_kind, texts=texts))
    result, _ = invoke(capability, model_state="AVAILABLE", run=lambda: items)
    return result
