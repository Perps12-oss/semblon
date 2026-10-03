"""Discovery → Compare → Decide (session-scoped).

Continuation of the Similar result set on Memory Canvas. Not a Light Table app,
not identity, not filesystem delete. Pure helpers — no Tk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

COMPARE_MIN = 2
COMPARE_MAX = 4

DECISION_KEEP = "keep"
DECISION_REJECT = "reject"


@dataclass
class CompareSession:
    """Contextual comparison over a Similar result set."""

    active: bool = False
    result_ids: list[str] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)
    compare_ids: list[str] = field(default_factory=list)
    focus_index: int = 0
    decisions: dict[str, str] = field(default_factory=dict)

    def clear(self) -> None:
        self.active = False
        self.result_ids.clear()
        self.selected_ids.clear()
        self.compare_ids.clear()
        self.focus_index = 0
        self.decisions.clear()

    def set_result_ids(self, media_ids: list[str] | None) -> None:
        self.result_ids = [str(m) for m in (media_ids or []) if m]
        # Drop selections that left the set.
        alive = set(self.result_ids)
        self.selected_ids = [m for m in self.selected_ids if m in alive]
        self.compare_ids = [m for m in self.compare_ids if m in alive]
        if self.active and len(self.compare_ids) < COMPARE_MIN:
            self.active = False
            self.compare_ids.clear()
            self.focus_index = 0

    def visible_result_ids(self) -> list[str]:
        """Result set minus session-rejected candidates (files remain on disk)."""
        return [
            m
            for m in self.result_ids
            if self.decisions.get(m) != DECISION_REJECT
        ]

    def toggle_selected(self, media_id: str) -> list[str]:
        mid = str(media_id)
        if mid not in self.result_ids:
            return list(self.selected_ids)
        if self.decisions.get(mid) == DECISION_REJECT:
            return list(self.selected_ids)
        if mid in self.selected_ids:
            self.selected_ids = [m for m in self.selected_ids if m != mid]
        else:
            if len(self.selected_ids) >= COMPARE_MAX:
                return list(self.selected_ids)
            self.selected_ids.append(mid)
        return list(self.selected_ids)

    def can_enter(self) -> tuple[bool, str]:
        n = len(self.selected_ids)
        if n < COMPARE_MIN:
            return False, f"Select {COMPARE_MIN}–{COMPARE_MAX} similar candidates to compare."
        if n > COMPARE_MAX:
            return False, f"Compare supports at most {COMPARE_MAX} photos."
        if len(self.visible_result_ids()) < COMPARE_MIN and n < COMPARE_MIN:
            return False, "Not enough candidates left to compare."
        return True, ""

    def enter(self) -> tuple[bool, str]:
        ok, reason = self.can_enter()
        if not ok:
            return False, reason
        self.compare_ids = list(self.selected_ids[:COMPARE_MAX])
        self.focus_index = 0
        self.active = True
        return True, ""

    def exit(self) -> None:
        self.active = False
        self.compare_ids.clear()
        self.focus_index = 0

    def focused_id(self) -> str | None:
        if not self.active or not self.compare_ids:
            return None
        i = max(0, min(self.focus_index, len(self.compare_ids) - 1))
        return self.compare_ids[i]

    def move_focus(self, delta: int) -> str | None:
        if not self.active or not self.compare_ids:
            return None
        self.focus_index = max(
            0, min(self.focus_index + int(delta), len(self.compare_ids) - 1)
        )
        return self.focused_id()

    def decide(self, media_id: str, decision: str) -> dict:
        """Session decision. Reject hides from result set; never deletes files."""
        mid = str(media_id)
        if decision not in {DECISION_KEEP, DECISION_REJECT}:
            return {"ok": False, "reason": "Unknown decision."}
        if mid not in self.result_ids and mid not in self.compare_ids:
            return {"ok": False, "reason": "Not a candidate in this result set."}
        self.decisions[mid] = decision
        if mid in self.selected_ids:
            self.selected_ids = [m for m in self.selected_ids if m != mid]
        if mid in self.compare_ids:
            idx = self.compare_ids.index(mid)
            self.compare_ids = [m for m in self.compare_ids if m != mid]
            if self.compare_ids:
                self.focus_index = min(idx, len(self.compare_ids) - 1)
            else:
                self.active = False
                self.focus_index = 0
        return {
            "ok": True,
            "decision": decision,
            "media_id": mid,
            "compare_active": self.active,
            "compare_ids": list(self.compare_ids),
            "visible_ids": self.visible_result_ids(),
            "deleted_file": False,
            "person_id_written": False,
        }


def compare_unavailable_lines(*, selected_count: int, result_count: int) -> list[str]:
    if result_count <= 0:
        return [
            "Nothing to compare.",
            "",
            "Find Similar first, then select candidates.",
        ]
    if result_count == 1:
        return [
            "Only one similar result.",
            "",
            "Open it in the Inspector, or Find Similar from another detail.",
        ]
    if selected_count < COMPARE_MIN:
        return [
            f"Select {COMPARE_MIN}–{COMPARE_MAX} candidates to compare.",
            "",
            "Ctrl+click thumbnails in the Similar results to select.",
            "Keep and Reject are session decisions — not identity, not delete.",
        ]
    if selected_count > COMPARE_MAX:
        return [
            f"Compare supports at most {COMPARE_MAX} photos.",
            "",
            "Deselect some candidates, then Compare again.",
        ]
    return ["Compare is unavailable."]


def decision_lines(decision: str, *, remaining: int) -> list[str]:
    if decision == DECISION_KEEP:
        head = "Kept for this discovery session."
    else:
        head = "Rejected for this discovery session (file not deleted)."
    return [
        head,
        "",
        f"{remaining} candidate{'s' if remaining != 1 else ''} left in Similar results.",
        "This is not a person identity decision.",
    ]
