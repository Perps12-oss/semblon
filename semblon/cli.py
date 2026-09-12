"""FACE-000 CLI: lab profile only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="semblon")
    sub = p.add_subparsers(dest="cmd", required=True)

    lab = sub.add_parser("lab")
    lab_sub = lab.add_subparsers(dest="labcmd", required=True)
    prof = lab_sub.add_parser("profile", help="FACE-000 runtime probe")
    prof.add_argument("--image", required=True, type=Path)
    prof.add_argument("--out", type=Path, default=Path("docs/runtime.md"))

    args = p.parse_args(argv)
    if args.cmd == "lab" and args.labcmd == "profile":
        from semblon.profile import run_profile

        rec = run_profile(args.image, args.out)
        print(json.dumps({k: rec[k] for k in ("pack_id", "arch", "execution", "one_image")}, indent=2))
        print(f"wrote {args.out}", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
