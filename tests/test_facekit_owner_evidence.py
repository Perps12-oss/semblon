"""Owner evidence helper fails closed without a pack and does not download."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from semblon.engine import PACK_PIN_NAME, accept_local_face_pack

ROOT = Path(__file__).resolve().parents[1]


def _load_evidence_main():
    path = ROOT / "tools" / "facekit_owner_evidence.py"
    spec = importlib.util.spec_from_file_location("facekit_owner_evidence", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def test_facekit_owner_evidence_fails_closed_without_pack(tmp_path):
    main = _load_evidence_main()
    empty = tmp_path / "empty-pack"
    empty.mkdir()
    out = tmp_path / "evidence.json"
    code = main(["--pack-dir", str(empty), "--out", str(out)])
    assert code == 1
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["status"] == "FAILED"
    assert rec["error"]


def test_facekit_owner_evidence_pass_with_pin(tmp_path):
    main = _load_evidence_main()
    pack = tmp_path / "yunet_sface"
    pack.mkdir()
    (pack / "face_detection_yunet_2023mar.onnx").write_bytes(b"not-a-real-yunet")
    (pack / "face_recognition_sface_2021dec.onnx").write_bytes(b"not-a-real-sface")
    accept_local_face_pack(pack)
    assert (pack / PACK_PIN_NAME).is_file()
    out = tmp_path / "ok.json"
    code = main(["--pack-dir", str(pack), "--out", str(out)])
    assert code == 0
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["status"] == "PASS"
    assert "face_recognition_sface_2021dec.onnx" in (rec.get("pin") or {})
