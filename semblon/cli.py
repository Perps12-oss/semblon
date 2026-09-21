"""Semblon CLI. lab + ingest + cluster + export + review + name/merge/split + identify + inbox + stats + report + memory.

Observatory is not a dump gate. cluster -> review -> person -> name.
FACE-002: lab eval. Precision only on frozen confirmatory sets.
FACE-004: identify vs persons, never clusters. Unknown is valid.
FACE-005: incremental ingest + inbox. No watcher.
S6: memory history / together / events. Time/place are not identity.
process: happy-path ingest -> cluster -> export review.html.
home: double-click opens tk Home (JobEngine ingest + Review Toplevel).
review-ui: tkinter review vertical (Name/Merge/Split/Ignore/Note).
S7a: video files in the ingest folder are sampled (not every frame).
S7b: tracks --run is derived IoU+time association (not identity, not written).
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

    obs = lab_sub.add_parser("observatory", help="measurement spine - not a development gate")
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

    bak = lab_sub.add_parser("backup", help="copy the SQLite store (WAL-aware; does not write the source)")
    bak.add_argument("--store", required=True, type=Path)
    bak.add_argument("--out", required=True, type=Path)
    rst = lab_sub.add_parser("restore", help="restore a store backup; refuses to overwrite unless --force")
    rst.add_argument("--from", dest="backup_from", required=True, type=Path)
    rst.add_argument("--store", required=True, type=Path)
    rst.add_argument("--force", action="store_true")
    integ = lab_sub.add_parser("integrity", help="read-only store integrity report")
    integ.add_argument("--store", required=True, type=Path)
    mods = lab_sub.add_parser("models", help="report local buffalo_l weights (does not download)")
    lab_sub.add_parser("providers", help="list observation providers and availability")
    gates_p = lab_sub.add_parser(
        "gates",
        help="code-ahead gate registry status (read-only; all defaults OFF until human VERIFY)",
    )
    gates_p.add_argument(
        "--gate",
        action="append",
        dest="gate_keys",
        default=None,
        help="optional gate key filter (repeatable)",
    )
    oc = lab_sub.add_parser("opencv", help="timed OpenCV import probe (does not hang the suite)")
    oc.add_argument("--timeout", type=float, default=8.0)

    ev = lab_sub.add_parser("eval", help="FACE-002 confirmatory eval harness")
    ev_sub = ev.add_subparsers(dest="evalcmd", required=True)

    ev_c = ev_sub.add_parser("create", help="create an eval set (unfrozen)")
    ev_c.add_argument("--store", required=True, type=Path)
    ev_c.add_argument("--eval-set", required=True)
    ev_c.add_argument(
        "--kind",
        required=True,
        choices=("confirmatory_hard", "mined_discovery", "soft_impostor", "genuine"),
    )
    ev_c.add_argument("--pack", default=None)
    ev_c.add_argument("--notes", default=None)

    ev_p = ev_sub.add_parser("pair", help="add a labeled pair (refused if frozen)")
    ev_p.add_argument("--store", required=True, type=Path)
    ev_p.add_argument("--eval-set", required=True)
    ev_p.add_argument("--faces", nargs=2, required=True, metavar="FACE")
    ev_p.add_argument("--label", required=True, choices=("same", "different"))
    ev_p.add_argument("--stratum", required=True)

    ev_f = ev_sub.add_parser("freeze", help="freeze a set (confirmatory becomes immutable)")
    ev_f.add_argument("--store", required=True, type=Path)
    ev_f.add_argument("--eval-set", required=True)

    ev_m = ev_sub.add_parser("mine", help="remine discovery tail - never confirmatory")
    ev_m.add_argument("--store", required=True, type=Path)
    ev_m.add_argument("--run", required=True)
    ev_m.add_argument("--eval-set", required=True)
    ev_m.add_argument("--min-sim", type=float, default=None)
    ev_m.add_argument("--max-pairs", type=int, default=None)

    ev_s = ev_sub.add_parser(
        "score",
        help="score a set; FAR/FRR only for --eval-set confirmatory (frozen)",
    )
    ev_s.add_argument("--store", required=True, type=Path)
    ev_s.add_argument(
        "--eval-set",
        required=True,
        help="set id, or 'confirmatory' for the single frozen confirmatory_hard set",
    )
    ev_s.add_argument("--threshold", type=float, default=None)

    ing = sub.add_parser(
        "ingest",
        help="FACE-005 folder stills + S7a sampled video -> store (incremental by default)",
    )
    ing.add_argument("folder", type=Path)
    ing.add_argument("--store", required=True, type=Path)
    ing.add_argument(
        "--reprocess",
        action="store_true",
        help="re-embed hashes already in the store (default skips them)",
    )
    ing.add_argument(
        "--workers",
        type=int,
        default=1,
        help="experimental bounded hash workers (default 1; single FaceAnalysis; single SQLite writer)",
    )
    ing.add_argument(
        "--observers",
        default="face",
        help="comma list: face,color,object,text,clip,pose (face is identity; extras never vote)",
    )
    ing.add_argument("--prefer-gpu", action="store_true", help="use GPU EP if available; recorded honestly")
    ing.add_argument(
        "--resume-run",
        default=None,
        help="continue a cancelled/interrupted ingest on this run_id (same-run skip)",
    )

    proc = sub.add_parser(
        "process",
        help="happy path: ingest -> cluster -> review.html (owns run_id for you)",
    )
    proc.add_argument("folder", type=Path)
    proc.add_argument(
        "--store",
        default=None,
        type=Path,
        help="SQLite store (default: %%LOCALAPPDATA%%\\Semblon\\store.sqlite)",
    )
    proc.add_argument(
        "--out",
        default=None,
        type=Path,
        help="review.html path (default: beside the store)",
    )
    proc.add_argument(
        "--reprocess",
        action="store_true",
        help="re-embed hashes already in the store (default skips them)",
    )
    proc.add_argument(
        "--no-open",
        action="store_true",
        help="do not open review.html automatically",
    )
    proc.add_argument("--workers", type=int, default=1)
    proc.add_argument("--observers", default="face")
    proc.add_argument("--prefer-gpu", action="store_true")
    proc.add_argument(
        "--resume",
        action="store_true",
        help="continue the latest unfinished process for this folder from the next stage",
    )

    clu = sub.add_parser("cluster", help="DBSCAN on ok faces for a run")
    clu.add_argument("--run", required=True)
    clu.add_argument("--store", required=True, type=Path)
    clu.add_argument("--eps", type=float, default=None, help="DBSCAN eps on 1-cosine (default 0.40)")
    clu.add_argument("--min-samples", type=int, default=None)

    exp = sub.add_parser("export", help="review.html and/or person view folders")
    exp.add_argument("--run", required=True)
    exp.add_argument("--store", required=True, type=Path)
    exp.add_argument("--out", default=None, type=Path, help="review.html")
    exp.add_argument("--views", default=None, type=Path, help="person view folders; originals stay put")
    exp.add_argument(
        "--strong-min-intra",
        type=float,
        default=None,
        help="min_intra >= this -> STRONG (default 0.50)",
    )

    nam = sub.add_parser("name", help="FACE-005 name a cluster, face, or derived track -> person")
    nam.add_argument("--cluster", default=None)
    nam.add_argument("--face", default=None, help="unassigned inbox face (not a clustered face)")
    nam.add_argument("--track", default=None, help="derived S7 track id (not a person id)")
    nam.add_argument("--faces", nargs="+", default=None, help="unassigned face ids (one person)")
    nam.add_argument("--as", dest="display_name", required=True, help="display name")
    nam.add_argument(
        "--attach-to",
        default=None,
        dest="attach_to",
        help="existing person_id to attach (default: create a new person; no silent name reuse)",
    )
    nam.add_argument("--run", required=True)
    nam.add_argument("--store", required=True, type=Path)

    mer = sub.add_parser("merge", help="merge clusters into the first id (correction)")
    mer.add_argument(
        "--clusters",
        nargs="+",
        required=True,
        help="survivor first, then donors",
    )
    mer.add_argument("--run", required=True)
    mer.add_argument("--store", required=True, type=Path)

    spl = sub.add_parser("split", help="move faces into a new cluster")
    spl.add_argument("--cluster", required=True)
    spl.add_argument("--faces", nargs="+", required=True)
    spl.add_argument("--run", required=True)
    spl.add_argument("--store", required=True, type=Path)

    ident = sub.add_parser("identify", help="1.0/FACE-005 1:N vs reviewed persons (not clusters)")
    ident.add_argument("--run", required=True)
    ident.add_argument("--store", required=True, type=Path)
    ident.add_argument("--face", default=None, help="existing face_id on this run")
    ident.add_argument("--image", default=None, type=Path, help="new still; not enrolled")
    ident.add_argument("--threshold", type=float, default=None)

    box = sub.add_parser("inbox", help="FACE-005 KNOWN/UNKNOWN/REVIEW_REQUIRED/REJECTED")
    box.add_argument("--run", required=True)
    box.add_argument("--store", required=True, type=Path)
    box.add_argument("--threshold", type=float, default=None)

    st = sub.add_parser("stats", help="read-only run counts (does not write the store)")
    st.add_argument("--run", required=True)
    st.add_argument("--store", required=True, type=Path)

    rp = sub.add_parser("report", help="read-only markdown; writes --out only")
    rp.add_argument("--run", required=True)
    rp.add_argument("--store", required=True, type=Path)
    rp.add_argument("--out", required=True, type=Path)

    mem = sub.add_parser("memory", help="S6 visual memory (when/where/with whom); not identity")
    mem_sub = mem.add_subparsers(dest="memcmd", required=True)
    mh = mem_sub.add_parser("history", help="person x time/place")
    mh.add_argument("--person", required=True, help="person_id or display_name")
    mh.add_argument("--store", required=True, type=Path)
    mh.add_argument("--run", default=None)
    mt = mem_sub.add_parser("together", help="named people on the same still or video clip")
    mt.add_argument("--store", required=True, type=Path)
    mt.add_argument("--run", default=None)
    me = mem_sub.add_parser("events", help="burst/day/folder signals; no LLM titles")
    me.add_argument("--store", required=True, type=Path)
    me.add_argument("--run", default=None)

    trk = sub.add_parser(
        "tracks",
        help="S7b derived video tracks (IoU+time; read-only; not persons)",
    )
    trk.add_argument("--run", required=True)
    trk.add_argument("--store", required=True, type=Path)
    trk.add_argument("--iou-min", type=float, default=None)
    trk.add_argument("--max-t-ms-gap", type=int, default=None)

    rev = sub.add_parser("review", help="persist review decisions (does not rewrite DBSCAN)")
    rev.add_argument("--run", required=True)
    rev.add_argument("--store", required=True, type=Path)
    rev_sub = rev.add_subparsers(dest="reviewcmd", required=True)
    r_m = rev_sub.add_parser("merge", help="same review identity; not a person")
    r_m.add_argument("--clusters", nargs="+", required=True, help="survivor first, then donors")
    r_s = rev_sub.add_parser("split", help="move faces into a new cluster")
    r_s.add_argument("--cluster", required=True)
    r_s.add_argument("--faces", nargs="+", required=True)
    r_i = rev_sub.add_parser("ignore", help="not a person, or unassigned singleton/junk/needs-review")
    r_i.add_argument("--cluster", default=None)
    r_i.add_argument("--face", default=None)
    r_i.add_argument("--as", dest="disposition", default=None)
    r_n = rev_sub.add_parser("note", help="durable review note")
    r_n.add_argument("--cluster", default=None)
    r_n.add_argument("--face", default=None)
    r_n.add_argument("--text", required=True)

    rui = sub.add_parser(
        "review-ui",
        help="S8 Interactive Review slice (tkinter; Name/Merge/Split/Ignore over review APIs)",
    )
    rui.add_argument(
        "--store",
        default=None,
        type=Path,
        help="SQLite store (default: %%LOCALAPPDATA%%\\Semblon\\store.sqlite)",
    )
    rui.add_argument(
        "--run",
        default=None,
        help="run id (default: latest run that has faces)",
    )

    home = sub.add_parser(
        "home",
        help="tk Home: Choose folder, Pause/Cancel/Resume, Open Review (JobEngine)",
    )
    home.add_argument(
        "--store",
        default=None,
        type=Path,
        help="SQLite store (default: %%LOCALAPPDATA%%\\Semblon\\store.sqlite)",
    )

    srch = sub.add_parser(
        "search",
        help="evidence-based lookup of named persons or identify a face (not a vector DB)",
    )
    srch.add_argument("--store", required=True, type=Path)
    srch.add_argument("--person", default=None, help="person_id or display_name")
    srch.add_argument("--face", default=None, help="face_id to identify vs persons")
    srch.add_argument("--run", default=None, help="required with --face")
    srch.add_argument("--people", action="store_true", help="list active named persons")
    srch.add_argument("--similar", default=None, help="observation_item_id in a non-identity space")

    wat = sub.add_parser("watch", help="poll a folder and ingest incrementally (cancellable)")
    wat.add_argument("folder", type=Path)
    wat.add_argument("--store", required=True, type=Path)
    wat.add_argument("--interval", type=float, default=5.0)
    wat.add_argument("--once", action="store_true")
    wat.add_argument("--observers", default="face")

    liv = sub.add_parser(
        "live",
        help="webcam/RTSP capture: detect->track->selective embed->identify vs persons (not always-on unless --seconds 0)",
    )
    liv.add_argument("--store", required=True, type=Path)
    liv.add_argument("--source", default="0", help="camera index or RTSP URL")
    liv.add_argument("--seconds", type=float, default=5.0, help="capture duration in seconds; 0 runs until cancel/SIGINT")
    liv.add_argument("--hz", type=float, default=1.0)
    liv.add_argument(
        "--reembed-s",
        type=float,
        default=2.0,
        help="re-embed a track when its last persisted embedding is older than this many seconds",
    )
    liv.add_argument(
        "--retain-s",
        type=float,
        default=None,
        help="rolling retention window for this live media (delete older observations)",
    )
    liv.add_argument("--strict", action="store_true", help="fail run on detect/embed errors")
    liv.add_argument("--prefer-gpu", action="store_true")

    canv = sub.add_parser(
        "canvas",
        help="observation overlay (boxes + tracks; not identity; not the S8 shell)",
    )
    canv.add_argument("--store", default=None, type=Path)
    canv.add_argument("--run", default=None)

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
            print("unexplained regression - not mature", file=sys.stderr)
            return 3
        return 0

    if args.cmd == "lab" and args.labcmd == "backup":
        from semblon.store import backup_store

        try:
            rec = backup_store(args.store, args.out)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "lab" and args.labcmd == "restore":
        from semblon.store import restore_store

        try:
            rec = restore_store(args.backup_from, args.store, force=args.force)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        except FileExistsError as e:
            print(f"refusing to overwrite: {e}", file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "lab" and args.labcmd == "integrity":
        from semblon.store import integrity_report

        try:
            rec = integrity_report(args.store)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0 if rec.get("ok") else 3

    if args.cmd == "lab" and args.labcmd == "models":
        from semblon.providers import weights_status

        print(json.dumps(weights_status(), indent=2))
        return 0

    if args.cmd == "lab" and args.labcmd == "providers":
        from semblon.engine import select_execution_provider
        from semblon.observers import optional_status

        rec = {"observers": optional_status(), "execution": select_execution_provider(prefer_gpu=True)}
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "lab" and args.labcmd == "gates":
        from semblon.gates import status_report

        print(json.dumps(status_report(args.gate_keys), indent=2))
        return 0

    if args.cmd == "lab" and args.labcmd == "opencv":
        from semblon.opencv_probe import probe_opencv

        rec = probe_opencv(timeout_s=args.timeout)
        print(json.dumps(rec, indent=2))
        return 0 if rec.get("ok") else 2

    if args.cmd == "lab" and args.labcmd == "eval":
        from semblon.eval import (
            DEFAULT_MINE_MAX,
            DEFAULT_THRESHOLD,
            EvalError,
            HARD_NEAR,
            add_pair,
            create_set,
            freeze_set,
            mine_discovery,
            score_set,
        )

        try:
            if args.evalcmd == "create":
                rec = create_set(
                    args.store,
                    args.eval_set,
                    args.kind,
                    pack_id=args.pack,
                    notes=args.notes,
                )
            elif args.evalcmd == "pair":
                rec = add_pair(
                    args.store,
                    args.eval_set,
                    args.faces[0],
                    args.faces[1],
                    args.label,
                    args.stratum,
                )
            elif args.evalcmd == "freeze":
                rec = freeze_set(args.store, args.eval_set)
            elif args.evalcmd == "mine":
                kwargs = {}
                if args.min_sim is not None:
                    kwargs["min_sim"] = args.min_sim
                else:
                    kwargs["min_sim"] = HARD_NEAR
                if args.max_pairs is not None:
                    kwargs["max_pairs"] = args.max_pairs
                else:
                    kwargs["max_pairs"] = DEFAULT_MINE_MAX
                rec = mine_discovery(args.store, args.run, args.eval_set, **kwargs)
            else:
                rec = score_set(
                    args.store,
                    args.eval_set,
                    threshold=DEFAULT_THRESHOLD if args.threshold is None else args.threshold,
                )
        except EvalError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2, default=str))
        return 0

    if args.cmd == "ingest":
        from semblon.ingest import CancelledError, ingest

        try:
            rec = ingest(
                args.folder,
                args.store,
                reprocess=args.reprocess,
                workers=args.workers,
                observers=args.observers,
                prefer_gpu=args.prefer_gpu,
                resume_run_id=args.resume_run,
            )
        except CancelledError as e:
            print(json.dumps({"cancelled": True, "run_id": e.run_id, **e.timings}, indent=2, default=str))
            return 2
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "process":
        from semblon.process import ProcessCancelled, ProcessError, process_folder

        try:
            from semblon.progress import format_progress_line

            def _cli_progress(ev):
                print(format_progress_line(ev), flush=True)

            process_folder(
                args.folder,
                store=args.store,
                out=args.out,
                reprocess=args.reprocess,
                open_review=not args.no_open,
                workers=args.workers,
                observers=args.observers,
                prefer_gpu=args.prefer_gpu,
                resume=args.resume,
                on_event=_cli_progress,
            )
        except ProcessCancelled as e:
            print(str(e), file=sys.stderr)
            return 2
        except ProcessError as e:
            print(str(e), file=sys.stderr)
            return 2
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            print("cancelled", file=sys.stderr)
            return 2
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
        from semblon.export import STRONG_MIN_INTRA, ExportError, export_review, export_views

        if args.out is None and args.views is None:
            print("export requires --out and/or --views", file=sys.stderr)
            return 2
        rec: dict = {"run_id": args.run}
        try:
            if args.out is not None:
                rec["html"] = export_review(
                    args.store,
                    args.run,
                    args.out,
                    strong_min_intra=STRONG_MIN_INTRA if args.strong_min_intra is None else args.strong_min_intra,
                )
            if args.views is not None:
                rec["views"] = export_views(args.store, args.run, args.views)
        except ExportError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "name":
        from semblon.review import ReviewError, name_cluster, name_face, name_faces, name_track

        chosen = [x for x in (args.cluster, args.face, args.track, args.faces) if x]
        if len(chosen) != 1:
            print(
                "name requires exactly one of --cluster, --face, --track, or --faces",
                file=sys.stderr,
            )
            return 2
        try:
            attach = getattr(args, "attach_to", None)
            kw = {"attach_to_person_id": attach, "create_new": attach is None}
            if args.cluster:
                rec = name_cluster(args.store, args.run, args.cluster, args.display_name, **kw)
            elif args.face:
                rec = name_face(args.store, args.run, args.face, args.display_name, **kw)
            elif args.track:
                rec = name_track(args.store, args.run, args.track, args.display_name, **kw)
            else:
                rec = name_faces(args.store, args.run, args.faces, args.display_name, **kw)
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

    if args.cmd == "identify":
        from semblon.eval import DEFAULT_THRESHOLD
        from semblon.identify import IdentifyError, identify_face, identify_image, identify_run

        if args.face and args.image:
            print("identify accepts at most one of --face or --image", file=sys.stderr)
            return 2
        threshold = DEFAULT_THRESHOLD if args.threshold is None else args.threshold
        try:
            if args.face:
                rec = identify_face(
                    args.store, args.run, args.face, threshold=threshold
                )
            elif args.image:
                rec = identify_image(
                    args.store, args.run, args.image, threshold=threshold
                )
            else:
                rec = identify_run(args.store, args.run, threshold=threshold)
        except IdentifyError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "inbox":
        from semblon.eval import DEFAULT_THRESHOLD
        from semblon.inbox import InboxError, inbox

        threshold = DEFAULT_THRESHOLD if args.threshold is None else args.threshold
        try:
            rec = inbox(args.store, args.run, threshold=threshold)
        except InboxError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "review":
        from semblon.review import (
            ReviewError,
            ignore_subject,
            merge_clusters,
            note_subject,
            split_cluster,
        )

        try:
            if args.reviewcmd == "merge":
                rec = merge_clusters(args.store, args.run, args.clusters)
            elif args.reviewcmd == "split":
                rec = split_cluster(args.store, args.run, args.cluster, args.faces)
            elif args.reviewcmd == "ignore":
                rec = ignore_subject(
                    args.store,
                    args.run,
                    cluster_id=args.cluster,
                    face_id=args.face,
                    disposition=args.disposition,
                )
            else:
                rec = note_subject(
                    args.store,
                    args.run,
                    args.text,
                    cluster_id=args.cluster,
                    face_id=args.face,
                )
        except ReviewError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "review-ui":
        from semblon.review_ui import ReviewUiError, run_review_ui

        try:
            run_review_ui(store=args.store, run_id=args.run)
        except ReviewUiError as e:
            print(str(e), file=sys.stderr)
            return 2
        return 0

    if args.cmd == "home":
        from semblon.home_ui import run_home_ui

        return run_home_ui(store=args.store)

    if args.cmd == "stats":
        from semblon.stats import StatsError, stats as run_stats

        try:
            rec = run_stats(args.store, args.run)
        except StatsError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2, default=str))
        return 0

    if args.cmd == "report":
        from semblon.report import ReportError, write_report

        try:
            rec = write_report(args.store, args.run, args.out)
        except ReportError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2))
        return 0

    if args.cmd == "search":
        from semblon.search import SearchError, search_face, search_people, search_person, search_similar

        try:
            if args.people:
                rec = search_people(args.store)
            elif args.person:
                rec = search_person(args.store, args.person)
            elif args.face:
                if not args.run:
                    print("--run is required with --face", file=sys.stderr)
                    return 2
                rec = search_face(args.store, args.run, args.face)
            elif args.similar:
                rec = search_similar(args.store, args.similar)
            else:
                print("search requires --people, --person, --face, or --similar", file=sys.stderr)
                return 2
        except SearchError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2, default=str))
        return 0

    if args.cmd == "memory":
        from semblon.memory import MemoryError, events, history, together

        try:
            if args.memcmd == "history":
                rec = history(args.store, person=args.person, run_id=args.run)
            elif args.memcmd == "together":
                rec = together(args.store, run_id=args.run)
            else:
                rec = events(args.store, run_id=args.run)
        except MemoryError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2, default=str))
        return 0

    if args.cmd == "tracks":
        from semblon.tracks import TracksError, derive_tracks

        kwargs = {}
        if args.iou_min is not None:
            kwargs["iou_min"] = args.iou_min
        if args.max_t_ms_gap is not None:
            kwargs["max_t_ms_gap"] = args.max_t_ms_gap
        try:
            rec = derive_tracks(args.store, args.run, **kwargs)
        except TracksError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(rec, indent=2, default=str))
        return 0

    if args.cmd == "watch":
        from semblon.ingest import CancelledError
        from semblon.watch import WatchError, watch_folder

        try:
            rec = watch_folder(
                args.folder,
                args.store,
                interval_s=args.interval,
                once=args.once,
                observers=args.observers,
            )
        except (WatchError, FileNotFoundError) as e:
            print(str(e), file=sys.stderr)
            return 2
        except CancelledError as e:
            print(json.dumps({"cancelled": True, "run_id": getattr(e, "run_id", None)}, indent=2))
            return 2
        print(json.dumps(rec, indent=2, default=str))
        return 0

    if args.cmd == "live":
        from semblon.ingest import CancelledError
        from semblon.live import LiveError, live_capture

        try:
            rec = live_capture(
                args.store,
                source=args.source,
                seconds=args.seconds,
                sample_hz=args.hz,
                reembed_s=args.reembed_s,
                retain_s=args.retain_s,
                strict=args.strict,
                prefer_gpu=args.prefer_gpu,
            )
        except (LiveError, FileNotFoundError) as e:
            print(str(e), file=sys.stderr)
            return 2
        except CancelledError as e:
            print(json.dumps({"cancelled": True, "run_id": e.run_id}, indent=2))
            return 2
        print(json.dumps(rec, indent=2, default=str))
        return 0

    if args.cmd == "canvas":
        from semblon.canvas import CanvasError, run_canvas

        try:
            return run_canvas(args.store, args.run)
        except CanvasError as e:
            print(str(e), file=sys.stderr)
            return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
