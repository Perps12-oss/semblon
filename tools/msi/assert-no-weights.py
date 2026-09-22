#!/usr/bin/env python3
"""Refuse MSI stage/build if buffalo_l or ONNX weight artifacts are present."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FORBIDDEN_RE = re.compile(
    r"(buffalo_l|\.insightface|antelopev2|w600k_r50|\.onnx$)",
    re.IGNORECASE,
)


def scan(root: Path) -> list[str]:
    hits: list[str] = []
    if not root.exists():
        return hits
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        if FORBIDDEN_RE.search(rel):
            hits.append(rel)
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Directories to scan (default: packaging/msi/payload)",
    )
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    paths = args.paths or [repo / "packaging" / "msi" / "payload"]
    all_hits: list[str] = []
    for p in paths:
        all_hits.extend(f"{p}: {h}" for h in scan(p.resolve()))
    if all_hits:
        print("REFUSED: weight/cache artifacts must not ship in MSI:", file=sys.stderr)
        for h in all_hits:
            print(f"  {h}", file=sys.stderr)
        print("buffalo_l redistribution is UNAVAILABLE — docs/licenses.md", file=sys.stderr)
        return 2
    print("assert-no-weights: OK (no buffalo_l / .onnx in scanned paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
