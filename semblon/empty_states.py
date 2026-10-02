"""UX Rescue §§12–17 — shared empty-state anatomy and error classification.

Presentation only. No identity, clustering, JobEngine, ingest, or schema changes.
Forbidden in empty states: paths, run IDs, store jargon, layer vocab, "Error"
for expected empties.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

try:
    from semblon import ui_tokens as _tokens
except ImportError:  # pragma: no cover — tokens land via parallel UX slice
    _tokens = None

SEARCH_PLACEHOLDER = "Search memory…"
SEARCH_PLACEHOLDER_PHOTOS = "Search memory…"


def search_placeholder(*, has_named_people: bool) -> str:
    """Placeholder when named people exist vs first-run / unnamed-only library."""
    if has_named_people:
        return SEARCH_PLACEHOLDER
    return SEARCH_PLACEHOLDER_PHOTOS


# Soft action ids for Home wiring (map to existing job-bar / review handlers).
ACTION_ADD_FOLDER = "add_folder"
ACTION_ADD_ANOTHER_FOLDER = "add_another_folder"
ACTION_OPEN_REVIEW = "open_review"
ACTION_CLEAR_SEARCH = "clear_search"
ACTION_REVIEW_PEOPLE = "review_people"


def _font(role: str, fallback: tuple[str, int]) -> tuple[str, int]:
    if _tokens is None:
        return fallback
    get = getattr(_tokens, "font", None)
    if callable(get):
        try:
            return tuple(get(role))  # type: ignore[return-value]
        except Exception:  # noqa: BLE001
            return fallback
    return fallback


FONT_HEADING = _font("h2", ("Segoe UI", 16, "bold"))
FONT_BODY = _font("body", ("Segoe UI", 11))
FONT_CAPTION = _font("caption", ("Segoe UI", 9))


@dataclass(frozen=True)
class EmptyState:
    """Global empty-state anatomy (§12): headline + description + one primary.

    Tertiary is optional and must never match primary visual weight.
    """

    headline: str
    description: str
    primary_action: str | None = None
    tertiary_action: str | None = None
    action_id: str | None = None
    tertiary_action_id: str | None = None

    def as_lines(self) -> list[str]:
        """Inspector / listbox rendering. No paths, run IDs, or Error titles."""
        lines = [self.headline, self.description]
        if self.primary_action:
            lines.append(self.primary_action)
        if self.tertiary_action:
            lines.append(self.tertiary_action)
        return lines


# ── Per-screen content (§12 table + §13–16 variants) ─────────────────────────


def photos_empty() -> EmptyState:
    return EmptyState(
        headline="No photos yet",
        description="Add a photo folder to begin.",
        primary_action="Add a photo folder",
        action_id=ACTION_ADD_FOLDER,
    )


def videos_empty() -> EmptyState:
    return EmptyState(
        headline="No videos yet",
        description="Add or process a video to see people found in it.",
        primary_action="Add a folder",
        action_id=ACTION_ADD_FOLDER,
    )


def people_empty() -> EmptyState:
    return EmptyState(
        headline="No people yet",
        description=(
            "Open People to name, pick a group you recognise, "
            "and give them a name."
        ),
        primary_action="People to name",
        action_id=ACTION_REVIEW_PEOPLE,
        tertiary_action="Open Review",
        tertiary_action_id=ACTION_OPEN_REVIEW,
    )


def to_review_empty(*, has_store: bool, has_faces: bool = False) -> EmptyState:
    """§13 — route display label is To review; route id stays ``unknown``."""
    if not has_store:
        return EmptyState(
            headline="Nothing to review yet",
            description=(
                "Add a photo folder first. Semblon will find and group faces "
                "for you to review here."
            ),
            primary_action="Add a photo folder",
            action_id=ACTION_ADD_FOLDER,
        )
    if not has_faces:
        return EmptyState(
            headline="No faces to review",
            description="Semblon checked your photos but didn't find any faces to group.",
            primary_action="Add another folder",
            action_id=ACTION_ADD_ANOTHER_FOLDER,
        )
    return EmptyState(
        headline="Nothing to review yet",
        description=(
            "Add a photo folder first. Semblon will find and group faces "
            "for you to review here."
        ),
        primary_action="Add a photo folder",
        action_id=ACTION_ADD_FOLDER,
    )


def activity_empty() -> EmptyState:
    return EmptyState(
        headline="No activity yet",
        description="Your recent photo processing and results will appear here.",
        primary_action="Add a photo folder",
        action_id=ACTION_ADD_FOLDER,
    )


def search_no_store() -> EmptyState:
    return EmptyState(
        headline="Nothing to search yet",
        description="Add a photo folder first.",
        primary_action="Add a photo folder",
        action_id=ACTION_ADD_FOLDER,
    )


def search_no_named_people() -> EmptyState:
    return EmptyState(
        headline="No named people yet",
        description="After you review and name people, you can find them here.",
        primary_action="Open Review",
        action_id=ACTION_OPEN_REVIEW,
    )


def search_no_matches(query: str) -> EmptyState:
    q = (query or "").strip() or "…"
    return EmptyState(
        headline=f'No matches for "{q}"',
        description=(
            "Try another person name, or words that appear in a photo."
        ),
        tertiary_action="Clear search",
        tertiary_action_id=ACTION_CLEAR_SEARCH,
    )


def search_library_analysing() -> EmptyState:
    """Search while an ingest/process job is still building the library."""
    return EmptyState(
        headline="Still analysing your library",
        description=(
            "Semblon is still finding faces and building your photo library. "
            "Search will work better when this finishes — or try a name you "
            "have already reviewed."
        ),
        primary_action="Open Review",
        action_id=ACTION_OPEN_REVIEW,
    )


def search_text_unavailable(*, reason: str | None = None) -> EmptyState:
    """OCR/text search could not run — optional model or no stored reads."""
    detail = (reason or "").strip()
    if not detail:
        detail = (
            "Text in photos is optional. Semblon can still find people "
            "you have named."
        )
    return EmptyState(
        headline="Text search unavailable",
        description=detail,
        tertiary_action="Clear search",
        tertiary_action_id=ACTION_CLEAR_SEARCH,
    )


def search_text_error(*, reason: str | None = None) -> EmptyState:
    """Text search failed — soft product copy, no capability ids."""
    detail = (reason or "").strip() or "Semblon could not read text in photos right now."
    return EmptyState(
        headline="Couldn't search text",
        description=detail,
        tertiary_action="Clear search",
        tertiary_action_id=ACTION_CLEAR_SEARCH,
    )


def loading_workspace(label: str = "results") -> EmptyState:
    """Cheap loading copy — never fake progress percentages."""
    noun = (label or "results").strip() or "results"
    return EmptyState(
        headline=f"Loading {noun}…",
        description="This should only take a moment.",
    )


def disabled_while_busy(action: str = "this") -> EmptyState:
    """Controls disabled while a job runs — soft, not an Error title."""
    bit = (action or "this").strip() or "this"
    return EmptyState(
        headline="Not available right now",
        description=f"Finish or cancel processing before {bit}.",
    )


def photos_videos_nothing_selected(*, kind: str = "photo") -> EmptyState:
    """§15 inspector with no selection (populated library)."""
    noun = "photo or video" if kind == "any" else kind
    return EmptyState(
        headline="Nothing selected",
        description=f"Select a {noun} to see details.",
    )


def lens_empty() -> EmptyState:
    """Lens workspace with no current photo — guide, never a capability dump."""
    return EmptyState(
        headline="Nothing to look at yet",
        description="Open a photo, then select something to look at.",
        primary_action="Browse photos",
        action_id="browse_photos",
    )


# ── Soft populated copy (formatters) ─────────────────────────────────────────


def groups_waiting_line(n: int) -> str:
    """Populated review-queue counts — same noun as the status bar."""
    from semblon.library_status import people_to_name_text

    n = int(n)
    if n <= 0:
        return "No people to name."
    return people_to_name_text(n) + "."


def activity_history_lines(
    *,
    photos: int | None = None,
    faces: int | None = None,
    groups: int | None = None,
    stamped: str | None = None,
    has_unnamed: bool = False,
) -> list[str]:
    """§14 populated history row — plain language, no integrity/tracks jargon."""
    if photos is not None and photos > 0:
        title = f"{photos} photos processed"
    else:
        title = "Processing complete"
    bits: list[str] = []
    if faces is not None:
        bits.append(f"{faces} faces")
    if groups is not None:
        bits.append(f"{groups} groups")
    lines = [title]
    if bits:
        lines.append(" · ".join(bits))
    if stamped:
        lines.append(stamped)
    if has_unnamed:
        lines.append("Review people")
    return lines


def search_result_lines(rec: dict, *, advanced: bool = False) -> list[str]:
    """§16 populated / empty search rendering. Demote modality=/pack= by default.

    Hierarchy (product): results → no match → unavailable (optional) → error.
    Never ANN-as-production theatre; never capability ids in soft copy.
    """
    kind = rec.get("kind")
    if kind == "person":
        items = rec.get("items") or []
        if not items:
            return search_no_matches(str(rec.get("query") or "")).as_lines()
        lines = ["People"]
        for i in items:
            name = i.get("display_name") or "Named person"
            faces = i.get("faces", 0)
            lines.append(f"{name}  ({faces} photos)" if faces else str(name))
            if advanced and i.get("why"):
                lines.append(f"  {i.get('why')}")
            if advanced and i.get("person_id"):
                lines.append(f"  person_id={i.get('person_id')}")
        return lines
    if kind == "similar":
        status = str(rec.get("status") or "").upper()
        if status == "UNAVAILABLE":
            reason = str(
                rec.get("reason")
                or "Similar photos need an optional model. Nothing was searched."
            )
            return [
                "Similar photos unavailable",
                reason,
            ]
        if status in {"ERROR", "TIMEOUT", "CANCELLED"}:
            return [
                "Couldn't compare photos",
                str(rec.get("reason") or "Similarity did not run."),
            ]
        lines: list[str] = ["Similar photos"]
        if advanced:
            lines = [
                f"similar {rec.get('query')}  modality={rec.get('modality')}  "
                f"pack={rec.get('pack_id')}",
                rec.get("note") or "Similarity is not identity.",
            ]
            if rec.get("fallback"):
                lines.append(f"fallback={rec.get('fallback')}")
        else:
            # Soft honesty: library scan is authoritative; index is optional speed.
            reason = str(rec.get("reason") or "")
            if "index is absent" in reason.lower() or "library" in reason.lower():
                lines.append("Searched your library directly.")
            elif rec.get("note"):
                note = str(rec.get("note"))
                if "identity" in note.lower():
                    lines.append("Similar looking — not the same as a named person.")
                else:
                    lines.append(note)
        for i in rec.get("items") or []:
            score = i.get("score")
            if advanced:
                if score is None:
                    s = "n/a"
                else:
                    try:
                        s = f"{float(score):.4f}"
                    except (TypeError, ValueError):
                        s = "n/a"
                lines.append(
                    f"{s}  {i.get('kind')}  {i.get('item_id')}  {i.get('why', '')}"
                )
            else:
                label = i.get("item_id") or i.get("kind") or "result"
                lines.append(str(label))
        if rec.get("count") == 0:
            if status == "NO_RESULT":
                lines.append(str(rec.get("reason") or "Nothing matched in your library."))
            else:
                lines.append("No matches nearby.")
        return lines
    if kind == "text":
        status = str(rec.get("status") or "").upper()
        if status == "UNAVAILABLE":
            return search_text_unavailable(reason=str(rec.get("reason") or "")).as_lines()
        if status in {"ERROR", "TIMEOUT", "CANCELLED"}:
            return search_text_error(reason=str(rec.get("reason") or "")).as_lines()
        lines = [f'Text in photos for "{rec.get("query") or ""}"']
        if advanced:
            lines = [
                f"OCR text {rec.get('query')!r}  hits={rec.get('count', 0)}",
                rec.get("note") or "OCR text is not identity.",
            ]
        for i in rec.get("items") or []:
            snippet = (i.get("text") or "")[:80]
            if advanced:
                lines.append(f"{i.get('item_id')}  {snippet!r}  {i.get('why', '')}")
            else:
                lines.append(snippet or str(i.get("item_id") or ""))
        if rec.get("count") == 0:
            if status == "NO_RESULT":
                lines.append(str(rec.get("reason") or "No text matched in your photos."))
            else:
                lines.append("No text matches.")
        return lines
    return []


# ── §17 classification ───────────────────────────────────────────────────────


class ConditionKind(str, Enum):
    EXPECTED = "expected"
    FAILURE = "failure"


# Substrings / exact messages that are normal product states, not failures.
_EXPECTED_MARKERS = (
    "store not found",
    "store has no runs",
    "no store",
    "no runs",
    "person query is empty",
    "text query is empty",
    "unknown run",  # empty/missing run selection for review inbox — soft empty
)


def classify_condition(
    exc_or_msg: BaseException | str | None,
    *,
    has_store: bool | None = None,
) -> ConditionKind:
    """Classify expected empties vs real failures (§17).

    Expected → empty-state surface. Failure → friendly dialog with optional details.
    """
    if has_store is False:
        return ConditionKind.EXPECTED
    if exc_or_msg is None:
        return ConditionKind.EXPECTED
    if isinstance(exc_or_msg, BaseException):
        # Structural DB / IO failures always surface as failures.
        import sqlite3

        if isinstance(exc_or_msg, (sqlite3.DatabaseError, OSError)):
            # "store not found" style ValueErrors are expected; OSError on missing
            # path may still be expected when the file simply does not exist yet.
            if isinstance(exc_or_msg, FileNotFoundError):
                return ConditionKind.EXPECTED
            if isinstance(exc_or_msg, OSError) and getattr(exc_or_msg, "errno", None) == 2:
                return ConditionKind.EXPECTED
            if isinstance(exc_or_msg, sqlite3.DatabaseError):
                return ConditionKind.FAILURE
            # Other OSError (permission, etc.) = failure
            if isinstance(exc_or_msg, OSError):
                return ConditionKind.FAILURE
        name = type(exc_or_msg).__name__.lower()
        if "cancel" in name:
            return ConditionKind.EXPECTED
        blob = f"{name} {exc_or_msg}".lower()
    else:
        blob = str(exc_or_msg).lower()
    for marker in _EXPECTED_MARKERS:
        if marker in blob:
            return ConditionKind.EXPECTED
    return ConditionKind.FAILURE


def is_expected_condition(exc_or_msg: BaseException | str | None, **kw: Any) -> bool:
    return classify_condition(exc_or_msg, **kw) is ConditionKind.EXPECTED


@dataclass(frozen=True)
class FailureDialog:
    headline: str
    body: str
    detail: str


def failure_dialog_for(exc: BaseException) -> FailureDialog:
    """§17 failure copy. Exception type stays in ``detail`` only."""
    detail = f"{type(exc).__name__}: {exc}"
    blob = f"{type(exc).__name__} {exc}".lower()
    if "integrity" in blob or "malformed" in blob or "corrupt" in blob:
        return FailureDialog(
            headline="Semblon couldn't open your library.",
            body=(
                "Try opening Semblon again. If the problem continues, "
                "your library may need to be checked."
            ),
            detail=detail,
        )
    return FailureDialog(
        headline="Semblon couldn't complete this.",
        body="Try again. If the problem continues, check Advanced diagnostics.",
        detail=detail,
    )


def show_failure_dialog(
    parent: Any,
    exc: BaseException,
    *,
    tk_mod: Any = None,
    ttk_mod: Any = None,
) -> None:
    """Friendly failure dialog with optional Show details (exception).

    Falls back to ``messagebox.showerror`` titled ``Semblon`` (never bare ``Error``)
    when tk Toplevel is unavailable.
    """
    dialog = failure_dialog_for(exc)
    if tk_mod is None or ttk_mod is None:
        try:
            from tkinter import messagebox as mb
        except ModuleNotFoundError:  # pragma: no cover
            return
        mb.showerror("Semblon", f"{dialog.headline}\n\n{dialog.body}")
        return

    win = tk_mod.Toplevel(parent) if parent is not None else tk_mod.Tk()
    try:
        from semblon.ui_theme import apply_theme

        apply_theme(win)
    except Exception:  # noqa: BLE001 — dialog still works on the default theme
        pass
    win.title("Semblon")
    win.resizable(False, False)
    win.minsize(480, 0)
    frame = ttk_mod.Frame(win, padding=16)
    frame.pack(fill="both", expand=True)
    ttk_mod.Label(frame, text=dialog.headline, font=FONT_HEADING, wraplength=360).pack(
        anchor="w"
    )
    ttk_mod.Label(frame, text=dialog.body, font=FONT_BODY, wraplength=360).pack(
        anchor="w", pady=(8, 0)
    )
    detail_var = tk_mod.StringVar(value="")
    detail_lbl = ttk_mod.Label(
        frame, textvariable=detail_var, font=FONT_CAPTION, wraplength=360
    )

    def _toggle() -> None:
        if detail_var.get():
            detail_var.set("")
            detail_lbl.pack_forget()
        else:
            detail_var.set(dialog.detail)
            detail_lbl.pack(anchor="w", pady=(12, 0))

    btns = ttk_mod.Frame(frame)
    btns.pack(fill="x", pady=(16, 0))
    ttk_mod.Button(btns, text="Close", command=win.destroy).pack(side="right")
    ttk_mod.Button(btns, text="Show details", command=_toggle).pack(
        side="right", padx=(0, 8)
    )
    try:
        win.transient(parent)
        win.grab_set()
    except Exception:  # noqa: BLE001
        pass


def mount_empty_state(
    parent: Any,
    state: EmptyState,
    *,
    on_primary: Callable[[], None] | None = None,
    on_tertiary: Callable[[], None] | None = None,
    tk_mod: Any = None,
    ttk_mod: Any = None,
) -> Any:
    """Build centered empty-state widgets (§12 anatomy). Returns the frame."""
    if ttk_mod is None:
        raise RuntimeError("ttk is required to mount an empty state")
    wrap = ttk_mod.Frame(parent, padding=16)
    inner = ttk_mod.Frame(wrap)
    inner.pack(anchor="center", pady=24)
    ttk_mod.Label(inner, text=state.headline, font=FONT_HEADING, wraplength=360).pack(
        anchor="center", pady=(0, 8)
    )
    ttk_mod.Label(
        inner, text=state.description, font=FONT_BODY, wraplength=360, justify="center"
    ).pack(anchor="center", pady=(0, 16))
    if state.primary_action and on_primary is not None:
        ttk_mod.Button(inner, text=state.primary_action, command=on_primary).pack(
            anchor="center"
        )
    if state.tertiary_action and on_tertiary is not None:
        ttk_mod.Button(inner, text=state.tertiary_action, command=on_tertiary).pack(
            anchor="center", pady=(8, 0)
        )
    return wrap


def library_has_media_lines(lines: list[str]) -> bool:
    """True when format_library_lines shows real media (not an empty/no-store line)."""
    if not lines:
        return False
    head = (lines[0] or "").lower()
    if "no store" in head or "no media" in head or "unavailable" in head:
        return False
    return len(lines) > 1 or ("showing" in head and " of " in head)
