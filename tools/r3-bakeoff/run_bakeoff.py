#!/usr/bin/env python3
"""R3 toolkit bake-off harness — measurement stubs only.

Does not choose WinUI vs Qt. Does not invent PASS. Does not enable a product default.

Usage (from repo root):

  py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit WinUI3
  py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit Qt --frametimes path\\to\\ms.txt --wcag-pairs path\\to\\pairs.json

Write human PASS/FAIL into the JSON (criteria[].pass) and the checklist after verification.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.results import (  # noqa: E402
    default_out_path,
    new_results_doc,
    utc_now_iso,
    write_results,
)
from probes import (  # noqa: E402
    c1_accent_suppress,
    c2_mica_opaque,
    c3_scrub_frametime,
    c4_wcag_aa,
    c5_virtualized_grid,
    c6_a11y_tree,
)

PROBES: list[tuple[int, Callable[[dict[str, Any]], dict[str, Any]]]] = [
    (1, c1_accent_suppress.run),
    (2, c2_mica_opaque.run),
    (3, c3_scrub_frametime.run),
    (4, c4_wcag_aa.run),
    (5, c5_virtualized_grid.run),
    (6, c6_a11y_tree.run),
]


def _apply_probe(criterion: dict[str, Any], result: dict[str, Any]) -> None:
    criterion["status"] = result["status"]
    criterion["pass"] = None  # human only
    criterion["measurements"] = result.get("measurements") or {}
    criterion["notes"] = result.get("notes") or ""
    criterion["human_steps"] = list(result.get("human_steps") or [])
    criterion["probe"] = result.get("probe") or criterion.get("probe")
    if result.get("evidence_path"):
        criterion["evidence_path"] = result["evidence_path"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="R3 §6 toolkit bake-off measurement harness")
    p.add_argument("--toolkit", default="", help="Candidate label (WinUI3, Qt/PySide6, …). Not a winner pick.")
    p.add_argument("--toolkit-version", default="", help="Toolkit / runtime version string")
    p.add_argument("--operator", default="", help="Human operator name")
    p.add_argument("--notes", default="", help="Free-form run notes")
    p.add_argument("--out", default="", help="Output JSON path (default under tools/r3-bakeoff/results/)")
    p.add_argument(
        "--frametimes",
        default="",
        help="Optional C3: text file with one frame duration ms per line",
    )
    p.add_argument(
        "--wcag-pairs",
        default="",
        help="Optional C4: JSON array of {name,theme,fg,bg,...} color pairs",
    )
    args = p.parse_args(argv)

    doc = new_results_doc(
        toolkit=args.toolkit,
        toolkit_version=args.toolkit_version,
        operator=args.operator,
        notes=args.notes,
    )
    ctx: dict[str, Any] = {
        "toolkit": args.toolkit,
        "frametimes_path": args.frametimes or None,
        "wcag_pairs_path": args.wcag_pairs or None,
    }

    by_id = {c["id"]: c for c in doc["criteria"]}
    for cid, fn in PROBES:
        _apply_probe(by_id[cid], fn(ctx))

    doc["run"]["finished_at"] = utc_now_iso()
    out = Path(args.out) if args.out else default_out_path(args.toolkit)
    write_results(out, doc)

    pending = sum(1 for c in doc["criteria"] if c["status"] == "pending_human")
    measured = sum(1 for c in doc["criteria"] if c["status"] == "measured")
    errors = sum(1 for c in doc["criteria"] if c["status"] == "error")
    print(f"Wrote {out}")
    print(f"status counts: pending_human={pending} measured={measured} error={errors}")
    print("overall.pass=null (human verification required; harness does not PASS)")
    print("Fill criteria[].pass and docs/r3-artifacts/05-bake-off-checklist.md after owner runs.")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
