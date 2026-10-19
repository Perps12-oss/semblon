from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import semblon.object_pack_install as object_pack_install
from semblon.object_pack import WEIGHT_NAME, probe_nanodet_status
from semblon.object_pack_install import ObjectPackInstallError, install_object_pack


def test_probe_module_does_not_download():
    text = Path(object_pack_install.__file__).with_name("object_pack.py").read_text(encoding="utf-8")
    assert "urlopen" not in text
    assert "urllib" not in text


def test_install_object_pack_writes_pin_and_reuses_existing(monkeypatch, tmp_path):
    payload = b"nanodet-pack-bytes" + (b"\x00" * 1024)
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setitem(object_pack_install.KNOWN_SHA256, WEIGHT_NAME, digest)
    monkeypatch.setattr(
        "semblon.object_pack_install._download",
        lambda _url, dest, *, timeout_s: dest.write_bytes(payload),
    )
    rec = install_object_pack(root=tmp_path)
    assert rec["changed"] is True
    assert rec["sha256"] == digest
    assert (tmp_path / "semblon-object-pack-pin.json").is_file()
    ready, note = probe_nanodet_status(tmp_path)
    assert ready is True
    assert note is None
    rec2 = install_object_pack(root=tmp_path)
    assert rec2["changed"] is False
    assert rec2["sha256"] == digest


def test_install_object_pack_rejects_wrong_hash(monkeypatch, tmp_path):
    payload = b"bad-pack"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setitem(object_pack_install.KNOWN_SHA256, WEIGHT_NAME, "0" * len(digest))
    monkeypatch.setattr(
        "semblon.object_pack_install._download",
        lambda _url, dest, *, timeout_s: dest.write_bytes(payload),
    )
    with pytest.raises(ObjectPackInstallError):
        install_object_pack(root=tmp_path)
    assert not (tmp_path / WEIGHT_NAME).exists()
    ready, _note = probe_nanodet_status(tmp_path)
    assert ready is False
