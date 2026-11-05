"""INVENTORY.md must cover C1–C9 with required fields and adoption board."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs" / "brain" / "INVENTORY.md"

REQUIRED_CAPS = [f"C{i}" for i in range(1, 10)]
REQUIRED_FIELDS = (
    "Existing provider",
    "Input / output",
    "Embedding pack",
    "Latency (p50/p95)",
    "Coverage",
    "Quality signal",
    "Reusable?",
    "Inc 1 adoption",
)


def test_inventory_file_exists():
    assert INVENTORY.is_file()


def test_inventory_covers_c1_through_c9():
    text = INVENTORY.read_text(encoding="utf-8")
    for cap in REQUIRED_CAPS:
        assert re.search(rf"## {cap}\b", text), f"missing section {cap}"


def test_inventory_sections_have_required_fields():
    text = INVENTORY.read_text(encoding="utf-8")
    parts = re.split(r"(?=## C\d)", text)
    sections = [p for p in parts if p.startswith("## C")]
    assert len(sections) == 9
    for section in sections:
        for field in REQUIRED_FIELDS:
            assert field in section, f"{section[:20]}… missing {field}"


def test_inventory_adoption_board_zero_new_models():
    text = INVENTORY.read_text(encoding="utf-8")
    assert "count = **0**" in text
    assert "Inc 1 outcome" in text
    assert "zero" in text.lower() or "adopted=1" in text
    for cap in REQUIRED_CAPS:
        assert f"| {cap} |" in text


def test_inventory_marks_unmeasured_honestly():
    text = INVENTORY.read_text(encoding="utf-8")
    assert "UNMEASURED" in text


def test_policy_has_no_faiss():
    policy = (ROOT / "docs" / "brain" / "policy.yaml").read_text(encoding="utf-8")
    assert "faiss" not in policy.lower()
    assert "existing_index" in policy
    assert "embedding_then_cluster" in policy
