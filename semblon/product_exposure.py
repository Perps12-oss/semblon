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
        "tk Home shell",
        "CANONICAL",
        "semblon home / interactive double-click",
        "home_ui.run_home_ui",
        "KEEP",
    ),
    (
        "Photos (nav home)",
        "CANONICAL",
        "HOME_NAV home → Photos",
        "home_ui.HOME_NAV / _navigate('home')",
        "KEEP",
    ),
    (
        "Photos grid",
        "CANONICAL",
        "route photos / More → Browse photos",
        "CanvasWorkspace source_types=folder",
        "KEEP",
    ),
    (
        "Videos",
        "CANONICAL",
        "HOME_NAV videos",
        "CanvasWorkspace source_types=video",
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
        "CANONICAL",
        "HOME_NAV unknown",
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
        "application.activity via Home",
        "KEEP",
    ),
    (
        "Lens / Inspect",
        "CANONICAL",
        "ASK Lens / top Lens button",
        "home_ui._open_lens → selection.open_region_window",
        "KEEP",
    ),
    (
        "Settings",
        "CANONICAL",
        "Settings button",
        "home_ui._show_settings",
        "KEEP",
    ),
    (
        "Ingest Pause/Resume/Cancel",
        "CANONICAL",
        "processing Home + progress chrome",
        "JobEngine via Application / Home",
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
        "Live / Watch",
        "SECONDARY",
        "More → Live… / semblon live|watch",
        "live_overlay / watch",
        "KEEP",
    ),
    (
        "Qt semblon shell",
        "OPTIONAL",
        "semblon shell",
        "native_shell.run_native_shell",
        "KEEP",
    ),
    (
        "review.html product chrome",
        "STALE",
        "was: job bar / More → Open review.html",
        "home_ui._open_html",
        "DELETE_FROM_PRODUCT_CHROME",
    ),
    (
        "review.html export",
        "SUPERSEDED",
        "Settings → Advanced / export path",
        "export / process default_review_out",
        "EXPORT_ONLY",
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
    """Normal product entry — tk Home only."""
    return "semblon home"


def soft_capability_label(capability_id: str, *, catalog_label: str | None = None) -> str:
    """User-facing capability name — never provider / internal ids."""
    if catalog_label:
        return catalog_label
    # Fallback when catalog is unavailable: humanize id without leaking providers.
    return (capability_id or "Capability").replace("_", " ").strip().capitalize()
