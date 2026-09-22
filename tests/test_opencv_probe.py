"""Portable tests for OpenCV PE / timed probe (no ARM64 OpenCV required)."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from semblon.opencv_probe import (
    KNOWN_HANG_DLL,
    inspect_arm64_opencv_layout,
    inspect_opencv_binding,
    probe_opencv,
)
from semblon.pe_arch import pe_arch_label, pe_machine


def _write_minimal_pe(path: Path, machine: int) -> None:
    buf = bytearray(0x80)
    buf[0:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x40)
    buf[0x40:0x44] = b"PE" + bytes([0, 0])
    struct.pack_into("<H", buf, 0x44, machine)
    path.write_bytes(bytes(buf))


def test_pe_machine_arm64(tmp_path: Path):
    p = tmp_path / "cv2.pyd"
    _write_minimal_pe(p, 0xAA64)
    rec = pe_machine(p)
    assert rec["ok"] is True
    assert rec["pe_machine"] == "0xaa64"
    assert rec["arch"] == "arm64"
    assert pe_arch_label(p) == "arm64"


def test_pe_machine_x64(tmp_path: Path):
    p = tmp_path / "cv2.pyd"
    _write_minimal_pe(p, 0x8664)
    rec = pe_machine(p)
    assert rec["ok"] is True
    assert rec["pe_machine"] == "0x8664"
    assert rec["arch"] == "x64"


def test_pe_machine_missing(tmp_path: Path):
    rec = pe_machine(tmp_path / "nope.dll")
    assert rec["ok"] is False
    assert rec["error"] == "missing"


def test_pe_machine_not_pe(tmp_path: Path):
    p = tmp_path / "junk.bin"
    p.write_bytes(b"not a pe")
    rec = pe_machine(p)
    assert rec["ok"] is False
    assert "MZ" in rec["error"] or "PE" in rec["error"] or "not a PE" in rec["error"]


def test_inspect_opencv_binding_identity_firewall(tmp_path: Path):
    p = tmp_path / "cv2.pyd"
    _write_minimal_pe(p, 0xAA64)
    rec = inspect_opencv_binding(p)
    assert rec["ok"] is True
    assert rec["binding"]["arch"] == "arm64"
    assert rec["identity_firewall"]["semblon_consumes_this_for_s1"] is False


def test_inspect_arm64_layout_missing_paths(tmp_path: Path):
    rec = inspect_arm64_opencv_layout(
        bin_dir=tmp_path / "bin",
        pyd_path=tmp_path / "missing.pyd",
    )
    assert rec["status"] == "layout"
    assert rec["hang_dll_present"] is False
    assert rec["known_hang_dll"] == KNOWN_HANG_DLL
    assert rec["import_safe_to_try"] is False
    assert rec["identity_firewall"]["semblon_consumes_this_for_s1"] is False
    assert rec["identity_firewall"]["product_workers_default"] == 1


def test_inspect_arm64_layout_with_present_arm64_dlls(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in (
        "opencv_core500.dll",
        "opencv_geometry500.dll",
        "opencv_imgproc500.dll",
        "opencv_imgcodecs500.dll",
        "opencv_highgui500.dll",
    ):
        _write_minimal_pe(bin_dir / name, 0xAA64)
    pyd = tmp_path / "cv2.cp314-win_arm64.pyd"
    _write_minimal_pe(pyd, 0xAA64)
    rec = inspect_arm64_opencv_layout(bin_dir=bin_dir, pyd_path=pyd)
    assert rec["hang_dll_present"] is True
    assert rec["all_present_are_arm64"] is True
    assert rec["pyd"]["arch"] == "arm64"
    # Still not safe to try import — historical hang class
    assert rec["import_safe_to_try"] is False


def test_probe_opencv_timeout_fail_fast():
    fake = subprocess.TimeoutExpired(cmd=["x"], timeout=1.5)
    with mock.patch("semblon.opencv_probe.subprocess.run", side_effect=fake):
        rec = probe_opencv(timeout_s=1.5)
    assert rec["ok"] is False
    assert rec["status"] == "timeout"
    assert rec["fail_fast"] is True
    assert rec["known_hang_dll"] == KNOWN_HANG_DLL
    assert "S1" in rec["note"]


def test_probe_opencv_error_fail_fast():
    fake = mock.Mock(returncode=1, stdout="", stderr="ImportError: boom")
    with mock.patch("semblon.opencv_probe.subprocess.run", return_value=fake):
        rec = probe_opencv(timeout_s=2.0)
    assert rec["ok"] is False
    assert rec["status"] == "error"
    assert rec["fail_fast"] is True


def test_probe_opencv_ok_with_pe(tmp_path: Path):
    pyd = tmp_path / "cv2.pyd"
    _write_minimal_pe(pyd, 0x8664)
    payload = {
        "ok": True,
        "import_s": 0.01,
        "cv2": "5.0.0",
        "file": str(pyd),
        "python": "3.14.0",
        "machine": "x86_64",
    }
    fake = mock.Mock(returncode=0, stdout=json.dumps(payload) + "\n", stderr="")
    with mock.patch("semblon.opencv_probe.subprocess.run", return_value=fake):
        rec = probe_opencv(timeout_s=5.0)
    assert rec["status"] == "ok"
    assert rec["ok"] is True
    assert rec["binding"]["arch"] == "x64"
    assert rec["semblon_consumes_as_native_opencv"] is False


def test_perf_p1_tool_pe_only(tmp_path: Path):
    tool = Path(__file__).resolve().parents[1] / "tools" / "_perf_p1_load_cv2.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--pe-only",
            "--bin",
            str(tmp_path / "missing-bin"),
            "--pyd",
            str(tmp_path / "missing.pyd"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rec = json.loads(proc.stdout)
    assert rec["mode"] == "pe_only"
    assert rec["identity_firewall"]["semblon_consumes_this_for_s1"] is False


def test_perf_p1_tool_load_skipped_on_non_windows(tmp_path: Path):
    if sys.platform.startswith("win"):
        pytest.skip("Windows host — LoadLibrary path differs")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_minimal_pe(bin_dir / "opencv_core500.dll", 0xAA64)
    tool = Path(__file__).resolve().parents[1] / "tools" / "_perf_p1_load_cv2.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--bin",
            str(bin_dir),
            "--pyd",
            str(tmp_path / "no.pyd"),
            "--timeout",
            "2",
            "--stop-on-fail",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # Non-Windows: first DLL is skipped_non_windows => not ok => exit 3
    assert proc.returncode == 3
    rec = json.loads(proc.stdout[proc.stdout.index("{") :])
    assert rec["results"][0]["status"] == "skipped_non_windows"
    assert rec["identity_firewall"]["semblon_consumes_this_for_s1"] is False
