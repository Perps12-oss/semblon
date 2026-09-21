"""Observer honesty: import ≠ capability for Pose/OCR/CLIP."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

from semblon.observer_probes import probe_all, probe_clip, probe_ocr, probe_pose
from semblon.observers import optional_status


def _install_fake(name: str, module: types.ModuleType, monkeypatch):
    monkeypatch.setitem(sys.modules, name, module)


def test_pose_import_ok_but_not_runnable_without_solutions(monkeypatch):
    mp = types.ModuleType("mediapipe")
    mp.__version__ = "0.0-test"
    # Import succeeds; solutions.pose intentionally absent.
    _install_fake("mediapipe", mp, monkeypatch)

    rec = probe_pose()
    assert rec["import_ok"] is True
    assert rec["runnable"] is False
    assert rec["available"] is False
    assert rec["verified"] is True
    assert "solutions.pose" in rec["detail"]


def test_pose_runnable_when_solutions_pose_present(monkeypatch):
    mp = types.ModuleType("mediapipe")
    mp.__version__ = "0.10-test"
    solutions = types.ModuleType("mediapipe.solutions")
    solutions.pose = types.ModuleType("mediapipe.solutions.pose")
    mp.solutions = solutions
    _install_fake("mediapipe", mp, monkeypatch)
    _install_fake("mediapipe.solutions", solutions, monkeypatch)

    rec = probe_pose()
    assert rec["import_ok"] is True
    assert rec["runnable"] is True
    assert rec["available"] is True
    assert rec["verified"] is True


def test_ocr_import_ok_binary_missing(monkeypatch):
    fake = types.ModuleType("pytesseract")

    def _boom():
        raise OSError("tesseract not found")

    fake.get_tesseract_version = _boom
    _install_fake("pytesseract", fake, monkeypatch)

    rec = probe_ocr()
    assert rec["import_ok"] is True
    assert rec["runnable"] is False
    assert rec["available"] is False
    assert "binary" in rec["detail"].lower() or "missing" in rec["detail"].lower()


def test_clip_import_ok_without_download(monkeypatch):
    fake = types.ModuleType("open_clip")
    fake.create_model_and_transforms = MagicMock(name="create_model_and_transforms")
    _install_fake("open_clip", fake, monkeypatch)

    rec = probe_clip()
    assert rec["import_ok"] is True
    assert rec["runnable"] is True
    assert "no download" in rec["detail"].lower() or "weights not probed" in rec["detail"].lower()
    fake.create_model_and_transforms.assert_not_called()


def test_probe_all_keys():
    rec = probe_all()
    assert set(rec) == {"ocr", "clip", "pose"}
    for key in ("ocr", "clip", "pose"):
        for field in ("available", "runnable", "import_ok", "detail", "verified"):
            assert field in rec[key]


def test_optional_status_gate_off_shape_compatible(monkeypatch):
    monkeypatch.setenv("SEMBLON_GATE_OBSERVER_HONESTY", "0")
    st = optional_status()
    assert st["facekit"] is True
    assert st["appearance"] is True
    assert st["object"] is True
    assert isinstance(st["ocr"], bool)
    assert isinstance(st["clip"], bool)
    assert isinstance(st["pose"], bool)
    assert isinstance(st["notes"], dict)
    assert st["identity"] == "facekit only"
    assert "probes" not in st
    assert "object_kind" not in st


def test_optional_status_gate_on_uses_runnable(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_OBSERVER_HONESTY", raising=False)
    mp = types.ModuleType("mediapipe")
    mp.__version__ = "broken-install"
    _install_fake("mediapipe", mp, monkeypatch)

    st = optional_status()
    assert st["pose"] is False
    assert "probes" in st
    assert st["probes"]["pose"]["import_ok"] is True
    assert st["probes"]["pose"]["runnable"] is False
    assert st["object_kind"] == "contour_regions"
    assert "contour" in st["notes"]["object"].lower()
