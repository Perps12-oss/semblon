"""Product GUI exposure classification — forensic registry for consolidation.

Backend capability does not dictate navigation. Classes match
``docs/UI-EXPOSURE-MAP.md``. This module is presentation/policy only: no store
writes, no identity, no clustering.

2026-10-15: Tk ``home`` / ``review-ui`` / ``canvas`` clients are retired.
Rows that still name those modules are a historical inventory, not live doors.
The production GUI is ``semblon shell``.
"""

from __future__ import annotations

from typing import Literal

ExposureClass = Literal[
    "CANONICAL",
    "SECONDARY",
    "OPTIONAL",
    "CLI",
    "LAB",
    "ENGINEERING",
    "SUPERSEDED",
    "STALE",
]

# (surface, class, entry, implementation, action)
# action: KEEP | DEMOTE | MIGRATE | DELETE_FROM_PRODUCT_CHROME | EXPORT_ONLY | FORBIDDEN
GUI_PATHS: tuple[tuple[str, ExposureClass, str, str, str], ...] = (
    (
        "PySide6 archive shell",
        "CANONICAL",
        "semblon shell / interactive double-click",
        "native_shell.run_native_shell",
        "KEEP",
    ),
    (
        "tk Home shell",
        "SUPERSEDED",
        "retired: semblon home",
        "removed home_ui",
        "DELETE_FROM_PRODUCT_CHROME",
    ),
    (
        "Library",
        "CANONICAL",
        "shell archive grid + day/folder filter",
        "native_shell.ShellBridge / ArchiveModel",
        "KEEP",
    ),
    (
        "Photos (compat)",
        "SECONDARY",
        "shell mediaKind photos filter",
        "native_shell.ShellBridge.setMediaKind",
        "KEEP",
    ),
    (
        "Videos (compat filter)",
        "SECONDARY",
        "shell mediaKind videos filter",
        "native_shell.ShellBridge.setMediaKind",
        "KEEP",
    ),
    (
        "People",
        "CANONICAL",
        "shell People desk",
        "native_shell → review_board",
        "KEEP",
    ),
    (
        "People to name (Unknown)",
        "SECONDARY",
        "shell People desk unnamed groups",
        "native_shell → review_board",
        "KEEP",
    ),
    (
        "Search",
        "CANONICAL",
        "shell search field",
        "native_shell.ShellBridge.search",
        "KEEP",
    ),
    (
        "Activity",
        "CANONICAL",
        "shell Advanced → Activity sheet",
        "application.activity_memory via ShellBridge.showActivity",
        "KEEP",
    ),
    (
        "Lens / Inspect",
        "CANONICAL",
        "Focus → region drag → Find Similar",
        "native_shell.ShellBridge → Application.remember_and_find_region",
        "KEEP",
    ),
    (
        "Settings",
        "CANONICAL",
        "shell Settings",
        "native_shell settings surface",
        "KEEP",
    ),
    (
        "Ingest Pause/Resume/Cancel",
        "CANONICAL",
        "shell job band",
        "JobEngine owned by Application; shell submits",
        "KEEP",
    ),
    (
        "Review UI",
        "SUPERSEDED",
        "retired: semblon review-ui",
        "removed review_ui",
        "DELETE_FROM_PRODUCT_CHROME",
    ),
    (
        "Canvas / Explore",
        "SUPERSEDED",
        "retired: semblon canvas — overlays live in shell Focus",
        "removed canvas; canvas_data.overlay_boxes",
        "DELETE_FROM_PRODUCT_CHROME",
    ),
    (
        "Live overlay",
        "SECONDARY",
        "semblon live (CLI; off the product shell)",
        "live_overlay",
        "KEEP",
    ),
    (
        "Continuous folder watch",
        "CLI",
        "semblon watch only — shell Add folder is one-shot ingest",
        "watch.watch_folder",
        "KEEP",
    ),
    (
        "S8 toolkit spike",
        "OPTIONAL",
        "tools/s8_toolkit_spike — not the product shell",
        "tools.s8_toolkit_spike",
        "KEEP",
    ),
    (
        "review.html product chrome",
        "STALE",
        "retired: was job bar / More / Settings export page",
        "retired review.html",
        "DELETE_FROM_PRODUCT_CHROME",
    ),
    (
        "review.html export",
        "STALE",
        "retired: process no longer writes review.html",
        "retired export_review",
        "DELETE_FROM_PRODUCT_CHROME",
    ),
    (
        "Job-bar Canvas primary",
        "STALE",
        "was: equal-weight Canvas on job bar",
        "retired Tk job bar",
        "DELETE_FROM_PRODUCT_CHROME",
    ),
    (
        "CLI pipeline / corrections",
        "CLI",
        "semblon process|name|merge|…",
        "cli.py",
        "KEEP",
    ),
    (
        "lab *",
        "LAB",
        "semblon lab …",
        "cli.py lab subparsers",
        "KEEP",
    ),
    (
        "Advanced diagnostics",
        "ENGINEERING",
        "Settings → Advanced diagnostics…",
        "advanced_diagnostics",
        "KEEP",
    ),
    (
        "Electron / Tauri / FastAPI / CustomTkinter shell",
        "SUPERSEDED",
        "forbidden product shells",
        "n/a",
        "FORBIDDEN",
    ),
)


def paths_by_class(exposure: ExposureClass) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (name, entry, impl, action)
        for name, cls, entry, impl, action in GUI_PATHS
        if cls == exposure
    )


def product_chrome_forbidden_labels() -> frozenset[str]:
    """Labels that must not appear as equal-weight Home product chrome."""
    return frozenset(
        {
            "Open review.html",
            "review.html",
            "JobEngine",
            "buffalo_l",
            "FaceKit",
            "AppShell",
            "observatory",
            "vector DB",
            "ANN",
            "embed_siglip",
            "ground_selection",
            "describe_vlm",
        }
    )


def canonical_product_entry() -> str:
    """Forward product entry — PySide6 archive shell."""
    return "semblon shell"


def soft_capability_label(capability_id: str, *, catalog_label: str | None = None) -> str:
    """User-facing capability name — never provider / internal ids."""
    if catalog_label:
        return catalog_label
    # Fallback when catalog is unavailable: humanize id without leaking providers.
    return (capability_id or "Capability").replace("_", " ").strip().capitalize()
