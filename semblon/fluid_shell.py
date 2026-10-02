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
    "LIBRARY_FILTERS",
    "library_source_types",
    "footer_library_line",
    "footer_status_word",
    "people_review_banner",
]

ONBOARD_HEADLINE = "Welcome to Semblon"
ONBOARD_SUBCOPY = "Your local, private visual memory."
ONBOARD_PRIVACY = (
    "Your photos stay on your PC.\n"
    "Choose a folder to build your local visual library."
)
ONBOARD_CTA = "Select Photo Folder"

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
