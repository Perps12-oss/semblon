"""Item 22: Inspector verbs are registry commands, rendered by Home."""

from __future__ import annotations

from pathlib import Path

from semblon.product_features import INSPECTOR_VERB_SPECS, build_product_registry
from semblon.product_surface import (
    VERB_LABEL_ASSIGN,
    VERB_LABEL_IGNORE,
    VERB_LABEL_MERGE,
    VERB_LABEL_NAME,
    VERB_LABEL_RULE_OUT,
    VERB_LABEL_SPLIT,
)


def test_inspector_verbs_registered_on_inspector_only():
    reg = build_product_registry()
    cmds = {c.id: c for c in reg.commands(surface="inspector")}
    expected = {
        "inspector.verb.name": VERB_LABEL_NAME,
        "inspector.verb.assign": VERB_LABEL_ASSIGN,
        "inspector.verb.merge": VERB_LABEL_MERGE,
        "inspector.verb.split": VERB_LABEL_SPLIT,
        "inspector.verb.rule_out": VERB_LABEL_RULE_OUT,
        "inspector.verb.ignore": VERB_LABEL_IGNORE,
    }
    assert [spec[1] for spec in INSPECTOR_VERB_SPECS] == list(expected)
    for cmd_id, label in expected.items():
        assert cmds[cmd_id].label == label
        assert cmds[cmd_id].surfaces == frozenset({"inspector"})
        assert cmds[cmd_id].requires_context is True
    palette = {c.id for c in reg.commands(surface="palette")}
    assert not palette & set(expected)


def test_verb_command_dispatches_to_existing_home_method():
    reg = build_product_registry()
    calls: list[str] = []

    class Host:
        def _inspector_merge(self) -> None:
            calls.append("merge")

        def _inspector_name_commit(self) -> None:
            calls.append("name")

    reg.get_command("inspector.verb.merge").execute(Host(), {"selected": []})
    reg.get_command("inspector.verb.name").execute(Host(), None)
    assert calls == ["merge", "name"]


def test_home_ui_renders_verbs_from_registry_not_literals():
    text = Path("semblon/home_ui.py").read_text(encoding="utf-8")
    assert "INSPECTOR_VERB_SPECS" in text
    assert "self._run_inspector_verb" in text
    assert "self.btn_name = _button(" not in text
    assert "self.btn_merge = _button(" not in text
    assert "self.btn_rule_out = _button(" not in text
    assert "self._name_entry" in text
