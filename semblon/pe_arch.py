"""Portable PE COFF machine-type reader (no Windows LoadLibrary).

Used to label OpenCV .pyd/.dll arch honestly (0xaa64 = ARM64, 0x8664 = x64)
without importing or loading the binary — safe on Linux CI and when import hangs.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO

# IMAGE_FILE_MACHINE_* (subset)
PE_MACHINE_NAMES: dict[int, str] = {
    0x014C: "i386",
    0x8664: "x64",
    0xAA64: "arm64",
    0x01C4: "arm",
    0x0200: "ia64",
}


def _read_pe_machine_from_stream(f: BinaryIO) -> int:
    mz = f.read(2)
    if mz != b"MZ":
        raise ValueError("not a PE file (missing MZ)")
    f.seek(0x3C)
    pe_off_raw = f.read(4)
    if len(pe_off_raw) != 4:
        raise ValueError("truncated PE header offset")
    (pe_off,) = struct.unpack("<I", pe_off_raw)
    f.seek(pe_off)
    sig = f.read(4)
    if sig != b"PE" + bytes([0, 0]):
        raise ValueError("not a PE file (missing PE signature)")
    coff = f.read(2)
    if len(coff) != 2:
        raise ValueError("truncated COFF header")
    (machine,) = struct.unpack("<H", coff)
    return int(machine)


def pe_machine(path: str | Path) -> dict:
    """Return PE machine fields for a Windows PE binary.

    Does not load or execute the file. Works on any host that can read the bytes.
    """
    p = Path(path)
    out: dict = {
        "path": str(p),
        "exists": p.is_file(),
        "ok": False,
    }
    if not out["exists"]:
        out["error"] = "missing"
        return out
    try:
        size = p.stat().st_size
        out["bytes"] = size
        with p.open("rb") as f:
            machine = _read_pe_machine_from_stream(f)
        out["pe_machine"] = f"0x{machine:04x}"
        out["pe_machine_int"] = machine
        out["arch"] = PE_MACHINE_NAMES.get(machine, f"unknown_0x{machine:04x}")
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)
    return out


def pe_arch_label(path: str | Path) -> str | None:
    """Short arch label (x64/arm64/...) or None if unreadable."""
    rec = pe_machine(path)
    if not rec.get("ok"):
        return None
    return str(rec.get("arch"))
