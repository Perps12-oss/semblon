"""Blank sheet for a real Home session. Nothing in here is a judgement.

The person at the photograph fills the row. A model must not.
One bad interaction gets one primary class. Performance and the
machine belong on the session header, not as a reason to retune hover.
"""

from __future__ import annotations

# Primary class for one bad pointer interaction. Not a score.
FAILURE_CLASSES = (
    "DISCOVERY",
    "LATTICE",
    "SLICE",
    "RENDERER",
    "NAMING",
)

STEPS = (
    "Open the photograph. It should appear before analysis finishes.",
    "Move the pointer. Do not click Analyse. Do not draw a box.",
    "Does the lit boundary match a piece you would naturally point at?",
    "If it does not, name the first layer only: discovery, lattice, slice, renderer, or naming.",
    "A lit piece with no word is allowed. Do not invent a word to make the row look finished.",
    "Reopen the same photograph. The stored regions should come back without a second wait.",
)


def session_header() -> dict:
    """Facts from the Windows process. Leave None until that process is the one running."""
    return {
        "windows_version": None,
        "python_version": None,
        "python_arch": None,
        "process_arch": None,
        "execution": None,
        "torch_backend": None,
        "directml": None,
        "sam2_runtime": None,
        "checkpoint": None,
        "naming": None,
        "home_launched": None,
        "blocker": None,
    }


def blank_row(image: str) -> dict:
    return {
        "image": image,
        "scene": "",
        "expected": "",
        "proposed": None,
        "retained": None,
        "exposed": None,
        "highlight_matched": None,
        "too_fragmented": None,
        "too_broad": None,
        "nested_missing": None,
        "unnamed": None,
        "label_correct": None,
        "analysis_time": None,
        "rendering_notes": "",
        "failure_class": "",
        "note": "",
    }


def sheet(images: list[str]) -> list[dict]:
    return [blank_row(image) for image in images]
