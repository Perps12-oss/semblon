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
    "That is not a folder. Drop a folder of photos, or use Add a folder.",
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
    "These are two named people, so Semblon will not join them. Rename one to tell them apart.",
    "Pick a different group to say this is the same.",
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
    "A folder is being added. Wait until that finishes.",
    "Library clear was cancelled.",
    "The library could not be cleared.",
    "Semblon's list of your photos was cleared. Your original photos were not changed. Add a folder to start again.",
    "A match is a similar region, not proof it is the same object.",
    "Still looking through your photos. Ones already added can be opened.",
    "Still looking through your photos. This one can already be searched.",
    "Semblon has not looked at this photo yet. Add its folder so search can see inside it.",
    "Semblon has only had a quick look at this photo. Matches may miss the area you point at.",
    "Naming this area.",
    "This area could not be named.",
    "Unlabelled region.",
    "Face in the selection. Not a named person.",
    "Checked the matches.",
    "The piece that finds a similar look is ready. Semblon will try that search again.",
    "That piece was already here. Semblon will try the similar-look search again.",
    "That extra piece is installed on this computer.",
    "Choose a reference file on this computer.",
    "That file is not a reference Semblon can use.",
    "Semblon can now look for things in pictures. That search will run again.",
    "Looking for things in pictures was already ready. That search will run again.",
    "Semblon can now describe a picture. That will run again.",
    "Describing a picture was already ready. It will run again.",
    "Semblon is already looking at the screen.",
    "Stopped looking at the screen.",
    "Text first — read the words on screen.",
    "Picture first — match the look on screen.",
    "You pointed at words on the screen.",
    "You pointed at something on the screen.",
}

_SAFE_PRIMARY_PATTERNS = (
    re.compile(r"^Saved name: [^\n]+\.$"),
    re.compile(r"^Found: [^\n]+\.$"),
    re.compile(r"^Found \d+ matches\. Top results: [^\n]+\.$"),
    re.compile(r"^Library check: [^\n]+\.$"),
    re.compile(r"^Density is [^\n]+\.$"),
    re.compile(r"^Search looks at [^\n]+\.$"),
    re.compile(r"^Search quality is [^\n]+\.$"),
    re.compile(r"^Confidence \d+%\.$"),
    re.compile(r"^First look \d+ ms\.$"),
    re.compile(r"^First look \d+ ms\. Refined \d+ ms\.$"),
    re.compile(r"^Looks like a [^\n]+\.$"),
    re.compile(r"^Object: [^\n]+\.$"),
    re.compile(r"^Text: [^\n]+\.$"),
    re.compile(r"^Showing [^\n]+\.$"),
    re.compile(r"^Reset finished\. [^\n]+\.$"),
    re.compile(r"^Activity: [^\n]+\.$"),
    re.compile(r"^Unresolved: [^\n]+\.$"),
    re.compile(r"^Review counts: [^\n]+\.$"),
    re.compile(r"^Duplicates: [^\n]+\.$"),
    re.compile(r"^GPU: [^\n]+\.$"),
    re.compile(r"^Extras: [^\n]+\.$"),
    re.compile(r"^Face files: [^\n]+\.$"),
    re.compile(r"^Extra: [^\n]+\.$"),
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
    re.compile(r"^Setup: [^\n]+\.$"),
    re.compile(r"^Reference notes loaded \(\d+\)\.$"),
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