"""Presentation policy for native shell.

Primary mode is non-technical. Advanced mode may expose technical detail.
These helpers do not change backend semantics; they only shape user-facing text.
"""

from __future__ import annotations

import re

PRIMARY = "primary"
ADVANCED = "advanced"
MODES = (PRIMARY, ADVANCED)

_SAFE_PRIMARY_EXACT = {
    "Nothing was searched.",
    "Similar search could not run.",
    "Semblon couldn't complete that step.",
    "Saved name for this group.",
    "Left this group unknown.",
    "Saved your note.",
    "Merged the selected groups.",
    "Split the selected faces into a new group.",
    "Marked this as not the same person.",
    "Saved your decision.",
    "No reviewed run yet.",
    "A name or note is required.",
    "People groups are unavailable right now.",
    "No unnamed groups.",
    "No people matched that search.",
    "Open a photo first.",
    "Draw a region on the photo first.",
    "No similar images found yet.",
    "Similar search needs photos that have already been looked at.",
    "That decision is not available.",
    "Select a group first.",
    "Select another group to merge with.",
    "That group is no longer here.",
    "Select one or more faces to split.",
    "Leave at least one face in the group.",
}

_SAFE_PRIMARY_PATTERNS = (
    re.compile(r"^Saved name: [^\n]+\.$"),
    re.compile(r"^Found: [^\n]+\.$"),
    re.compile(r"^Found \d+ matches\. Top results: [^\n]+\.$"),
)

_WORD_REPLACEMENTS = (
    (re.compile(r"\bclusters\b", flags=re.IGNORECASE), "groups"),
    (re.compile(r"\bcluster\b", flags=re.IGNORECASE), "group"),
)


def normalize_mode(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    return text if text in MODES else PRIMARY


def is_primary_safe_message(text: str) -> bool:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return False
    for line in lines:
        if line in _SAFE_PRIMARY_EXACT:
            continue
        if any(pattern.match(line) for pattern in _SAFE_PRIMARY_PATTERNS):
            continue
        return False
    return True


def sanitize_primary(text: str, *, fallback: str = "Semblon couldn't complete that step.") -> str:
    cleaned = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    if not is_primary_safe_message(cleaned):
        return fallback
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