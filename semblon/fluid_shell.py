"""Fluid Visual Workspace — pure presentation helpers.

No store writes. No identity. Consumes library summaries and filter keys only.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ONBOARD_HEADLINE",
    "ONBOARD_SUBCOPY",
    "ONBOARD_PRIVACY",
    "ONBOARD_CTA",
    "STAGE_HEADLINE",
    "STAGE_SUBCOPY",
    "STAGE_PRIVACY",
    "STAGE_CTA",
    "STAGE_EXPLORE_TITLE",
    "STAGE_EXPLORE_BODY",
    "STAGE_DISCOVER_TITLE",
    "STAGE_DISCOVER_BODY",
    "STAGE_PEOPLE_TITLE",
    "STAGE_PEOPLE_BODY",
    "LIBRARY_FILTERS",
    "library_source_types",
    "footer_library_line",
    "footer_status_word",
    "people_review_banner",
    "people_chrome_label",
]

# Model D — Home Stage (capability introduction). ONBOARD_* kept as aliases.
STAGE_HEADLINE = "Your visual memory."
STAGE_SUBCOPY = (
    "Keep photos where they are. Explore, discover, and organise people "
    "when it helps — all local."
)
STAGE_PRIVACY = "Local · private · files stay put."
STAGE_CTA = "Add your photo folder"

STAGE_EXPLORE_TITLE = "Explore"
STAGE_EXPLORE_BODY = "See your photos and videos as a living library."
STAGE_DISCOVER_TITLE = "Discover"
STAGE_DISCOVER_BODY = (
    "Find things, regions, text, and visually similar content across your memory."
)
STAGE_PEOPLE_TITLE = "People"
STAGE_PEOPLE_BODY = (
    "Organise people when useful. Naming is optional. Unknown stays valid."
)

# Compatibility aliases (tests / older call sites).
ONBOARD_HEADLINE = STAGE_HEADLINE
ONBOARD_SUBCOPY = STAGE_SUBCOPY
ONBOARD_PRIVACY = STAGE_PRIVACY
ONBOARD_CTA = STAGE_CTA

# Product filter key → canvas source_types (None = all media).
LIBRARY_FILTERS: tuple[tuple[str, str], ...] = (
    ("all", "All"),
    ("photos", "Photos"),
    ("videos", "Videos"),
)


def library_source_types(filter_key: str) -> tuple[str, ...] | None:
    key = (filter_key or "all").strip().lower()
    if key == "photos":
        return ("folder", "")
    if key == "videos":
        return ("video",)
    return None


def footer_library_line(summary: dict | None) -> str:
    """``N photos · M videos`` — no face counts in the footer."""
    if not summary:
        return "No library yet"
    photos = int(summary.get("photos") if summary.get("photos") is not None else 0)
    videos = int(summary.get("videos") if summary.get("videos") is not None else 0)
    if photos <= 0 and videos <= 0:
        files = int(summary.get("files") or 0)
        if files > 0:
            return f"{files:,} file{'s' if files != 1 else ''}"
        return "No media yet"
    return (
        f"{photos:,} photo{'s' if photos != 1 else ''} · "
        f"{videos:,} video{'s' if videos != 1 else ''}"
    )


def footer_status_word(*, busy: bool, paused: bool = False) -> str:
    if busy and paused:
        return "Paused"
    if busy:
        return "Scanning library…"
    return "Ready"


def people_review_banner(unnamed: int) -> str | None:
    n = int(unnamed or 0)
    if n <= 0:
        return None
    if n == 1:
        return "Some people still need names."
    return "Some people still need names."


def people_chrome_label(unnamed: int | None = None) -> str:
    """Compact header label — People, with review count when useful."""
    n = int(unnamed or 0)
    if n <= 0:
        return "People"
    return f"People · {n}"
