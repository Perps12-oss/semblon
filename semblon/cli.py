"""Semblon CLI. 0.3: lab profile + ingest + cluster + export."""

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

    ing = sub.add_parser("ingest", help="0.2 folder stills → store")
    ing.add_argument("folder", type=Path)
    ing.add_argument("--store", required=True, type=Path)

    clu = sub.add_parser("cluster", help="0.3 DBSCAN on ok faces for a run")
    clu.add_argument("--run", required=True)
    clu.add_argument("--store", required=True, type=Path)
    clu.add_argument("--eps", type=float, default=None, help="DBSCAN eps on 1-cosine (default 0.40)")
    clu.add_argument("--min-samples", type=int, default=None)

    exp = sub.add_parser("export", help="0.3 static review.html (read-only)")
    exp.add_argument("--run", required=True)
    exp.add_argument("--store", required=True, type=Path)
    exp.add_argument("--out", required=True, type=Path)
    exp.add_argument(
        "--strong-min-intra",
        type=float,
        default=None,
        help="min_intra ≥ this → STRONG (default 0.50)",
    )

    args = p.parse_args(argv)

    if args.cmd == "lab" and args.labcmd == "profile":
        from semblon.profile import run_profile

        rec = run_profile(args.image, args.out)
        print(json.dumps({k: rec[k] for k in ("pack_id", "arch", "execution", "one_image")}, indent=2))
        print(f"wrote {args.out}", file=sys.stderr)
        return 0

    if args.cmd == "ingest":
        from semblon.ingest import ingest

        try:
            rec = ingest(args.folder, args.store)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "cluster":
        from semblon.cluster import DEFAULT_EPS, DEFAULT_MIN_SAMPLES, ClusterError, cluster_run

        kwargs = {}
        if args.eps is not None:
            kwargs["eps"] = args.eps
        else:
            kwargs["eps"] = DEFAULT_EPS
        if args.min_samples is not None:
            kwargs["min_samples"] = args.min_samples
        else:
            kwargs["min_samples"] = DEFAULT_MIN_SAMPLES
        try:
            rec = cluster_run(args.store, args.run, **kwargs)
        except ClusterError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "export":
        from semblon.export import STRONG_MIN_INTRA, ExportError, export_review

        try:
            rec = export_review(
                args.store,
                args.run,
                args.out,
                strong_min_intra=STRONG_MIN_INTRA if args.strong_min_intra is None else args.strong_min_intra,
            )
        except ExportError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
