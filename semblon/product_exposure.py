"""Product GUI exposure classification — forensic registry for consolidation.

Backend capability does not dictate navigation. Classes match
``docs/UI-EXPOSURE-MAP.md``. This module is presentation/policy only: no store
writes, no identity, no clustering.
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
        "SECONDARY",
        "semblon home — legacy Tk surface, not the application architecture",
        "home_ui.run_home_ui",
        "KEEP",
    ),
    (
        "Library",
        "CANONICAL",
        "HOME_NAV library → unified media grid",
        "home_ui._show_library / CanvasWorkspace",
        "KEEP",
    ),
    (
        "Photos (compat)",
        "SECONDARY",
        "route photos → Library photos filter",
        "product_features._page_photos",
        "KEEP",
    ),
    (
        "Videos (compat filter)",
        "SECONDARY",
        "route videos → Library videos filter",
        "product_features._page_videos",
        "KEEP",
    ),
    (
        "People",
        "CANONICAL",
        "HOME_NAV people",
        "home_ui._show_people",
        "KEEP",
    ),
    (
        "People to name (Unknown)",
        "SECONDARY",
        "route unknown / Review People / palette",
        "home_ui._show_unknown",
        "KEEP",
    ),
    (
        "Search",
        "CANONICAL",
        "top bar Search / Ctrl+F",
        "home_ui._search_person",
        "KEEP",
    ),
    (
        "Activity",
        "CANONICAL",
        "HOME_NAV activity",
        "application.activity_memory via Home Activity workspace",
        "KEEP",
    ),
    (
        "Lens / Inspect",
        "CANONICAL",
        "open media → select region → Find Similar",
        "home_ui.HomeApp._open_region_select → Application.remember_and_find_region",
        "KEEP",
    ),
    (
        "Settings",
        "CANONICAL",
        "header Settings control",
        "home_ui._show_settings",
        "KEEP",
    ),
    (
        "Ingest Pause/Resume/Cancel",
        "CANONICAL",
        "processing Home + progress chrome",
        "JobEngine owned by Application; Home and the Qt shell submit",
        "KEEP",
    ),
    (
        "Review UI",
        "SECONDARY",
        "More → Open Review / semblon review-ui",
        "review_ui.run_review_ui",
        "KEEP",
    ),
    (
        "Canvas / Explore",
        "SECONDARY",
        "More → Explore workspace / semblon canvas",
        "canvas.CanvasWorkspace",
        "DEMOTE",
    ),
    (
        "Live overlay",
        "SECONDARY",
        "More → Live… / semblon live",
        "live_overlay",
        "KEEP",
    ),
    (
        "Continuous folder watch",
        "CLI",
        "semblon watch only — Home “Add or update this folder…” is one-shot ingest",
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
        "home_ui.btn_canvas pack",
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
