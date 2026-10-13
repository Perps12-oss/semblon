"""Five-repo synthesis completion wiring checks."""

from __future__ import annotations

import inspect

from semblon.context_menu import build_context_menu
from semblon.duplicates import find_integrity_groups, similarity_basis_label
from semblon.product_features import build_product_registry
from semblon.ui_primitives import SEARCH_MODES, search_mode_label


def test_search_modes_and_labels():
    keys = [k for k, _ in SEARCH_MODES]
    assert keys == ["people", "text", "whole", "region"]
    assert search_mode_label("similar") == "Whole image"
    assert search_mode_label("region") == "Region"


def test_abc_labels_never_collapse():
    assert "SHA-256" in similarity_basis_label("exact")
    assert "aHash" in similarity_basis_label("near") or "dHash" in similarity_basis_label("near")
    assert "Whole" in similarity_basis_label("whole")
    assert "region" in similarity_basis_label("region").lower()


def test_registry_exposes_browse_and_regions():
    reg = build_product_registry()
    ids = {c.id for c in reg.commands()}
    assert "library.saved_regions" in ids
    assert "library.browse_timeline" in ids
    assert "library.browse_folders" in ids
    assert "library.browse_moments" in ids
    ctx = {c.id for c in reg.commands(surface="context")}
    assert "library.duplicates" in ctx or "lens.find_similar" in ctx


def test_home_methods_exist():
    import semblon.home_ui as home_ui

    for name in (
        "_open_browse_facet",
        "_run_unified_search",
        "_search_whole_image",
        "_show_saved_regions",
        "_on_library_context_menu",
        "_set_grid_density",
        "_set_search_mode",
    ):
        assert callable(getattr(home_ui.HomeApp, name))


def test_find_similar_not_search_similar_firewall():
    import semblon.product_features as pf

    src = inspect.getsource(pf._cmd_lens_find_similar)
    # Docstring may mention the forbidden stack; the body must not call it.
    body = src.split('"""', 2)[-1] if '"""' in src else src
    assert "search_similar(" not in body
    assert "from semblon.search" not in body
    assert "_find_similar" in src


def test_integrity_groups_shape(tmp_path):
    store = tmp_path / "missing.sqlite"
    rec = find_integrity_groups(store)
    assert "exact" in rec and "near" in rec
    assert rec["kind"] == "integrity"


def test_context_menu_builder_tolerates_empty_host():
    assert build_context_menu(None, None) is None
