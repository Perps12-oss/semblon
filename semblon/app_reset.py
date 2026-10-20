"""Reset Semblon application state to canonical defaults.

Clears Semblon-owned rebuildable caches and preferences beside the library
store. Never deletes original media files or user library folders.

Identity decisions, named persons, notes, saved regions, and the media index
live in store.sqlite and are PRESERVED. Erasing them is ``semblon erase``
(``semblon.erasure``), not this reset.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from semblon.ann_index import index_path
from semblon.process import default_review_out, default_store_path
from semblon.ui_prefs import appearance_path
from semblon.visual_cache import cache_dir as visual_cache_dir

log = logging.getLogger("semblon.app_reset")

# Explicit classification. YES = cleared by reset_app_to_defaults.
# NO / PRESERVE = never touched. VERIFY resolved below as PRESERVE.
RESET_MANIFEST: tuple[tuple[str, str, str], ...] = (
    ("appearance.json theme", "YES", "Canonical default = missing → system"),
    ("appearance.json grid_density", "YES", "Canonical default = comfortable"),
    ("appearance.json search_mode", "YES", "Canonical default = people"),
    ("appearance.json search_quality", "YES", "Canonical default = balanced"),
    ("appearance.json library_filter", "YES", "Canonical default = all"),
    ("appearance.json prefer_gpu", "YES", "Canonical default = unset → product_prefer_gpu()"),
    ("appearance.json (library file removed)", "YES", "All library-scoped presentation prefs"),
    ("Machine window_geometry (default Semblon dir)", "YES*", "Cleared when Reset removes that appearance.json"),
    ("Machine last_store (default Semblon dir)", "YES*", "Cleared only when Reset hits the default-dir prefs file"),
    ("visual_cache/ sidecars", "YES", "Rebuildable visual analysis cache beside store"),
    ("*.semblon-index.npz ANN sidecar", "YES", "Derived speed index; SQLite embeddings remain authoritative"),
    ("review.html beside store", "YES", "Retired artifact; delete if a leftover file is present"),
    ("home_completion schema_meta keys", "YES", "FTUE/UI completion presentation only"),
    ("In-session UI/job chrome state", "YES", "Host clears compare/filter/GPU/search/library prefs after success"),
    ("store.sqlite (media index)", "NO", "Pointers to user media; reopening library must work"),
    ("faces / persons / cluster_person", "NO", "Identity — user-authorized"),
    ("decisions (name/merge/split/note/reject)", "NO", "User-authored identity decisions"),
    ("user_region observation_items", "NO", "User-created saved regions"),
    ("embeddings / observation_items OCR text", "NO", "In-store derived; rebuild via normal ingest — not deleted to avoid hollow store"),
    ("Original photos and videos", "NO", "User-owned; never deleted"),
    ("User library folders", "NO", "User-owned; never deleted"),
    ("Model weights / InsightFace packs", "NO", "Optional capability install; not app prefs"),
    ("observatory/ golden under store parent", "NO", "Eval evidence; not product cache"),
)


@dataclass
class ResetResult:
    ok: bool
    cleared: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    restart_required: bool = False

    @property
    def message(self) -> str:
        if self.ok:
            return (
                "Semblon was reset to defaults.\n"
                "Cached and derived application data were cleared.\n"
                "Your original photos and videos were not deleted."
            )
        detail = "\n".join(self.errors) if self.errors else "Unknown failure."
        return f"Reset could not finish.\n{detail}"


class AppResetError(RuntimeError):
    """Raised when a reset step fails before prefs are restored."""


def _remove_path(path: Path, *, label: str, cleared: list[str], errors: list[str]) -> None:
    """Remove a file or directory. Missing path is success (idempotent)."""
    try:
        if not path.exists():
            cleared.append(f"{label} (already absent)")
            return
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        cleared.append(label)
        log.info("app_reset cleared %s", path)
    except OSError as exc:
        errors.append(f"{label}: {exc}")
        log.exception("app_reset failed clearing %s", path)


def _clear_home_completion_meta(store: Path, *, cleared: list[str], errors: list[str]) -> None:
    if not Path(store).is_file():
        cleared.append("home_completion meta (no store)")
        return
    try:
        from semblon.home_completion import clear_completion

        clear_completion(store)
        # Also drop ack so FTUE presentation returns to default.
        import sqlite3

        conn = sqlite3.connect(str(Path(store).resolve()))
        try:
            conn.execute("DELETE FROM schema_meta WHERE key=?", ("home_completion_ack_run",))
            conn.commit()
        finally:
            conn.close()
        cleared.append("home_completion meta")
        log.info("app_reset cleared home_completion meta")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"home_completion meta: {exc}")
        log.exception("app_reset failed clearing home_completion")


def library_root(store: Path | None = None) -> Path:
    """Directory owning Semblon sidecars for this library store."""
    lib = Path(store) if store is not None else default_store_path()
    return lib.resolve().parent


def resettable_paths(store: Path | None = None) -> dict[str, Path]:
    """Known Semblon-owned rebuildable paths for the active store."""
    lib = Path(store) if store is not None else default_store_path()
    return {
        "appearance": appearance_path(lib),
        "visual_cache": visual_cache_dir(lib),
        "ann_index": index_path(lib),
        "review_html": default_review_out(lib),
    }


def reset_app_to_defaults(store: Path | None = None) -> ResetResult:
    """Clear rebuildable Semblon state, then restore canonical prefs.

    Stage 1: clear caches / generated figures / FTUE meta.
    Stage 2: only if stage 1 has no errors — remove appearance.json
    (canonical defaults = missing file).

    Does not delete store.sqlite or any original media path.
    """
    lib = Path(store) if store is not None else default_store_path()
    cleared: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    paths = resettable_paths(lib)
    # Stage 1 — rebuildable caches / generated artifacts.
    _remove_path(paths["visual_cache"], label="visual_cache", cleared=cleared, errors=errors)
    _remove_path(paths["ann_index"], label="ann_index", cleared=cleared, errors=errors)
    _remove_path(paths["review_html"], label="review.html", cleared=cleared, errors=errors)
    _clear_home_completion_meta(lib, cleared=cleared, errors=errors)

    # Never touch the store file itself.
    if lib.is_file():
        skipped.append("store.sqlite (preserved)")
    else:
        skipped.append("store.sqlite (absent)")

    if errors:
        return ResetResult(ok=False, cleared=cleared, skipped=skipped, errors=errors)

    # Stage 2 — prefs last so a cache failure does not leave defaults applied.
    _remove_path(paths["appearance"], label="appearance.json", cleared=cleared, errors=errors)
    if errors:
        return ResetResult(ok=False, cleared=cleared, skipped=skipped, errors=errors)

    log.info("app_reset completed for library root %s", library_root(lib))
    return ResetResult(ok=True, cleared=cleared, skipped=skipped, errors=[], restart_required=False)


def assert_media_untouched(media_paths: list[Path], *, probe_bytes: dict[Path, bytes] | None = None) -> None:
    """Test helper: every path still exists; optional byte equality."""
    for path in media_paths:
        if not path.is_file():
            raise AssertionError(f"media missing after reset: {path}")
        if probe_bytes is not None and path in probe_bytes:
            if path.read_bytes() != probe_bytes[path]:
                raise AssertionError(f"media mutated after reset: {path}")
