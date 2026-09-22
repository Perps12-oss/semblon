"""Portable contracts for MSI code packaging (no Windows / WiX required)."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MSI_DIR = REPO / "packaging" / "msi"
TOOLS_MSI = REPO / "tools" / "msi"


def test_msi_source_files_present():
    assert (MSI_DIR / "Semblon.wxs").is_file()
    assert (MSI_DIR / "README.md").is_file()
    assert (MSI_DIR / "smoke-checklist.md").is_file()
    assert (TOOLS_MSI / "stage-payload.py").is_file()
    assert (TOOLS_MSI / "generate-components.py").is_file()
    assert (TOOLS_MSI / "assert-no-weights.py").is_file()
    assert (TOOLS_MSI / "build-msi.ps1").is_file()
    assert (TOOLS_MSI / "bootstrap-install.ps1").is_file()


def test_wxs_declares_per_user_and_forbids_weight_story():
    text = (MSI_DIR / "Semblon.wxs").read_text(encoding="utf-8")
    assert 'Scope="perUser"' in text
    assert "buffalo_l" in text.lower() or "weights" in text.lower()
    assert "LocalAppDataFolder" in text
    assert "INSTALLFOLDER" in text
    assert "b7988316-a8a8-5fd9-84e0-e4633ccbff43" in text  # UpgradeCode


def test_install_windows_accepts_root_param():
    text = (REPO / "tools" / "install-windows.ps1").read_text(encoding="utf-8")
    assert "$Root" in text
    assert "buffalo_l" in text
    assert "pip install -e" in text


def test_uninstall_keeps_store_by_default():
    text = (REPO / "tools" / "uninstall-windows.ps1").read_text(encoding="utf-8")
    assert "DeleteStore" in text
    assert "LOCALAPPDATA" in text
    assert "Kept user data" in text


def test_interactive_bootstraps_msi_marker():
    text = (REPO / "tools" / "semblon-interactive.ps1").read_text(encoding="utf-8")
    assert ".semblon-msi-install" in text
    assert "bootstrap-install.ps1" in text


def test_semblon_cmd_msi_bootstrap_path():
    text = (REPO / "semblon.cmd").read_text(encoding="utf-8")
    assert ".semblon-msi-install" in text
    assert "bootstrap-install.ps1" in text


def test_stage_payload_excludes_weights(tmp_path: Path):
    out = tmp_path / "payload"
    # Plant a forbidden file in a fake tree to ensure assert refuses — stage from real repo.
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOLS_MSI / "stage-payload.py"),
            "--repo",
            str(REPO),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert (out / "semblon.cmd").is_file()
    assert (out / "semblon" / "__init__.py").is_file()
    assert (out / ".semblon-msi-install").is_file()
    assert (out / "tools" / "install-windows.ps1").is_file()
    assert (out / "tools" / "msi" / "bootstrap-install.ps1").is_file()
    # No weights
    for path in out.rglob("*"):
        if path.is_file():
            rel = str(path.relative_to(out)).replace("\\", "/").lower()
            assert "buffalo_l" not in rel
            assert not rel.endswith(".onnx")
            assert ".insightface" not in rel


def test_assert_no_weights_ok_on_clean_payload(tmp_path: Path):
    out = tmp_path / "payload"
    subprocess.run(
        [
            sys.executable,
            str(TOOLS_MSI / "stage-payload.py"),
            "--repo",
            str(REPO),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    proc = subprocess.run(
        [sys.executable, str(TOOLS_MSI / "assert-no-weights.py"), str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_assert_no_weights_refuses_onnx(tmp_path: Path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "model.onnx").write_bytes(b"not-a-real-weight")
    proc = subprocess.run(
        [sys.executable, str(TOOLS_MSI / "assert-no-weights.py"), str(bad)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "REFUSED" in proc.stderr


def test_assert_no_weights_refuses_buffalo_name(tmp_path: Path):
    bad = tmp_path / "bad" / "buffalo_l"
    bad.mkdir(parents=True)
    (bad / "readme.txt").write_text("nope", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TOOLS_MSI / "assert-no-weights.py"), str(tmp_path / "bad")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2


def test_generate_components_wxs_well_formed(tmp_path: Path):
    payload = tmp_path / "payload"
    wxs_out = tmp_path / "PayloadComponents.wxs"
    subprocess.run(
        [
            sys.executable,
            str(TOOLS_MSI / "stage-payload.py"),
            "--repo",
            str(REPO),
            "--out",
            str(payload),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(TOOLS_MSI / "generate-components.py"),
            "--payload",
            str(payload),
            "--out",
            str(wxs_out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    text = wxs_out.read_text(encoding="utf-8")
    assert "ComponentGroup" in text
    assert "buffalo_l" not in text.lower() or "NEVER" in text
    # Parse as XML (default namespace)
    root = ET.fromstring(text)
    assert root.tag.endswith("Wix")
    assert "PayloadComponents" in text


def test_packaging_docs_honest_about_weights():
    packaging = (REPO / "docs" / "PACKAGING.md").read_text(encoding="utf-8")
    assert "UNAVAILABLE" in packaging
    assert "build-msi.ps1" in packaging
    assert "LOCALAPPDATA" in packaging
    licenses = (REPO / "docs" / "licenses.md").read_text(encoding="utf-8")
    assert "code MSI" in licenses.lower() or "WiX" in licenses or "packaging/msi" in licenses
    matrix = (REPO / "docs" / "COMPLETION-MATRIX.md").read_text(encoding="utf-8")
    assert "MSI code" in matrix
    assert "UNAVAILABLE" in matrix
