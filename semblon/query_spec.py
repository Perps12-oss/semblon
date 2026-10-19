"""Query specification for local region search.

Frontend contract. User-facing words only. Not identity.
No new store columns. A missing door stays off; it does not fail the search.
"""

from __future__ import annotations

from dataclasses import dataclass

MODE_LOOK = "look"
MODE_KIND = "kind"
MODES = (MODE_LOOK, MODE_KIND)
DEFAULT_MODE = MODE_LOOK

DOOR_LOOK = "look"
DOOR_TEXT = "text"
DOOR_OBJECT = "object"
DOOR_KIND = "kind"
DOORS = (DOOR_LOOK, DOOR_TEXT, DOOR_OBJECT, DOOR_KIND)

_MODE_LABELS = {
    MODE_LOOK: "Same look",
    MODE_KIND: "Same kind",
}
_MODE_HINTS = {
    MODE_LOOK: "Finds this thing again, even from another angle.",
    MODE_KIND: "Finds other things of the same kind.",
}


def normalize_mode(value: str | None) -> str:
    key = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in {"same_look", "exact", "instance", "appearance"}:
        return MODE_LOOK
    if key in {"same_kind", "semantic", "category", "kind_of"}:
        return MODE_KIND
    if key in MODES:
        return key
    return DEFAULT_MODE


def mode_label(value: str | None) -> str:
    return _MODE_LABELS[normalize_mode(value)]


def mode_hint(value: str | None) -> str:
    return _MODE_HINTS[normalize_mode(value)]


def normalize_modifier(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())[:80]


def normalize_part_index(value) -> int:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return -1
    return index if index >= -1 else -1


def _doors_for_mode(mode: str) -> tuple[str, ...]:
    if mode == MODE_KIND:
        return (DOOR_KIND, DOOR_TEXT, DOOR_OBJECT, DOOR_LOOK)
    return (DOOR_LOOK, DOOR_TEXT, DOOR_OBJECT, DOOR_KIND)


@dataclass(frozen=True)
class QuerySpec:
    """What to search. The shell shows labels, not model names."""

    mode: str = DEFAULT_MODE
    modifier: str = ""
    part_index: int = -1

    @property
    def doors(self) -> tuple[str, ...]:
        return _doors_for_mode(self.mode)

    @property
    def look_weight(self) -> float:
        return 0.45 if self.mode == MODE_LOOK else 0.18

    @property
    def kind_weight(self) -> float:
        return 0.18 if self.mode == MODE_LOOK else 0.42

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "mode_label": mode_label(self.mode),
            "mode_hint": mode_hint(self.mode),
            "modifier": self.modifier,
            "part_index": self.part_index,
            "doors": list(self.doors),
        }

    def as_public(self) -> dict:
        """Fields a non-technical UI can bind without translation."""
        rec = self.as_dict()
        rec["whole_area"] = self.part_index < 0
        rec["has_word"] = bool(self.modifier)
        rec["hint"] = refine_hint(self)
        return rec


def parse_query_spec(payload=None) -> QuerySpec:
    if isinstance(payload, QuerySpec):
        return payload
    data = payload if isinstance(payload, dict) else {}
    return QuerySpec(
        mode=normalize_mode(data.get("mode") or data.get("refine_mode")),
        modifier=normalize_modifier(data.get("modifier") or data.get("word") or data.get("text")),
        part_index=normalize_part_index(data.get("part_index", data.get("part", -1))),
    )


def refine_hint(spec: QuerySpec | None = None) -> str:
    spec = spec if isinstance(spec, QuerySpec) else parse_query_spec(spec)
    if spec.modifier:
        return f"{mode_hint(spec.mode)} Using the word {spec.modifier}."
    return f"{mode_hint(spec.mode)} You can pick a part or add a word."


def empty_parts() -> list[dict]:
    return [
        {
            "index": -1,
            "label": "Whole area",
            "kind": "whole",
            "norm": None,
            "selected": True,
        }
    ]
