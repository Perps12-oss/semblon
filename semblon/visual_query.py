"""Shared visual-query orchestration for media and screen sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from semblon.lens import query_image, query_screen_with_image, report_observations
from semblon.selection import format_query_lines, lens_result_summary, load_media_bgr

VisualQuerySource = Literal["media", "screen"]


@dataclass(frozen=True)
class VisualQuery:
    source: VisualQuerySource
    media_id: str = ""
    rect: dict | None = None
    screen_rect: dict | None = None
    capabilities: tuple[str, ...] | None = None
    limit: int = 10
    selection_kind: str | None = None


@dataclass(frozen=True)
class VisualQueryResult:
    source: VisualQuerySource
    summary: dict
    similar: dict | None = None

    def as_dict(self) -> dict:
        out = dict(self.summary)
        out["source"] = self.source
        if self.similar is not None:
            out["similar"] = self.similar
        return out


def _summary(report, *, media_id: str = "") -> dict:
    rec = lens_result_summary(report)
    rec["lines"] = format_query_lines(report)
    rec["region"] = dict(getattr(report, "region", {}) or {})
    rec["media_id"] = str(media_id or "")
    rec["observations"] = report_observations(report)
    return rec


def _observed_text(observations: list[dict] | None) -> str:
    if not observations:
        return ""
    chunks: list[str] = []
    for item in observations:
        if str(item.get("kind") or "") != "text":
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        text = str(payload.get("text") or "").strip()
        if text:
            chunks.append(text)
    return " ".join(chunks).strip()


def run_visual_query(store: Path, query: VisualQuery, *, cancelled=None) -> VisualQueryResult:
    if query.source == "media":
        image = load_media_bgr(store, query.media_id)
        if image is None:
            reason = "Could not read that photo. Nothing was searched."
            return VisualQueryResult(
                source="media",
                summary={
                    "status": "UNAVAILABLE",
                    "reason": reason,
                    "lines": ["Could not read that photo.", "Nothing was searched."],
                    "media_id": str(query.media_id or ""),
                    "region": None,
                    "item_count": 0,
                },
            )
        kwargs: dict = {}
        if query.rect:
            kwargs["x"] = int(query.rect["x"])
            kwargs["y"] = int(query.rect["y"])
            kwargs["w"] = int(query.rect["w"])
            kwargs["h"] = int(query.rect["h"])
        report = query_image(image, capabilities=query.capabilities, **kwargs)
        return VisualQueryResult(source="media", summary=_summary(report, media_id=query.media_id))
    if query.source != "screen":
        raise ValueError(f"unknown visual query source {query.source}")
    rect = dict(query.screen_rect or {})
    x = int(rect.get("x") or 0)
    y = int(rect.get("y") or 0)
    w = int(rect.get("w") or 0)
    h = int(rect.get("h") or 0)
    report, crop = query_screen_with_image(
        x,
        y,
        w,
        h,
        capabilities=query.capabilities,
    )
    summary = _summary(report)
    if crop is None:
        return VisualQueryResult(source="screen", summary=summary, similar=None)
    from semblon.region_search import find_similar_crop

    similar = find_similar_crop(
        store,
        crop=crop,
        limit=max(1, int(query.limit)),
        selection_kind=query.selection_kind,
        observed_text=_observed_text(summary.get("observations") if isinstance(summary, dict) else None),
        cancelled=cancelled,
    )
    return VisualQueryResult(source="screen", summary=summary, similar=similar)

