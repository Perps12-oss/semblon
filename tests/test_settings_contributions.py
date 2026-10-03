"""Item 23: Settings sections are contribution records. Home still draws the page."""

from pathlib import Path

from semblon.product_surface import settings_contributions, settings_product_section_titles


def test_settings_contributions_are_the_product_sections():
    rows = settings_contributions()
    assert [s.id for s in rows] == ["library", "processing", "appearance", "about"]
    assert settings_product_section_titles() == tuple(s.title for s in rows)
    assert "SettingsRegistry" not in Path("semblon/product_surface.py").read_text(encoding="utf-8")


def test_home_reads_settings_contributions_and_builds_workspace_page():
    text = Path("semblon/home_ui.py").read_text(encoding="utf-8")
    assert "settings_contributions()" in text
    assert "def _show_settings" in text
    assert "def _build_settings_workspace" in text
    assert "def _fill_settings_body" in text
    assert '_navigate("settings")' in text
    # Settings is an in-shell route — not a dedicated Settings Toplevel.
    show = text.split("def _show_settings")[1].split("def _settings_change_library")[0]
    assert "Toplevel" not in show
    assert "_settings_win" not in text
