"""Discover category entry stays a presentation layer over existing archive workflows."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "semblon" / "native_shell" / "qml"


def test_discover_sheet_offers_explicit_categories_without_parallel_galleries():
    sheet = (QML / "DiscoverSheet.qml").read_text(encoding="utf-8")
    table = (QML / "Table.qml").read_text(encoding="utf-8")

    for label in ("People", "Objects", "Regions", "Words in photos"):
        assert f'label: "{label}"' in sheet
    assert 'objectName: "discoverButton"' in table
    assert 'onChosen: function (category)' in table
    assert 'category === "people") shell.openPeople()' in table
    assert 'category === "regions") shell.openVisualDiscovery()' in table
    assert 'category === "objects") table.focusEntry("detail", "object")' in table
    assert 'category === "words") table.focusEntry("detail", "text")' in table

    # Discovery is a way into the existing archive, not a second gallery/model.
    host = (ROOT / "semblon" / "native_shell" / "host.py").read_text(encoding="utf-8")
    assert 'setContextProperty("archiveModel", model)' in host
    assert 'setContextProperty("peopleModel", bridge.people_model)' in host
    assert "DiscoverSheet" not in host


def test_detail_search_keeps_the_selected_category():
    light_table = (QML / "LightTable.qml").read_text(encoding="utf-8")
    assert 'function focusEntry(m, searchMode)' in light_table
    assert 'shell.setSearchMode(searchMode)' in light_table
    assert 'shell.submitCommand(t)' in light_table
    assert 'shell.setSearchMode("text")' not in light_table


def test_discovery_copy_does_not_claim_object_detection_is_always_ready():
    sheet = (QML / "DiscoverSheet.qml").read_text(encoding="utf-8")
    assert "already stored" in sheet
    assert "optional object extra" in sheet
    assert "Nothing is silently downloaded" in sheet
    assert "shell.categoryCoverageText" in sheet
    assert "shell.refreshCategoryCoverage()" in sheet
    assert 'label: "Pause"' in sheet or "Pause" in sheet
    assert "shell.resumeJob()" in sheet
    assert "Continue check" in sheet
