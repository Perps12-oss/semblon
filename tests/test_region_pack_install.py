from __future__ import annotations

import hashlib

import pytest

import semblon.region_pack_install as region_pack_install
from semblon.region_pack_install import RegionPackInstallError, install_region_pack


def test_install_region_pack_writes_pin_and_reuses_existing(monkeypatch, tmp_path):
    payload = b"region-pack-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setitem(
        region_pack_install.KNOWN_SHA256,
        region_pack_install.WEIGHT_NAME,
        digest,
    )
    monkeypatch.setattr(
        "semblon.region_pack_install._download",
        lambda _url, dest, *, timeout_s: dest.write_bytes(payload),
    )
    rec = install_region_pack(root=tmp_path)
    assert rec["changed"] is True
    assert rec["sha256"] == digest
    assert (tmp_path / "semblon-region-pack-pin.json").is_file()
    rec2 = install_region_pack(root=tmp_path)
    assert rec2["changed"] is False
    assert rec2["sha256"] == digest


def test_install_region_pack_rejects_wrong_hash(monkeypatch, tmp_path):
    payload = b"bad-pack"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setitem(
        region_pack_install.KNOWN_SHA256,
        region_pack_install.WEIGHT_NAME,
        "0" * len(digest),
    )
    monkeypatch.setattr(
        "semblon.region_pack_install._download",
        lambda _url, dest, *, timeout_s: dest.write_bytes(payload),
    )
    with pytest.raises(RegionPackInstallError):
        install_region_pack(root=tmp_path)
    assert not (tmp_path / "dinov2-vits14.onnx").exists()

