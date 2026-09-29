"""Review group-crop callback must not touch a destroyed canvas."""

from pathlib import Path


def test_apply_group_crops_guards_destroyed_canvas():
    text = Path("semblon/review_ui.py").read_text(encoding="utf-8")
    start = text.index("def _apply_group_crops")
    body = text[start:text.index("\n    def ", start + 10)]
    assert "_group_canvas_alive" in body
    assert "winfo_exists" in text[text.index("def _group_canvas_alive"):start]
    schedule = text[text.index("def worker"):text.index("def _group_canvas_alive")]
    assert "except tk.TclError" in schedule
