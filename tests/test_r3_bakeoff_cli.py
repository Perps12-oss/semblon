"""lab r3-bakeoff wires tools/r3-bakeoff without inventing PASS."""

from __future__ import annotations

import json
from pathlib import Path

from semblon.cli import main


def test_lab_r3_bakeoff_dry_run(tmp_path, capsys):
    out = tmp_path / "bake.json"
    rc = main(
        [
            "lab",
            "r3-bakeoff",
            "--toolkit",
            "dry-run",
            "--operator",
            "ci",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert out.is_file()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc.get("overall", {}).get("pass") is None
    assert len(doc.get("criteria") or []) == 6
    for c in doc["criteria"]:
        assert c.get("pass") is None


def test_lab_r3_bakeoff_rejects_electron(capsys):
    rc = main(["lab", "r3-bakeoff", "--toolkit", "Electron"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "rejected" in err.lower() or "Electron" in err
