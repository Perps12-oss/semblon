"""Explicit install of the pinned region-encoder ONNX.

Semblon never downloads this at query time. Run this once, then search offline.

    py -3 tools/fetch_region_pack.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from semblon.region_pack_install import (
    RegionPackInstallError,
    install_region_pack,
)


def main() -> int:
    try:
        rec = install_region_pack()
    except RegionPackInstallError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"source {rec.get('source')}")
    print(f"commit {rec.get('commit')}")
    print(f"dest {rec.get('path')}")
    if rec.get("changed"):
        print(f"installed {rec.get('bytes')} bytes sha256={rec.get('sha256')}")
    else:
        print(f"already installed sha256={rec.get('sha256')}")
    print(f"pin {rec.get('pin')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
