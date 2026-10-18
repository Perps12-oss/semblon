"""Explicit, integrity-checked fetch of the region-encoder ONNX.

Semblon never downloads this at query time. Run this once, then search offline.

    py -3 tools/fetch_region_pack.py

Writes ``%USERPROFILE%\\.semblon\\models\\region\\`` (or ``SEMBLON_REGION_PACK``).
Refuses to install if the bytes do not match the pinned SHA-256.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from semblon.region_encoder import (  # noqa: E402
    KNOWN_SHA256,
    PIN_NAME,
    SOURCE_COMMIT,
    SOURCE_URL,
    WEIGHT_NAME,
    region_pack_dir,
    write_pin,
)

_EXPECTED = KNOWN_SHA256[WEIGHT_NAME]


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    if tmp.exists():
        tmp.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "semblon-region-pack-fetch"})
    with urllib.request.urlopen(request, timeout=120) as response, tmp.open("wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


def main() -> int:
    home = region_pack_dir()
    dest = home / WEIGHT_NAME
    print(f"source {SOURCE_URL}")
    print(f"commit {SOURCE_COMMIT}")
    print(f"dest {dest}")
    if dest.is_file():
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if digest == _EXPECTED:
            write_pin(home, digest)
            print(f"already installed sha256={digest}")
            return 0
        print(f"replacing file with unexpected sha256={digest}")
        dest.unlink()
    _download(SOURCE_URL, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != _EXPECTED:
        dest.unlink(missing_ok=True)
        print(f"REFUSED sha256={digest} expected={_EXPECTED}", file=sys.stderr)
        return 2
    write_pin(home, digest)
    print(f"installed {dest.stat().st_size} bytes sha256={digest}")
    print(f"pin {home / PIN_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
