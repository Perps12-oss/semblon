from __future__ import annotations

from pathlib import Path

import numpy as np

from semblon.lens import describe_vlm, probe_vlm
from semblon.vlm_model import install_local_description, vlm_model_path


def test_description_install_writes_a_local_marker_and_does_not_download(tmp_path, monkeypatch):
    text = Path(vlm_model_path.__code__.co_filename).read_text(encoding="utf-8")
    assert "urlopen" not in text
    assert "urllib" not in text
    monkeypatch.delenv("SEMBLON_VLM_MODEL", raising=False)
    monkeypatch.delenv("SEMBLON_VLM", raising=False)
    monkeypatch.setattr("semblon.vlm_model.Path.home", lambda: tmp_path)
    assert vlm_model_path() is None
    assert probe_vlm() == "MISSING"
    rec = install_local_description()
    assert rec["changed"] is True
    assert rec["kind"] == "pixel-describer"
    assert Path(rec["path"]).read_text(encoding="utf-8").startswith("pixel-describer")
    assert probe_vlm() == "AVAILABLE"
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[:, :] = (20, 30, 210)
    described = describe_vlm(image)
    assert described.status == "SUCCESS"
    assert described.items[0].detail == "pixel-describer"
    again = install_local_description()
    assert again["changed"] is False
