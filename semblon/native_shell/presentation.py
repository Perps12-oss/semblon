"""Presentation policy for native shell.

Primary mode is non-technical. Advanced mode may expose technical detail.
These helpers do not change backend semantics; they only shape user-facing text.
"""

from __future__ import annotations

import re

PRIMARY = "primary"
ADVANCED = "advanced"
MODES = (PRIMARY, ADVANCED)

_TECH_TOKENS = (
    "traceback",
    "sqlite",
    "cluster_id",
    "person_id",
    "run_id",
    "pack_id",
    "embedding",
    "model_state",
    "provider_state",
    "error_id",
)

_WORD_REPLACEMENTS = (
    (re.compile(r"\bclusters\b", flags=re.IGNORECASE), "groups"),
    (re.compile(r"\bcluster\b", flags=re.IGNORECASE), "group"),
)


def normalize_mode(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    return text if text in MODES else PRIMARY


def _drop_technical_lines(text: str) -> str:
    kept: list[str] = []
    for line in str(text or "").splitlines():
        lowered = line.lower()
        if any(token in lowered for token in _TECH_TOKENS):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def sanitize_primary(text: str, *, fallback: str = "Semblon couldn't complete that step.") -> str:
    cleaned = _drop_technical_lines(text)
    for pattern, replacement in _WORD_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    cleaned = cleaned.strip()
    return cleaned or fallback


def present_message(mode: str, text: str, *, fallback: str = "Semblon couldn't complete that step.") -> str:
    if normalize_mode(mode) == ADVANCED:
        return str(text or fallback).strip() or fallback
    return sanitize_primary(text, fallback=fallback)


def decision_success(kind: str, detail: str = "") -> str:
    lowered = str(kind or "").strip().lower()
    if lowered == "name":
        who = str(detail or "").strip()
        return f"Saved name: {who}." if who else "Saved name for this group."
    if lowered == "ignore":
        return "Left this group unknown."
    if lowered == "note":
        return "Saved your note."
    if lowered == "merge":
        return "Merged the selected groups."
    if lowered == "split":
        return "Split the selected faces into a new group."
    if lowered == "rule_out":
        return "Marked this as not the same person."
    return "Saved your decision."


def summarize_people_results(names: list[str], total: int, mode: str) -> str:
    if total <= 0:
        return "No people matched that search."
    if normalize_mode(mode) == ADVANCED:
        preview = ", ".join(names[:4])
        return f"Matches: {total}. {preview}" if preview else f"Matches: {total}."
    preview = ", ".join(names[:3])
    if total <= 3:
        return f"Found: {preview}."
    return f"Found {total} matches. Top results: {preview}."