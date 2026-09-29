"""Activity workspace uses ui_widgets.Button, not a missing _button."""

from pathlib import Path


def test_activity_feature_imports_button_not_private_helper():
    text = Path("semblon/features/activity_feature.py").read_text(encoding="utf-8")
    assert "from semblon.ui_widgets import Button" in text
    assert "from semblon.ui_widgets import _button" not in text
