"""Queue B 09–11: honest chrome labels, region-search target, live overrides."""

from __future__ import annotations

import inspect

from semblon.home_shell import capability_sections, lens_understanding_rows, probe_model_overrides
from semblon.product_features import build_product_registry, _cmd_identify_face, _cmd_lens_find_similar
from semblon.product_surface import SETTINGS_SHORTCUTS
from semblon.runtime_contract import default_catalog, status_report


def test_dashboard_and_command_labels_are_honest():
    reg = build_product_registry()
    nav = {n.route_id: n.label for n in reg.nav_contributions()}
    assert nav["library"] == "Library"
    labels = {c.id: c.label for c in reg.commands()}
    assert labels["lens.find_similar"] == "Find Similar"
    assert labels["library.watch_folder"] == "Add or update this folder…"
    assert labels["library.browse_photos"] == "Browse photos"
    assert ("Memory / Library", "Ctrl+1") in SETTINGS_SHORTCUTS
    assert ("Photos", "Ctrl+1") not in SETTINGS_SHORTCUTS


def test_catalog_vlm_and_knowledge_labels_are_honest():
    catalog = {spec.id: spec.label for spec in default_catalog().specs}
    assert catalog["vlm"] in {"Describe", "Local description (experimental)"}
    assert catalog["lkg"] in {"Knowledge", "Local pack match"}
    sections = capability_sections(has_library_content=False, model_overrides={})
    by_id = {r["id"]: r for r in sections["tracked"] + sections["ready"]}
    assert by_id["vlm"]["label"] in {"Describe", "Local description (experimental)"}
    assert by_id["lkg"]["label"] in {"Knowledge", "Local pack match"}


def test_find_similar_command_targets_region_search_not_embedding_stack():
    src = inspect.getsource(_cmd_lens_find_similar)
    assert "open_region_select" in src
    # Docstring may name the forbidden stack; the body must not call it.
    body = src.split('"""', 2)[-1] if '"""' in src else src
    assert "search.search_similar" not in body
    assert "search_similar(" not in body
    from semblon import lens_release

    rel = inspect.getsource(lens_release.remember_selection)
    assert "remember_and_find" in rel


def test_identify_command_stays_record_false_and_suggests_only():
    src = inspect.getsource(_cmd_identify_face)
    assert "record=False" in src
    assert "Suggestion only" in src
    assert "Name or Assign" in src
    assert "person_id" not in src or "faces.person_id" not in src


def test_probe_overrides_never_download_and_status_report_accepts_them():
    src = inspect.getsource(probe_model_overrides)
    assert "download" not in src.lower() or "Never download" in src
    probed = probe_model_overrides()
    assert isinstance(probed, dict)
    report = status_report(model_overrides={"ocr": "AVAILABLE"})
    ocr = next(r for r in report if r["capability_id"] == "ocr")
    assert ocr["model_state"] == "AVAILABLE"
    rows = lens_understanding_rows(model_overrides={"ocr": "AVAILABLE"})
    ocr_row = next(r for r in rows if r["id"] == "ocr")
    assert ocr_row["state"] == "Available"
