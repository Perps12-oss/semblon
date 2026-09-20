"""User-facing progress and error copy.

Never invent a percentage. Never use internal stage/kind names as the
primary headline. Never claim success when something failed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_PARTIAL,
    KIND_PROGRESS,
    KIND_QUEUED,
    KIND_STALLED,
    KIND_STARTED,
    STAGE_CLUSTER,
    STAGE_DISCOVER,
    STAGE_EXPORT,
    STAGE_INGEST,
    STAGE_PROCESS,
    ProgressEvent,
    ratio_percent,
)

STAGE_LABELS = {
    STAGE_PROCESS: "Processing",
    STAGE_DISCOVER: "Looking through your folder",
    STAGE_INGEST: "Reading photos",
    STAGE_CLUSTER: "Grouping faces",
    STAGE_EXPORT: "Writing review",
}

KIND_LABELS = {
    KIND_QUEUED: "Queued",
    KIND_STARTED: "Started",
    KIND_PROGRESS: "Working",
    KIND_PARTIAL: "Partial",
    KIND_COMPLETED: "Done",
    KIND_FAILED: "Couldn't finish",
    KIND_CANCELLED: "Cancelled",
    KIND_STALLED: "Still working",
}

_IN_PROGRESS = frozenset(
    {KIND_QUEUED, KIND_STARTED, KIND_PROGRESS, KIND_PARTIAL, KIND_STALLED}
)

# counts_line only prints these keys; anything else is ignored by design.
COUNT_LABELS = {
    "photos": "photos",
    "videos": "videos",
    "people": "people",
    "clusters": "groups",
    "tracks": "tracks",
    "skipped": "skipped",
    "failed": "failed",
    "skipped_seen": "already seen",
}

_ERROR_DETAIL_MAX = 180


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, kind)


def user_state(ev: ProgressEvent) -> str:
    return STAGE_LABELS.get(ev.stage, "Processing")


def basename(path: str | None) -> str:
    if not path:
        return ""
    trimmed = str(path).rstrip("/\\")
    if not trimmed:
        return ""
    return Path(trimmed.replace("\\", "/")).name


def headline(ev: ProgressEvent) -> str:
    """Primary line. Internal stage/kind tokens stay out of this string."""
    if ev.kind == KIND_STALLED:
        text = "Still working — this is taking longer than usual"
    elif ev.kind == KIND_CANCELLED:
        text = kind_label(KIND_CANCELLED)
    elif ev.kind == KIND_FAILED:
        text = kind_label(KIND_FAILED)
    elif ev.kind == KIND_COMPLETED:
        text = f"{user_state(ev)} done"
    elif ev.kind == KIND_QUEUED:
        text = f"{kind_label(KIND_QUEUED)} — {user_state(ev)}"
    elif ev.message and not _looks_internal(ev.message):
        text = ev.message
    else:
        text = user_state(ev)
    if ev.kind in _IN_PROGRESS and not text.endswith("…") and not text.endswith("..."):
        text = f"{text}…"
    return text


def _looks_internal(message: str) -> bool:
    lowered = message.strip().lower()
    if ":" in lowered and lowered.split(":", 1)[0] in STAGE_LABELS:
        return True
    return lowered in KIND_LABELS or lowered in STAGE_LABELS


def counts_line(ev: ProgressEvent) -> str | None:
    bits: list[str] = []
    if ev.files_processed is not None and ev.files_total is not None:
        bits.append(f"{ev.files_processed} of {ev.files_total} files")
    elif ev.current is not None and ev.total is not None:
        bits.append(f"{ev.current} of {ev.total}")
    elif ev.current is not None:
        bits.append(f"{ev.current} processed")
    elif ev.files_processed is not None:
        bits.append(f"{ev.files_processed} processed")
    if ev.faces_found is not None:
        bits.append(f"{ev.faces_found} faces")
    if ev.counts:
        for key, label in COUNT_LABELS.items():
            value = ev.counts.get(key)
            if value is not None:
                bits.append(f"{value} {label}")
    return " · ".join(bits) if bits else None


def current_item_line(ev: ProgressEvent) -> str | None:
    name = basename(ev.path)
    if not name:
        return None
    return f"Current: {name}"


def percent_text(ev: ProgressEvent) -> str | None:
    """Percent only when the event already has one, or files_processed/files_total."""
    if ev.percent is not None:
        return f"{ev.percent:g}%"
    pct = ratio_percent(ev.files_processed, ev.files_total)
    if pct is None:
        return None
    return f"{pct:g}%"


def status_lines(ev: ProgressEvent) -> list[str]:
    """Headline plus supporting lines. Callers may also use percent_text on its own for a bar."""
    lines = [headline(ev)]
    counts = counts_line(ev)
    if counts:
        lines.append(counts)
    pct = percent_text(ev)
    if pct:
        lines.append(pct)
    item = current_item_line(ev)
    if item:
        lines.append(item)
    if ev.kind == KIND_STALLED:
        lines.append("Semblon is still running. You can keep using the app or press Cancel.")
    if ev.kind == KIND_CANCELLED:
        lines.append("Any partial results have been retained.")
    if ev.kind == KIND_FAILED and ev.error:
        detail = str(ev.error).strip()
        if len(detail) > _ERROR_DETAIL_MAX:
            detail = detail[: _ERROR_DETAIL_MAX - 1] + "…"
        lines.append(f"Detail: {detail}")
    return lines


def status_text(ev: ProgressEvent) -> str:
    """Single status string for Home / CLI. Percent is included when real."""
    return "  ".join(status_lines(ev))


def _is_cancel(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    return "cancel" in name or "cancel" in str(exc).lower()


def _is_store_damage(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.DatabaseError):
        return True
    name = type(exc).__name__.lower()
    blob = f"{name} {exc}".lower()
    return "integrity" in blob or "database disk image is malformed" in blob or "corrupt" in blob


def friendly_exception(exc: BaseException) -> tuple[str, str]:
    """(user message, diagnostic detail). Never claims success.

    Does not claim existing results are safe when the store may be damaged.
    """
    detail = f"{type(exc).__name__}: {exc}"
    if _is_cancel(exc):
        return ("Cancelled. Any partial results have been retained.", detail)
    if _is_store_damage(exc):
        return (
            "Semblon couldn't complete this operation.\n"
            "The store may need an integrity check before you rely on existing results.",
            detail,
        )
    return ("Semblon couldn't complete this operation.", detail)
