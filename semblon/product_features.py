"""Product GUI features registered for Tk Home.

Registration is the seam for new destinations and commands. Shell loops
this registry; it must not grow a per-feature if/elif for every page.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from semblon.features.activity_feature import activity_feature
from semblon.gui_registry import Feature, FeatureRegistry, GuiCommand, NavContribution
from semblon.product_surface import (
    VERB_LABEL_ASSIGN,
    VERB_LABEL_IGNORE,
    VERB_LABEL_MERGE,
    VERB_LABEL_NAME,
    VERB_LABEL_NOTE,
    VERB_LABEL_RULE_OUT,
    VERB_LABEL_SPLIT,
)

__all__ = [
    "INSPECTOR_VERB_SPECS",
    "build_product_registry",
    "register_demo_feature",
]

# Item 22: Inspector verb buttons render from this list.
# (verb key, command id, label, HomeApp method). Mutation stays on HomeApp
# -> inspector_verbs.apply_* -> review.py. Not a second mutation path.
INSPECTOR_VERB_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("name", "inspector.verb.name", VERB_LABEL_NAME, "_inspector_name_commit"),
    ("assign", "inspector.verb.assign", VERB_LABEL_ASSIGN, "_inspector_assign"),
    ("merge", "inspector.verb.merge", VERB_LABEL_MERGE, "_inspector_merge"),
    ("split", "inspector.verb.split", VERB_LABEL_SPLIT, "_inspector_split"),
    ("rule_out", "inspector.verb.rule_out", VERB_LABEL_RULE_OUT, "_inspector_rule_out"),
    ("ignore", "inspector.verb.ignore", VERB_LABEL_IGNORE, "_inspector_ignore"),
    ("note", "inspector.verb.note", VERB_LABEL_NOTE, "_inspector_note"),
)


def _page_home(host: Any) -> None:
    """Compatibility: Home resolves to Library / onboarding."""
    host._show_library_or_onboard()


def _page_library(host: Any) -> None:
    host._show_library_or_onboard()


def _page_photos(host: Any) -> None:
    """Compatibility alias → Library photos filter."""
    host._library_filter = "photos"
    host._show_library(filter_key="photos")


def _page_videos(host: Any) -> None:
    """Compatibility alias → Library videos filter."""
    host._library_filter = "videos"
    host._show_library(filter_key="videos")


_INSPECTOR_EMPTY = (
    "Open a photo to inspect observations.",
    "Boxes are evidence. They are not people.",
)


def _page_canvas(host: Any) -> None:
    host._show_workspace_canvas(reload=True, source_types=None)
    host._set_inspector("Details", list(_INSPECTOR_EMPTY))
    host._set_inspector_collapsed(True)


def _page_lens(host: Any) -> None:
    """Lens stays a route for compatibility; open media workspace instead of a product dest."""
    # Prefer the open-media path: Library with region tools, not a separate Lens app.
    if getattr(host, "_insp_media_id", None):
        host._show_workspace_canvas(reload=False, source_types=None)
        host._set_inspector_collapsed(False)
        host._open_region_select()
        return
    host._library_filter = "all"
    host._show_library(filter_key="all")
    host._set_inspector(
        "Details",
        [
            "Open a photo in Library, then select something to look at.",
        ],
    )


def _page_people(host: Any) -> None:
    host._welcome_title.set("People")
    host._show_workspace_welcome()
    host._show_people()
    host._set_inspector_collapsed(False)


def _page_unknown(host: Any) -> None:
    host._welcome_title.set("People to name")
    host._show_workspace_welcome()
    host._show_unknown()
    host._set_inspector_collapsed(False)


def _page_settings(host: Any) -> None:
    host._show_settings()
    host._set_inspector_collapsed(True)


# --- commands (Phase 5–7) -------------------------------------------------


def _ctx_selected(context: Any) -> list[dict]:
    if context is None:
        return []
    if isinstance(context, dict):
        return list(context.get("selected") or [])
    return list(getattr(context, "selected", None) or [])


def _person_from_context(context: Any) -> dict | None:
    for it in _ctx_selected(context):
        if it.get("kind") == "person" and (it.get("person_id") or it.get("name")):
            return it
    return None


def _face_from_context(context: Any) -> dict | None:
    for it in _ctx_selected(context):
        if it.get("kind") in {"face", "unassigned"} and it.get("face_id"):
            return it
    return None


def _cmd_browse_photos(host: Any, _ctx: Any = None) -> None:
    host._navigate("library")


def _cmd_review_to_name(host: Any, _ctx: Any = None) -> None:
    host._navigate("unknown")


def _cmd_explore_canvas(host: Any, _ctx: Any = None) -> None:
    host._navigate("canvas")



def _cmd_live(host: Any, _ctx: Any = None) -> None:
    host._open_live_overlay()


def _cmd_open_settings(host: Any, _ctx: Any = None) -> None:
    host._navigate("settings")


def _cmd_select_region(host: Any, _ctx: Any = None) -> None:
    host._open_region_select()


def _cmd_ask_lens(host: Any, _ctx: Any = None) -> None:
    host._ask_with_lens()


def _cmd_ask_selection(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_ask_about_selection"):
        host._ask_about_selection()


def _ask_selection_available(host: Any, _ctx: Any = None) -> bool:
    if hasattr(host, "_selection_query_rect"):
        return host._selection_query_rect() is not None
    return False


def _ask_selection_reason(host: Any, _ctx: Any = None) -> str:
    if _ask_selection_available(host, _ctx):
        return ""
    return "Select a region on a photo first"


def _cmd_name_region(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_name_saved_region"):
        host._name_saved_region()


def _name_region_available(host: Any, _ctx: Any = None) -> bool:
    return bool(getattr(host, "_last_user_region_id", None))


def _name_region_reason(host: Any, _ctx: Any = None) -> str:
    if _name_region_available(host, _ctx):
        return ""
    return "Select and remember a region first"


def _cmd_lens_find_similar(host: Any, _ctx: Any = None) -> None:
    """Histogram region search via Application.remember_and_find_region.

    Prefers an in-canvas selection (discovery loop). Falls back to region window.
    This is not search.search_similar (embedding neighbours). Do not merge stacks.
    """
    if hasattr(host, "_find_similar_in_workspace"):
        host._find_similar_in_workspace()
        return
    if hasattr(host, "_open_region_select"):
        host._open_region_select()


def _compare_session(host: Any):
    return getattr(host, "_compare", None)


def _cmd_compare_enter(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_enter_compare"):
        host._enter_compare()


def _cmd_compare_exit(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_exit_compare"):
        host._exit_compare()


def _cmd_media_keep(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_compare_decide"):
        host._compare_decide("keep")


def _cmd_media_reject(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_compare_decide"):
        host._compare_decide("reject")


def _compare_enter_available(host: Any, _ctx: Any = None) -> bool:
    sess = _compare_session(host)
    if sess is None or sess.active:
        return False
    ok, _reason = sess.can_enter()
    return ok


def _compare_enter_reason(host: Any, _ctx: Any = None) -> str:
    sess = _compare_session(host)
    if sess is None:
        return "Compare unavailable"
    if sess.active:
        return "Already comparing"
    _ok, reason = sess.can_enter()
    return reason


def _compare_active_available(host: Any, _ctx: Any = None) -> bool:
    sess = _compare_session(host)
    return bool(sess and sess.active)


def _compare_decide_available(host: Any, _ctx: Any = None) -> bool:
    sess = _compare_session(host)
    return bool(sess and sess.active and sess.focused_id())


def _person_history_available(host: Any, context: Any = None) -> bool:
    return _person_from_context(context) is not None


def _person_history_reason(host: Any, context: Any = None) -> str:
    if _person_from_context(context) is None:
        return "Select one named person"
    return ""


def _cmd_person_history(host: Any, context: Any = None) -> None:
    from semblon.memory import history

    person = _person_from_context(context)
    if person is None:
        host._set_inspector("History", ["Select one named person."])
        return
    key = str(person.get("name") or person.get("display_name") or person.get("person_id") or "").strip()
    if not key:
        host._set_inspector("History", ["Select one named person."])
        return
    try:
        rec = history(Path(host.store), person=key)
    except Exception as e:  # noqa: BLE001 — surface soft failure
        host._set_inspector("History", [f"Could not load history: {e}"])
        return
    lines: list[str] = [str(rec.get("display_name") or key)]
    for it in list(rec.get("items") or [])[:16]:
        when = it.get("when") or it.get("date") or ""
        where = it.get("where") or it.get("folder") or it.get("place") or ""
        bit = " · ".join(p for p in (when, where) if p)
        if bit:
            lines.append(bit)
    if len(lines) == 1:
        lines.append("No dates or places recorded for this person yet.")
    host._set_inspector("History", lines)


def _identify_available(host: Any, context: Any = None) -> bool:
    return _face_from_context(context) is not None and Path(host.store).is_file()


def _identify_reason(host: Any, context: Any = None) -> str:
    if _face_from_context(context) is None:
        return "Select a face first"
    if not Path(host.store).is_file():
        return "Add photos first"
    return ""


def _cmd_identify_face(host: Any, context: Any = None) -> None:
    """Ask whether a selected face matches someone already named."""
    from semblon.identify import IdentifyError, identify_face
    from semblon.process import latest_run_id

    face = _face_from_context(context)
    if face is None:
        host._set_inspector("Identify", ["Select a face first."])
        return
    fid = str(face.get("face_id") or "")
    rid = getattr(host, "_insp_run_id", None) or latest_run_id(host.store)
    if not rid:
        host._set_inspector("Identify", ["Nothing processed yet."])
        return
    try:
        rec = identify_face(Path(host.store), rid, fid, record=False)
    except IdentifyError as e:
        host._set_inspector("Identify", [str(e)])
        return
    except Exception as e:  # noqa: BLE001
        host._set_inspector("Identify", [f"Could not identify: {e}"])
        return
    lines = ["Is this someone you already named?"]
    decision = rec.get("decision")
    name = rec.get("display_name")
    score = rec.get("score_top1")
    if name and decision in {"accept", "ACCEPT", "match", None} and score is not None:
        try:
            lines.append(f"Suggestion: {name} ({float(score):.2f})")
        except (TypeError, ValueError):
            lines.append(f"Suggestion: {name}")
    elif name:
        lines.append(f"Suggestion: {name}")
        if score is not None:
            lines.append(f"score {score}")
    else:
        lines.append("No named match yet. Unknown is valid.")
    lines.append("Suggestion only — use Name or Assign. Semblon does not auto-assign.")
    host._set_inspector("Identify", lines)


def _cmd_search_text_hint(host: Any, _ctx: Any = None) -> None:
    """Clear OCR / text-search affordance — focuses the search box."""
    try:
        host.search_var.set("")
        if hasattr(host, "_search_entry"):
            host._search_entry.focus_set()
        host._set_inspector(
            "Search",
            [
                "Type in the search box to find people by name.",
                "If no person matches, Semblon also looks for text in photos (OCR) when available.",
            ],
        )
    except Exception:  # noqa: BLE001
        pass


def _cmd_library_duplicates(host: Any, _ctx: Any = None) -> None:
    """Integrity (A) Exact + Near duplicate scan → Memory Canvas groups."""
    if hasattr(host, "_scan_duplicates"):
        host._scan_duplicates()


def _cmd_duplicates_open_selected(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_open_selected_duplicate_group"):
        host._open_selected_duplicate_group()


def _duplicates_scan_available(host: Any, _ctx: Any = None) -> bool:
    store = getattr(host, "store", None)
    return bool(store)


def _cmd_saved_regions(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_show_saved_regions"):
        host._show_saved_regions()


def _cmd_browse_timeline(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_open_browse_facet"):
        host._open_browse_facet("timeline")


def _cmd_browse_folders(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_open_browse_facet"):
        host._open_browse_facet("folders")


def _cmd_browse_moments(host: Any, _ctx: Any = None) -> None:
    if hasattr(host, "_open_browse_facet"):
        host._open_browse_facet("moments")


def _cmd_backup_library(host: Any, _ctx: Any = None) -> None:
    from tkinter import filedialog, messagebox

    from semblon.store import backup_store

    dest = filedialog.askdirectory(parent=host.root, title="Choose backup folder")
    if not dest:
        return
    try:
        out = Path(dest) / "semblon-backup.sqlite"
        rec = backup_store(Path(host.store), out)
        messagebox.showinfo(
            "Semblon",
            "Library backup saved.\n"
            f"{rec.get('out') or out}\n\n"
            "Restore stays a lab command (not this window).",
            parent=host.root,
        )
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Semblon", f"Backup failed: {e}", parent=host.root)


def _cmd_watch_folder(host: Any, _ctx: Any = None) -> None:
    """Folder update through Application. Continuous watch stays CLI."""
    from tkinter import filedialog, messagebox

    folder = filedialog.askdirectory(parent=host.root, title="Add or update this folder")
    if not folder:
        return
    try:
        if host.app.busy:
            messagebox.showinfo(
                "Semblon",
                "Ingest already running. Continuous watch: semblon watch",
                parent=host.root,
            )
            return
        # Same door as Add a photo folder.
        host._start_process(Path(folder), resume=False)
        messagebox.showinfo(
            "Semblon",
            "Semblon is scanning that folder.\n"
            "For continuous watch after this scan, use: semblon watch",
            parent=host.root,
        )
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Semblon", str(e), parent=host.root)


def _cmd_export_person_views(host: Any, _ctx: Any = None) -> None:
    from tkinter import filedialog, messagebox

    from semblon.export import export_views
    from semblon.process import latest_run_id

    dest = filedialog.askdirectory(parent=host.root, title="Export person folders")
    if not dest:
        return
    rid = latest_run_id(host.store)
    if not rid:
        messagebox.showinfo(
            "Semblon",
            "Nothing to export yet. Add a folder and name someone first.",
            parent=host.root,
        )
        return
    try:
        rec = export_views(Path(host.store), rid, Path(dest))
        views = rec.get("views") or dest
        written = rec.get("written") or rec.get("count") or rec.get("persons")
        if written == 0 or rec.get("empty"):
            messagebox.showinfo(
                "Semblon",
                "No named-person folders to write for this run.\n"
                "Originals stay put.",
                parent=host.root,
            )
            return
        messagebox.showinfo(
            "Semblon",
            f"Person folders written.\nOriginals stay put.\n{views}",
            parent=host.root,
        )
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Semblon", f"Export failed: {e}", parent=host.root)


def _inspector_verb_run(method_name: str):
    """Thin registry adapter. Does not name, merge, or assign itself."""

    def _run(host: Any, _ctx: Any = None) -> None:
        getattr(host, method_name)()

    return _run


def _inspector_verb_commands() -> tuple[GuiCommand, ...]:
    return tuple(
        GuiCommand(
            id=cmd_id,
            label=label,
            run=_inspector_verb_run(method),
            surfaces=frozenset({"inspector"}),
            requires_context=True,
        )
        for _key, cmd_id, label, method in INSPECTOR_VERB_SPECS
    )


def build_product_registry() -> FeatureRegistry:
    reg = FeatureRegistry()

    # Lens is capability/route only — not a sidebar destination.
    reg.register(
        Feature(
            id="lens",
            label="Lens",
            route_id="lens",
            page=_page_lens,
            commands=(
                GuiCommand(
                    id="lens.select_region",
                    label="Select a region",
                    run=_cmd_select_region,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                ),
                GuiCommand(
                    id="lens.find_similar",
                    label="Find Similar",
                    run=_cmd_lens_find_similar,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                ),
                GuiCommand(
                    id="lens.ask",
                    label="Ask about this photo",
                    run=_cmd_ask_lens,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                ),
                GuiCommand(
                    id="lens.ask_selection",
                    label="Ask about this selection",
                    run=_cmd_ask_selection,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                    available=_ask_selection_available,
                    reason=_ask_selection_reason,
                ),
                GuiCommand(
                    id="lens.name_region",
                    label="Name this region",
                    run=_cmd_name_region,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                    available=_name_region_available,
                    reason=_name_region_reason,
                ),
                GuiCommand(
                    id="lens.search_text",
                    label="Search text in photos",
                    run=_cmd_search_text_hint,
                    surfaces=frozenset({"palette", "overflow"}),
                ),
            ),
        )
    )

    # Discovery → Compare → Decide (contextual; not a MAIN destination).
    reg.register(
        Feature(
            id="discovery_compare",
            label="Compare",
            commands=(
                GuiCommand(
                    id="compare.enter",
                    label="Compare",
                    run=_cmd_compare_enter,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                    available=_compare_enter_available,
                    reason=_compare_enter_reason,
                ),
                GuiCommand(
                    id="compare.exit",
                    label="Leave Compare",
                    run=_cmd_compare_exit,
                    surfaces=frozenset({"inspector", "palette"}),
                    available=_compare_active_available,
                    reason=lambda _h, _c=None: "" if _compare_active_available(_h) else "Not comparing",
                ),
                GuiCommand(
                    id="media.keep",
                    label="Keep",
                    run=_cmd_media_keep,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                    available=_compare_decide_available,
                    reason=lambda _h, _c=None: (
                        "" if _compare_decide_available(_h) else "Open Compare first"
                    ),
                ),
                GuiCommand(
                    id="media.reject",
                    label="Reject",
                    run=_cmd_media_reject,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                    available=_compare_decide_available,
                    reason=lambda _h, _c=None: (
                        "" if _compare_decide_available(_h) else "Open Compare first"
                    ),
                ),
            ),
        )
    )

    reg.register(
        Feature(
            id="library",
            label="Library",
            nav=NavContribution(
                section="MAIN",
                route_id="library",
                label="Library",
                shortcut="1",
                order=0,
            ),
            route_id="library",
            page=_page_library,
            commands=(
                GuiCommand(
                    id="library.browse_photos",
                    label="Browse photos",
                    run=_cmd_browse_photos,
                    surfaces=frozenset({"overflow", "palette"}),
                ),
                GuiCommand(
                    id="library.duplicates",
                    label="Find Duplicates",
                    run=_cmd_library_duplicates,
                    surfaces=frozenset({"inspector", "palette", "overflow", "context"}),
                    available=_duplicates_scan_available,
                    reason=lambda _h, _c=None: (
                        "" if _duplicates_scan_available(_h) else "Library unavailable"
                    ),
                ),
                GuiCommand(
                    id="duplicates.open_group",
                    label="Open Duplicate Group",
                    run=_cmd_duplicates_open_selected,
                    surfaces=frozenset({"inspector", "palette"}),
                ),
                GuiCommand(
                    id="library.saved_regions",
                    label="Saved Regions",
                    run=_cmd_saved_regions,
                    surfaces=frozenset({"inspector", "palette", "overflow", "context"}),
                ),
                GuiCommand(
                    id="library.browse_timeline",
                    label="Timeline",
                    run=_cmd_browse_timeline,
                    surfaces=frozenset({"palette", "overflow"}),
                ),
                GuiCommand(
                    id="library.browse_folders",
                    label="Folders",
                    run=_cmd_browse_folders,
                    surfaces=frozenset({"palette", "overflow"}),
                ),
                GuiCommand(
                    id="library.browse_moments",
                    label="Moments",
                    run=_cmd_browse_moments,
                    surfaces=frozenset({"palette", "overflow"}),
                ),
                GuiCommand(
                    id="library.backup",
                    label="Back up library…",
                    run=_cmd_backup_library,
                    surfaces=frozenset({"overflow", "palette"}),
                ),
                GuiCommand(
                    id="library.watch_folder",
                    label="Add or update this folder…",
                    run=_cmd_watch_folder,
                    surfaces=frozenset({"overflow", "palette"}),
                ),
                GuiCommand(
                    id="library.export_person_folders",
                    label="Export person folders…",
                    run=_cmd_export_person_views,
                    surfaces=frozenset({"overflow", "palette"}),
                ),
            ),
        )
    )

    # Compatibility: old home/photos routes resolve to Library.
    reg.register(
        Feature(
            id="library_home",
            label="Library",
            route_id="home",
            page=_page_home,
        )
    )

    reg.register(
        Feature(
            id="photos_grid",
            label="Photos",
            route_id="photos",
            page=_page_photos,
        )
    )

    reg.register(
        Feature(
            id="videos",
            label="Videos",
            route_id="videos",
            page=_page_videos,
        )
    )

    reg.register(
        Feature(
            id="canvas",
            label="Explore workspace",
            route_id="canvas",
            page=_page_canvas,
            commands=(
                GuiCommand(
                    id="canvas.explore",
                    label="Explore workspace",
                    run=_cmd_explore_canvas,
                    surfaces=frozenset({"overflow", "palette"}),
                ),
            ),
        )
    )

    reg.register(
        Feature(
            id="people",
            label="People",
            nav=NavContribution(
                section="MAIN",
                route_id="people",
                label="People",
                shortcut="2",
                order=1,
            ),
            route_id="people",
            page=_page_people,
            commands=(
                GuiCommand(
                    id="person.history",
                    label="Show history",
                    run=_cmd_person_history,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                    available=_person_history_available,
                    reason=_person_history_reason,
                    requires_context=True,
                ),
                GuiCommand(
                    id="person.identify_face",
                    label="Is this someone I named?",
                    run=_cmd_identify_face,
                    surfaces=frozenset({"inspector", "palette", "context"}),
                    available=_identify_available,
                    reason=_identify_reason,
                    requires_context=True,
                ),
                GuiCommand(
                    id="person.review_to_name",
                    label="Start naming",
                    run=_cmd_review_to_name,
                    surfaces=frozenset({"palette", "overflow"}),
                ),
            ),
        )
    )

    # People to name stays a route — not a permanent sidebar row.
    reg.register(
        Feature(
            id="unknown",
            label="People to name",
            route_id="unknown",
            page=_page_unknown,
        )
    )

    reg.register(activity_feature())

    reg.register(
        Feature(
            id="settings",
            label="Settings",
            route_id="settings",
            page=_page_settings,
            commands=(
                GuiCommand(
                    id="shell.open_settings",
                    label="Settings",
                    run=_cmd_open_settings,
                    surfaces=frozenset({"palette"}),
                ),
                GuiCommand(
                    id="shell.live",
                    label="Live…",
                    run=_cmd_live,
                    surfaces=frozenset({"overflow", "palette"}),
                ),
            ),
        )
    )

    # No nav. Home renders these; it does not own the verb list.
    reg.register(
        Feature(
            id="inspector_verbs",
            label="Inspector verbs",
            commands=_inspector_verb_commands(),
        )
    )

    return reg


def register_demo_feature(registry: FeatureRegistry) -> Feature:
    """Acceptance: register without editing HomeApp / HOME_NAV / menus."""

    def _demo_page(host: Any) -> None:
        host._welcome_title.set("Registry demo")
        host._show_workspace_welcome()
        host._set_inspector(
            "Registry demo",
            [
                "This page was registered without editing HomeApp,",
                "HOME_NAV, _navigate, More, Ctrl+K, or the inspector.",
            ],
        )

    def _demo_ping(host: Any, _ctx: Any = None) -> None:
        host._set_inspector("Registry demo", ["Demo command ran."])

    feat = Feature(
        id="registry_demo",
        label="Registry demo",
        nav=NavContribution(
            section="MAIN",
            route_id="registry_demo",
            label="Registry demo",
            order=99,
        ),
        route_id="registry_demo",
        page=_demo_page,
        commands=(
            GuiCommand(
                id="registry_demo.ping",
                label="Demo ping",
                run=_demo_ping,
                surfaces=frozenset({"palette", "overflow", "inspector"}),
            ),
        ),
    )
    registry.register(feat)
    return feat
