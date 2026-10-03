"""Small reusable visual primitives for Home / Canvas / Inspector.

Appearance only. No identity, ingest, or registry behaviour.
Consumes ``ui_tokens`` / Atmosphere so paint is not scattered as hex literals.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Sequence

try:
    import tkinter as tk
    from tkinter import ttk
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]

from semblon.ui_tokens import (
    ACCENT,
    BG_STAGE,
    BG_SUBTLE,
    BG_SURFACE,
    BODY,
    BODY_SM,
    BORDER_DEFAULT,
    BORDER_STRONG,
    CAPTION,
    CAPTION_STRONG,
    FOCUS_RING,
    INK_DISABLED,
    INK_ON_DARK,
    INK_PRIMARY,
    INK_SECONDARY,
    INK_TERTIARY,
    SP_4,
    SP_8,
    SP_12,
)


class MediaTileState(str, Enum):
    """Interaction state for a Memory Canvas media tile."""

    RESTING = "resting"
    HOVER = "hover"
    SELECTED = "selected"
    FOCUS = "focus"
    LOADING = "loading"
    DISABLED = "disabled"


@dataclass(frozen=True)
class MediaTileColors:
    fill: str
    outline: str
    outline_width: int
    label: str
    compare_outline: str
    compare_width: int


@dataclass(frozen=True)
class MediaTileGeometry:
    cell: int = 156
    pad: int = 8
    label_band: int = 18
    label_max_chars: int = 18


MEDIA_TILE_GEOMETRY = MediaTileGeometry()


def media_tile_colors(state: MediaTileState | str = MediaTileState.RESTING) -> MediaTileColors:
    """Tokenized plate / outline / label for one tile state.

    Stage surface stays dominant; hover and selection use accent edges only —
    no gradients, no card shadows.
    """
    st = state if isinstance(state, MediaTileState) else MediaTileState(str(state))
    if st is MediaTileState.LOADING:
        return MediaTileColors(
            fill=BG_SUBTLE,
            outline=BORDER_DEFAULT,
            outline_width=1,
            label=INK_TERTIARY,
            compare_outline=ACCENT,
            compare_width=3,
        )
    if st is MediaTileState.DISABLED:
        return MediaTileColors(
            fill=BG_SUBTLE,
            outline=BORDER_DEFAULT,
            outline_width=1,
            label=INK_DISABLED,
            compare_outline=ACCENT,
            compare_width=3,
        )
    if st is MediaTileState.SELECTED:
        return MediaTileColors(
            fill=BG_STAGE,
            outline=ACCENT,
            outline_width=2,
            label=INK_ON_DARK,
            compare_outline=ACCENT,
            compare_width=3,
        )
    if st is MediaTileState.HOVER:
        return MediaTileColors(
            fill=BG_STAGE,
            outline=BORDER_STRONG,
            outline_width=2,
            label=INK_ON_DARK,
            compare_outline=ACCENT,
            compare_width=3,
        )
    if st is MediaTileState.FOCUS:
        return MediaTileColors(
            fill=BG_STAGE,
            outline=FOCUS_RING,
            outline_width=2,
            label=INK_ON_DARK,
            compare_outline=ACCENT,
            compare_width=3,
        )
    return MediaTileColors(
        fill=BG_STAGE,
        outline=BORDER_DEFAULT,
        outline_width=1,
        label=INK_ON_DARK,
        compare_outline=ACCENT,
        compare_width=3,
    )


def media_tile_state(
    *,
    selected: bool = False,
    hover: bool = False,
    focus: bool = False,
    loading: bool = False,
    disabled: bool = False,
) -> MediaTileState:
    """Resolve one visual state. Selection outranks hover; focus outranks resting."""
    if disabled:
        return MediaTileState.DISABLED
    if loading:
        return MediaTileState.LOADING
    if selected:
        return MediaTileState.SELECTED
    if focus:
        return MediaTileState.FOCUS
    if hover:
        return MediaTileState.HOVER
    return MediaTileState.RESTING


def truncate_label(text: str, *, max_chars: int | None = None) -> str:
    limit = int(max_chars if max_chars is not None else MEDIA_TILE_GEOMETRY.label_max_chars)
    raw = str(text or "")
    if len(raw) <= limit:
        return raw
    if limit <= 1:
        return "…"
    return raw[: max(1, limit - 1)] + "…"


@dataclass(frozen=True)
class InspectorSectionData:
    title: str
    lines: tuple[str, ...]


def sections_from_lines(lines: Sequence[str], *, default_title: str = "Details") -> list[InspectorSectionData]:
    """Split blank-line groups into titled sections when the first line is short."""
    groups: list[list[str]] = [[]]
    for raw in lines:
        line = str(raw)
        if not line.strip():
            if groups[-1]:
                groups.append([])
            continue
        groups[-1].append(line)
    out: list[InspectorSectionData] = []
    for group in groups:
        if not group:
            continue
        head = group[0].strip()
        # Short non-sentence heads become section titles (People, Similar photos, …).
        if len(group) > 1 and len(head) <= 40 and not head.endswith((".", "…")):
            out.append(InspectorSectionData(title=head, lines=tuple(group[1:])))
        else:
            out.append(InspectorSectionData(title=default_title, lines=tuple(group)))
    if not out:
        out.append(InspectorSectionData(title=default_title, lines=()))
    return out


@dataclass(frozen=True)
class SearchPresentation:
    """Structured search chrome — presentation only, no new search engine."""

    query: str
    mode: str
    status: str
    count: int
    lines: tuple[str, ...]
    media_ids: tuple[str, ...]


def search_mode_label(kind: str | None) -> str:
    k = (kind or "").strip().lower()
    return {
        "person": "People",
        "people": "People",
        "text": "Text in photos",
        "similar": "Whole image",
        "whole": "Whole image",
        "region": "Region",
        "face": "Face",
    }.get(k, "Search")


SEARCH_MODES: tuple[tuple[str, str], ...] = (
    ("people", "People"),
    ("text", "Text in photos"),
    ("whole", "Whole image"),
    ("region", "Region"),
)


def similarity_basis_for_mode(mode: str | None) -> str | None:
    m = (mode or "").strip().lower()
    return {
        "whole": "Whole photo (B · search_similar)",
        "similar": "Whole photo (B · search_similar)",
        "region": "Selected region (C · Find Similar)",
        "people": None,
        "text": None,
    }.get(m)


def media_ids_from_search_rec(rec: dict | None) -> list[str]:
    """Pull media ids already present on a search record (history / items)."""
    if not isinstance(rec, dict):
        return []
    found: list[str] = []
    seen: set[str] = set()

    def _add(mid: Any) -> None:
        s = str(mid or "").strip()
        if not s or s in seen:
            return
        seen.add(s)
        found.append(s)

    hist = rec.get("history")
    if isinstance(hist, dict):
        for it in hist.get("items") or []:
            if isinstance(it, dict):
                _add(it.get("media_id"))
    for it in rec.get("items") or []:
        if isinstance(it, dict):
            _add(it.get("media_id"))
    return found


def build_search_presentation(
    rec: dict | None,
    *,
    lines: Sequence[str] | None = None,
    media_ids: Sequence[str] | None = None,
) -> SearchPresentation:
    rec = rec if isinstance(rec, dict) else {}
    kind = str(rec.get("kind") or "search")
    query = str(rec.get("query") or "").strip()
    status = str(rec.get("status") or ("SUCCESS" if int(rec.get("count") or 0) else "")).upper()
    count = int(rec.get("count") or 0)
    body = tuple(str(x) for x in (lines if lines is not None else ()))
    mids = tuple(str(m) for m in (media_ids if media_ids is not None else media_ids_from_search_rec(rec)))
    return SearchPresentation(
        query=query,
        mode=search_mode_label(kind),
        status=status or ("SUCCESS" if count else "NO_RESULT"),
        count=count,
        lines=body,
        media_ids=mids,
    )


def search_header_lines(pres: SearchPresentation) -> list[str]:
    """Compact header block for Inspector Search surface."""
    q = pres.query or "(empty)"
    lines = [
        "Search",
        f"Query: {q}",
        f"Mode: {pres.mode}",
    ]
    basis = similarity_basis_for_mode(
        {
            "People": "people",
            "Text in photos": "text",
            "Whole image": "whole",
            "Similar": "whole",
            "Region": "region",
        }.get(pres.mode, "")
    )
    if basis:
        lines.append(f"Basis: {basis}")
    if pres.count:
        noun = "result" if pres.count == 1 else "results"
        lines.append(f"{pres.count} {noun}")
    elif pres.status in {"NO_RESULT", "SUCCESS"}:
        lines.append("No matches")
    elif pres.status:
        lines.append(pres.status.replace("_", " ").title())
    if pres.media_ids:
        lines.append("Open a photo on the Memory Canvas to continue.")
    return lines


if tk is not None and ttk is not None:

    class InspectorBody(ttk.Frame):
        """Scrollable sectioned Inspector body (replaces details Listbox)."""

        def __init__(self, master, *, width: int = 260, **kw):
            super().__init__(master, **kw)
            self._canvas = tk.Canvas(
                self,
                highlightthickness=0,
                bd=0,
                bg=BG_SURFACE,
                width=width,
            )
            self._sb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
            self._canvas.configure(yscrollcommand=self._sb.set)
            self._inner = ttk.Frame(self._canvas)
            self._win = self._canvas.create_window((0, 0), window=self._inner, anchor=tk.NW)
            self._sb.pack(side=tk.RIGHT, fill=tk.Y)
            self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._inner.bind("<Configure>", self._on_inner_configure)
            self._canvas.bind("<Configure>", self._on_canvas_configure)
            self._sections: list[ttk.Frame] = []

        def _on_inner_configure(self, _event=None) -> None:
            try:
                self._canvas.configure(scrollregion=self._canvas.bbox("all"))
            except tk.TclError:
                pass

        def _on_canvas_configure(self, event) -> None:
            try:
                self._canvas.itemconfigure(self._win, width=max(1, int(event.width)))
            except tk.TclError:
                pass

        def clear(self) -> None:
            for child in list(self._inner.winfo_children()):
                try:
                    child.destroy()
                except tk.TclError:
                    pass
            self._sections = []

        def set_lines(self, lines: Sequence[str], *, default_title: str = "Details") -> None:
            self.set_sections(sections_from_lines(lines, default_title=default_title))

        def set_sections(self, sections: Iterable[InspectorSectionData | tuple[str, Sequence[str]]]) -> None:
            self.clear()
            for sec in sections:
                if isinstance(sec, InspectorSectionData):
                    title, rows = sec.title, sec.lines
                else:
                    title, rows = sec[0], tuple(sec[1])
                block = ttk.Frame(self._inner)
                block.pack(fill=tk.X, anchor=tk.W, pady=(0, SP_12))
                ttk.Label(block, text=title, font=CAPTION_STRONG, foreground=INK_SECONDARY).pack(
                    anchor=tk.W, pady=(0, SP_4)
                )
                if not rows:
                    ttk.Label(
                        block,
                        text="Nothing here yet.",
                        font=BODY_SM,
                        foreground=INK_TERTIARY,
                        wraplength=240,
                    ).pack(anchor=tk.W)
                for row in rows:
                    ttk.Label(
                        block,
                        text=str(row),
                        font=BODY_SM if str(row).startswith("  ") else BODY,
                        foreground=INK_TERTIARY if str(row).startswith("  ") else INK_PRIMARY,
                        wraplength=240,
                        justify=tk.LEFT,
                    ).pack(anchor=tk.W, pady=(0, 1))
                self._sections.append(block)
            self._on_inner_configure()

        def delete(self, *_args, **_kwargs) -> None:
            """Listbox-shaped clear for gradual call-site migration."""
            self._insert_buf = []
            self.clear()

        def insert(self, _index, line: str) -> None:
            """Listbox-shaped append — prefer ``set_lines`` for new call sites."""
            buf = list(getattr(self, "_insert_buf", []) or [])
            buf.append(str(line))
            self._insert_buf = buf
            self.set_lines(buf)

    class ActionGroup(ttk.Frame):
        """Caption + action stack for Inspector verb grouping."""

        def __init__(self, master, title: str, **kw):
            super().__init__(master, **kw)
            ttk.Label(self, text=title, font=CAPTION, foreground=INK_SECONDARY).pack(
                anchor=tk.W, pady=(SP_8, SP_4)
            )
            self.body = ttk.Frame(self)
            self.body.pack(fill=tk.X)

else:  # pragma: no cover

    class InspectorBody:  # type: ignore[no-redef]
        def __init__(self, *_a, **_k):
            raise RuntimeError("tkinter is required")

    class ActionGroup:  # type: ignore[no-redef]
        def __init__(self, *_a, **_k):
            raise RuntimeError("tkinter is required")
