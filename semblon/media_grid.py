"""Media grid ViewModel — presentation rows only.

No store writes, detector, embed, or OCR. Canvas paint/hover consume this
ViewModel; hover must never start SAM2 / embed / OCR.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

__all__ = [
    "DENSITY_COMFORTABLE",
    "DENSITY_COMPACT",
    "DENSITIES",
    "MediaGridItem",
    "MediaGridViewModel",
    "density_geometry",
    "build_media_grid",
    "visible_index_range",
    "load_grid_density",
    "save_grid_density",
]

DENSITY_COMFORTABLE = "comfortable"
DENSITY_COMPACT = "compact"
DENSITIES = (DENSITY_COMFORTABLE, DENSITY_COMPACT)

_DENSITY_GEOM = {
    DENSITY_COMFORTABLE: {"cell": 156, "pad": 8, "label_band": 18, "overscan": 2},
    DENSITY_COMPACT: {"cell": 112, "pad": 6, "label_band": 16, "overscan": 3},
}


@dataclass(frozen=True)
class MediaGridItem:
    media_id: str
    path: str
    label: str
    source_type: str
    compare_marked: bool = False
    index: int = 0


@dataclass(frozen=True)
class MediaGridViewModel:
    items: tuple[MediaGridItem, ...]
    density: str
    filtered_count: int
    total_count: int

    @property
    def empty(self) -> bool:
        return not self.items


def density_geometry(density: str) -> dict[str, int]:
    key = (density or DENSITY_COMFORTABLE).strip().lower()
    return dict(_DENSITY_GEOM.get(key, _DENSITY_GEOM[DENSITY_COMFORTABLE]))


def _basename(path: str | None) -> str:
    if not path:
        return "Photo"
    return Path(str(path)).name or "Photo"


def build_media_grid(
    media_rows: Sequence[dict[str, Any]] | None,
    *,
    density: str = DENSITY_COMFORTABLE,
    compare_marks: set[str] | None = None,
    total_count: int | None = None,
) -> MediaGridViewModel:
    marks = {str(m) for m in (compare_marks or ()) if m}
    dens = (density or DENSITY_COMFORTABLE).strip().lower()
    if dens not in DENSITIES:
        dens = DENSITY_COMFORTABLE
    items: list[MediaGridItem] = []
    for i, row in enumerate(media_rows or ()):
        mid = str(row.get("media_id") or "").strip()
        if not mid:
            continue
        path = str(row.get("path") or "")
        items.append(
            MediaGridItem(
                media_id=mid,
                path=path,
                label=_basename(path),
                source_type=str(row.get("source_type") or ""),
                compare_marked=mid in marks,
                index=i,
            )
        )
    n = len(items)
    return MediaGridViewModel(
        items=tuple(items),
        density=dens,
        filtered_count=n,
        total_count=int(total_count) if total_count is not None else n,
    )


def visible_index_range(
    *,
    scroll_top: float,
    viewport_h: float,
    cell: int,
    pad: int,
    label_band: int,
    cols: int,
    total: int,
    overscan_rows: int = 2,
) -> tuple[int, int]:
    """Inclusive start index, exclusive end index for viewport virtualization."""
    if total <= 0 or cols <= 0:
        return 0, 0
    row_h = cell + pad + label_band
    if row_h <= 0:
        return 0, total
    first_row = max(0, int(scroll_top // row_h) - overscan_rows)
    visible_rows = int(viewport_h // row_h) + 1 + overscan_rows * 2
    start = first_row * cols
    end = min(total, start + visible_rows * cols)
    return start, max(start, end)


def load_grid_density(store: Path | None = None) -> str:
    from semblon.ui_prefs import appearance_path

    path = appearance_path(store)
    try:
        import json

        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return DENSITY_COMFORTABLE
    if not isinstance(raw, dict):
        return DENSITY_COMFORTABLE
    dens = str(raw.get("grid_density") or "").strip().lower()
    return dens if dens in DENSITIES else DENSITY_COMFORTABLE


def save_grid_density(density: str, store: Path | None = None) -> str:
    from semblon.ui_prefs import appearance_path

    dens = (density or DENSITY_COMFORTABLE).strip().lower()
    if dens not in DENSITIES:
        dens = DENSITY_COMFORTABLE
    path = appearance_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, UnicodeError, ValueError):
        raw = {}
    raw["grid_density"] = dens
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return dens
