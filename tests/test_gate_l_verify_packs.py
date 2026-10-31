"""tools/msi/gate_l_verify_packs.py — BYO hash evidence (not L PASS)."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


def _mod():
    path = Path(__file__).resolve().parents[1] / "tools" / "msi" / "gate_l_verify_packs.py"
    spec = importlib.util.spec_from_file_location("gate_l_verify_packs", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_gate_l_verify_missing_fails(tmp_path):
    mod = _mod()
    out = tmp_path / "out.md"
    assert mod.run_gate(tmp_path, out) is False
    text = out.read_text(encoding="utf-8")
    assert "FILE MISSING" in text
    assert "does **not** mark Gate L PASS" in text


def test_gate_l_verify_hash_match(tmp_path, monkeypatch):
    mod = _mod()
    packs = tmp_path / "models"
    fixture = []
    for pack in mod.PACK_GATE_MANIFEST:
        entry = dict(pack)
        folder = packs / entry["rel_dirs"][0]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / entry["filename"]
        blob = f"fixture-{entry['pack_name']}".encode()
        path.write_bytes(blob)
        entry["expected_sha256"] = hashlib.sha256(blob).hexdigest()
        fixture.append(entry)
    monkeypatch.setattr(mod, "PACK_GATE_MANIFEST", fixture)
    out = tmp_path / "ok.md"
    assert mod.run_gate(packs, out) is True
    assert "HASH MATCH" in out.read_text(encoding="utf-8")
