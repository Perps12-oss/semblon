"""ItemFlag portability for desktop list models. No FaceKit. No display."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from semblon.desktop.qtcompat import list_item_flags

MODELS_PY = Path(__file__).resolve().parents[1] / "semblon" / "desktop" / "models.py"


class _FlagEnumOld:
    ItemIsEnabled = 1
    ItemIsSelectable = 2
    NoItemFlags = 0


class _FlagEnumNew(_FlagEnumOld):
    ItemIsKeyboardFocusable = 4


def test_list_item_flags_without_keyboard_focusable():
    assert list_item_flags(_FlagEnumOld) == 1 | 2


def test_list_item_flags_with_keyboard_focusable():
    assert list_item_flags(_FlagEnumNew) == 1 | 2 | 4


def test_models_py_does_not_attribute_lookup_keyboard_focusable():
    tree = ast.parse(MODELS_PY.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "ItemIsKeyboardFocusable":
            hits.append(f"line {node.lineno}")
    assert hits == []


def test_list_item_flags_on_installed_pyside():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt

    flags = list_item_flags()
    assert flags & Qt.ItemFlag.ItemIsEnabled
    assert flags & Qt.ItemFlag.ItemIsSelectable


def test_semblon_list_model_flags_on_installed_pyside():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QModelIndex, Qt

    from semblon.desktop.models import ReviewListModel

    model = ReviewListModel()
    model.reset_rows([{"label": "c1", "kind": "cluster", "cluster_id": "c1"}])
    flags = model.flags(model.index(0, 0))
    assert flags & Qt.ItemFlag.ItemIsEnabled
    assert flags & Qt.ItemFlag.ItemIsSelectable
    assert model.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0)) == "c1"
