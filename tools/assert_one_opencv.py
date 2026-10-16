"""Fail when more than one OpenCV distribution is installed."""

from __future__ import annotations

import sys
from importlib.metadata import distributions


def main() -> int:
    names = set()
    for dist in distributions():
        label = dist.metadata.get("Name")
        if label:
            names.add(label.lower())
    extras = [name for name in ("opencv-python", "opencv-contrib-python") if name in names]
    headless = "opencv-python-headless" in names
    if extras and headless:
        print(
            "refusing mixed OpenCV installs: "
            + ", ".join(extras + ["opencv-python-headless"]),
            file=sys.stderr,
        )
        print("uninstall opencv-python so only opencv-python-headless remains", file=sys.stderr)
        return 1
    if not headless and not extras:
        print("opencv-python-headless is not installed", file=sys.stderr)
        return 1
    print("opencv ok: " + ", ".join(sorted(n for n in names if n.startswith("opencv"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
