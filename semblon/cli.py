"""Semblon CLI. 0.4: lab + ingest + cluster + export + name/merge/split.

Observatory is not a dump gate. cluster → review → person → name.
"""

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

    obs = lab_sub.add_parser("observatory", help="measurement spine — not a development gate")
    obs_sub = obs.add_subparsers(dest="obscmd", required=True)

    def _obs_io(sp):
        sp.add_argument("--store", required=True, type=Path)
        sp.add_argument("--run", required=True)

    snap = obs_sub.add_parser("snapshot", help="print a board from a run (read-only)")
    _obs_io(snap)

    frz = obs_sub.add_parser("freeze", help="write golden-{stage}.json beside the store")
    _obs_io(frz)
    frz.add_argument("--stage", required=True)
    frz.add_argument("--out", type=Path, default=None)
    frz.add_argument(
        "--notes",
        default=None,
        help="human review sentence stored on the golden (S1 dump gate, etc.)",
    )

    cmp_ = obs_sub.add_parser("compare", help="compare a run to a golden file")
    _obs_io(cmp_)
    cmp_.add_argument("--against", required=True, type=Path)

    ent = obs_sub.add_parser(
        "enter",
        help="auto-check completed-stage golden when starting a new stage",
    )
    _obs_io(ent)
    ent.add_argument("--stage", required=True, help="stage being entered, e.g. S3")
    ent.add_argument(
        "--promote",
        action="store_true",
        help="exit 3 on unexplained regression (maturity claim only)",
    )

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

    nam = sub.add_parser("name", help="0.4 name a reviewed cluster → person (not cluster=person)")
    nam.add_argument("--cluster", required=True)
    nam.add_argument("--as", dest="display_name", required=True, help="display name")
    nam.add_argument("--run", required=True)
    nam.add_argument("--store", required=True, type=Path)

    mer = sub.add_parser("merge", help="0.4 merge clusters into the first id (correction)")
    mer.add_argument(
        "--clusters",
        nargs="+",
        required=True,
        help="survivor first, then donors",
    )
    mer.add_argument("--run", required=True)
    mer.add_argument("--store", required=True, type=Path)

    spl = sub.add_parser("split", help="0.4 move faces into a new cluster")
    spl.add_argument("--cluster", required=True)
    spl.add_argument("--faces", nargs="+", required=True)
    spl.add_argument("--run", required=True)
    spl.add_argument("--store", required=True, type=Path)

    args = p.parse_args(argv)

    if args.cmd == "lab" and args.labcmd == "profile":
        from semblon.profile import ProfileError, run_profile

        try:
            rec = run_profile(args.image, args.out)
        except ProfileError as e:
            print(str(e), file=sys.stderr)
            return 2
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps({k: rec[k] for k in ("pack_id", "arch", "execution", "one_image")}, indent=2))
        print(f"wrote {args.out}", file=sys.stderr)
        return 0

    if args.cmd == "lab" and args.labcmd == "observatory":
        from semblon.observatory import ObservatoryError, compare_run, enter_stage, freeze, snapshot

        try:
            if args.obscmd == "snapshot":
                rec = snapshot(args.store, args.run)
            elif args.obscmd == "freeze":
                rec = freeze(
                    args.store,
                    args.run,
                    args.stage,
                    out=args.out,
                    notes=args.notes,
                )
            elif args.obscmd == "compare":
                rec = compare_run(args.store, args.run, args.against)
            else:
                rec = enter_stage(args.store, args.run, args.stage, promote=args.promote)
        except ObservatoryError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2, default=str))
        if args.obscmd == "enter" and args.promote and rec.get("verdict") == "regression":
            print("unexplained regression — not mature", file=sys.stderr)
            return 3
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

    if args.cmd == "name":
        from semblon.review import ReviewError, name_cluster

        try:
            rec = name_cluster(args.store, args.run, args.cluster, args.display_name)
        except ReviewError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "merge":
        from semblon.review import ReviewError, merge_clusters

        try:
            rec = merge_clusters(args.store, args.run, args.clusters)
        except ReviewError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "split":
        from semblon.review import ReviewError, split_cluster

        try:
            rec = split_cluster(args.store, args.run, args.cluster, args.faces)
        except ReviewError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
