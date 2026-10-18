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
    "Select a face on the photo first.",
    "No similar images found yet.",
    "Similar search needs photos that have already been looked at.",
    "That decision is not available.",
    "Select a group first.",
    "Select another group to merge with.",
    "That group is no longer here.",
    "Select one or more faces to split.",
    "Leave at least one face in the group.",
    "No groups yet.",
    "Groups could not be read.",
    "No photo for this group.",
    "Groups are hypotheses until you name them. A group is not a person.",
    "Opened the candidate group for this face.",
    "Opened this person.",
    "No candidate group for this face yet.",
    "No dated photos for this person yet.",
    "Opened this person in Time.",
    "Showing only this person's photos.",
    "Showing the full archive again.",
    "Opened overlooked faces for review.",
    "No overlooked faces right now.",
    "This photo is missing from its stored path. If you moved or renamed it, add that folder again so Semblon can reconnect it.",
    "Opened photo. No date on file — time context unavailable.",
    "Kept this find.",
    "A match is a similar region, not proof it is the same object.",
    "Still indexing. Photos already added can be opened.",
    "Still indexing. This photo can already be searched.",
    "This photo is not indexed yet. Add its folder so search can see inside it.",
    "This photo has a coarse index only. Matches may miss the area you point at.",
}

_SAFE_PRIMARY_PATTERNS = (
    re.compile(r"^Saved name: [^\n]+\.$"),
    re.compile(r"^Found: [^\n]+\.$"),
    re.compile(r"^Found \d+ matches\. Top results: [^\n]+\.$"),
    re.compile(r"^Library check: [^\n]+\.$"),
    re.compile(r"^Density is [^\n]+\.$"),
    re.compile(r"^Search looks at [^\n]+\.$"),
    re.compile(r"^Showing [^\n]+\.$"),
    re.compile(r"^Reset finished\. [^\n]+\.$"),
    re.compile(r"^Activity: [^\n]+\.$"),
    re.compile(r"^Unresolved: [^\n]+\.$"),
    re.compile(r"^Review counts: [^\n]+\.$"),
    re.compile(r"^Duplicates: [^\n]+\.$"),
    re.compile(r"^GPU: [^\n]+\.$"),
    re.compile(r"^Capabilities: [^\n]+\.$"),
    re.compile(r"^Pack: [^\n]+\.$"),
    re.compile(r"^Model file: [^\n]+\.$"),
    re.compile(r"^Moments: [^\n]+\.$"),
    re.compile(r"^Folders: [^\n]+\.$"),
    re.compile(r"^Days: [^\n]+\.$"),
    re.compile(r"^Text search: [^\n]+\.$"),
    re.compile(r"^Object search: [^\n]+\.$"),
    re.compile(r"^Similar: [^\n]+\.$"),
    re.compile(r"^Similar \([^)]+\): [^\n]+\.$"),
    re.compile(r"^Showing only [^\n]+\.$"),
    re.compile(r"^Overlooked faces: [^\n]+\.$"),
    re.compile(r"^Named items: [^\n]+\.$"),
    re.compile(r"^Rescan: [^\n]+\.$"),
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


def group_list_title(*, named: bool, names: list[str], kind: str, band: str) -> str:
    """Primary list title. Named persons keep their name; others stay hypotheses."""
    if named:
        for name in names or []:
            text = str(name or "").strip()
            if text:
                return text
        return "Named person"
    kind = str(kind or "").strip().lower()
    band = str(band or "").strip().lower()
    if kind == "track":
        return "Track (not a person)"
    if kind == "unassigned":
        return "Unassigned face"
    if band == "strong":
        return "Strong candidate group"
    return "Candidate group"


def group_band_label(*, named: bool, kind: str, band: str) -> str:
    """Secondary honesty line for a board row."""
    if named:
        return "Named person"
    kind = str(kind or "").strip().lower()
    band = str(band or "").strip().lower()
    if kind == "track":
        return "Appearance track — not a person"
    if kind == "unassigned":
        return "Single face — name to confirm"
    if band == "strong":
        return "Strong candidate — name to confirm"
    return "Needs review — name to confirm"