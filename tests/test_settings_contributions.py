"""Item 23: Settings sections are contribution records. Home still draws the window."""

from pathlib import Path

from semblon.product_surface import settings_contributions, settings_product_section_titles


def test_settings_contributions_are_the_product_sections():
    rows = settings_contributions()
    assert [s.id for s in rows] == ["library", "processing", "appearance", "about"]
    assert settings_product_section_titles() == tuple(s.title for s in rows)
    assert "SettingsRegistry" not in Path("semblon/product_surface.py").read_text(encoding="utf-8")


def test_home_reads_settings_contributions_and_still_builds_the_window():
    text = Path("semblon/home_ui.py").read_text(encoding="utf-8")
    assert "settings_contributions()" in text
    assert "def _show_settings" in text
    assert "tk.Toplevel" in text
