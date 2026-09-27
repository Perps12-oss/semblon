"""Human evaluation sheet. The model does not fill in the judgement."""

from __future__ import annotations

FAILURE_CLASSES = (
    "DISCOVERY",
    "FILTERING",
    "NAMING",
    "GRANULARITY",
    "SLICE",
    "OWNERSHIP",
    "COORDINATE",
    "RENDERING",
    "PERFORMANCE",
    "PROVIDER",
)

STEPS = (
    "Open the photograph. It should appear before analysis finishes.",
    "Move the pointer across the picture. Do not click Analyse.",
    "Does the highlight match a piece you would point at?",
    "Is the piece too big, too small, or about right?",
    "If a word appears, is it useful? If no word appears, should it have stayed quiet?",
    "Note a piece you expected and did not get.",
    "Note a highlight that felt wrong or awkward.",
    "Name the first layer that failed. Do not retune a later layer to hide it.",
)


def blank_row(image: str) -> dict:
    return {
        "image": image,
        "meaningful": None,
        "granularity": None,
        "label_useful": None,
        "should_have_abstained": None,
        "missed": "",
        "awkward": "",
        "failure_class": "",
    }


def sheet(images: list[str]) -> list[dict]:
    return [blank_row(image) for image in images]
