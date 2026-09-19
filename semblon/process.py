"""Happy-path folder processing: ingest -> cluster -> export review.html.

Owns run_id so the user does not copy it. Does not change thresholds or clustering.
Optional on_event is the UI-agnostic progress contract. progress=print stays the CLI log.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

from semblon.cluster import DEFAULT_EPS, DEFAULT_MIN_SAMPLES, ClusterError, cluster_run
from semblon.export import ExportError, export_review
from semblon.ingest import ingest
from semblon.progress import (
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_STARTED,
    STAGE_CLUSTER,
    STAGE_EXPORT,
    STAGE_PROCESS,
    ProgressCallback,
    emit,
    make_event,
)


class ProcessError(ValueError):
    pass


def default_store_path() -> Path:
    """User-local SQLite store. Windows: %LOCALAPPDATA%\\Semblon\\store.sqlite."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Semblon" / "store.sqlite"
    return Path.home() / ".local" / "share" / "semblon" / "store.sqlite"


def default_review_out(store: Path) -> Path:
    return Path(store).resolve().parent / "review.html"


def latest_run_id(store: Path, *, with_faces: bool = False) -> str | None:
    """Newest run on the store. with_faces skips empty incremental runs."""
    p = Path(store)
    if not p.is_file():
        return None
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    if with_faces:
        row = conn.execute(
            """SELECT r.run_id FROM runs r
               WHERE EXISTS (SELECT 1 FROM faces f WHERE f.run_id = r.run_id)
               ORDER BY COALESCE(r.finished_at, r.started_at) DESC, r.run_id DESC
               LIMIT 1"""
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT run_id FROM runs
               ORDER BY COALESCE(finished_at, started_at) DESC, run_id DESC
               LIMIT 1"""
        ).fetchone()
    conn.close()
    return None if row is None else str(row["run_id"])


def empty_state_line(store: Path, run_id: str) -> str:
    """One-line: this run's face count vs a populated run still on the store.

    Distinguishes an empty skip-all run from a store that still has faces,
    and (when ok=0) a run whose faces are all held-out of Review.
    """
    p = Path(store)
    if not p.is_file():
        return f"this run: 0 faces; store has 0 on run {run_id}"
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    this = conn.execute(
        """SELECT COUNT(*) AS n,
                  COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END), 0) AS ok
           FROM faces WHERE run_id=?""",
        (run_id,),
    ).fetchone()
    this_n = int(this["n"] or 0)
    this_ok = int(this["ok"] or 0)
    best = conn.execute(
        """SELECT r.run_id AS run_id, COUNT(f.face_id) AS n
           FROM runs r
           JOIN faces f ON f.run_id = r.run_id
           GROUP BY r.run_id
           ORDER BY n DESC, COALESCE(r.finished_at, r.started_at) DESC
           LIMIT 1"""
    ).fetchone()
    conn.close()
    if this_n == 0:
        this_bit = "this run: 0 faces"
    elif this_ok == this_n:
        this_bit = f"this run: {this_n} faces"
    else:
        this_bit = f"this run: {this_n} faces ({this_ok} ok)"
    if best is None:
        return f"{this_bit}; store has 0 on run {run_id}"
    return f"{this_bit}; store has {int(best['n'])} on run {best['run_id']}"


def process_folder(
    folder: Path,
    *,
    store: Path | None = None,
    out: Path | None = None,
    reprocess: bool = False,
    open_review: bool = True,
    progress=print,
    on_event: ProgressCallback = None,
) -> dict:
    """Run ingest -> cluster -> export. Uses frozen cluster defaults."""
    folder = Path(folder)
    t0 = time.perf_counter()
    if not folder.is_dir():
        err = f"folder not found: {folder}"
        emit(
            on_event,
            make_event(STAGE_PROCESS, KIND_FAILED, error=err, elapsed_s=0.0),
        )
        raise ProcessError(err)

    store_path = Path(store) if store is not None else default_store_path()
    out_path = Path(out) if out is not None else default_review_out(store_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)

    emit(
        on_event,
        make_event(
            STAGE_PROCESS,
            KIND_STARTED,
            path=str(folder.resolve()),
            message=f"Ingesting stills from: {folder.resolve()}",
        ),
    )
    progress(f"Ingesting stills from: {folder.resolve()}")
    progress(f"Store: {store_path.resolve()}")
    try:
        try:
            ing = ingest(folder, store_path, reprocess=reprocess, on_event=on_event)
        except FileNotFoundError as e:
            raise ProcessError(str(e)) from e

        run_id = ing["run_id"]
        progress(f"Ingest done. run_id={run_id}")
        progress(
            f"  new_media={ing.get('new_media')} faces={ing.get('faces')} "
            f"ok={ing.get('ok')} skipped_seen={ing.get('skipped_seen', 0)}"
        )

        # FACE-005 skip-all creates a new empty run. Review that and the HTML
        # would be blank even though prior faces still exist on the store.
        if int(ing.get("faces") or 0) == 0:
            prior = latest_run_id(store_path, with_faces=True)
            if prior:
                progress(
                    f"No new faces this run; reviewing existing run_id={prior} "
                    f"(skipped_seen={ing.get('skipped_seen', 0)})"
                )
                run_id = prior
                clu = {
                    "clusters": None,
                    "clustered": None,
                    "unassigned": None,
                    "note": "no new faces; reused prior run for review",
                }
            else:
                clu = None
        else:
            clu = None

        if clu is None:
            progress(f"Clustering (eps={DEFAULT_EPS}, min_samples={DEFAULT_MIN_SAMPLES})...")
            emit(
                on_event,
                make_event(
                    STAGE_CLUSTER,
                    KIND_STARTED,
                    run_id=run_id,
                    message=f"Clustering (eps={DEFAULT_EPS}, min_samples={DEFAULT_MIN_SAMPLES})",
                ),
            )
            try:
                clu = cluster_run(
                    store_path,
                    run_id,
                    eps=DEFAULT_EPS,
                    min_samples=DEFAULT_MIN_SAMPLES,
                )
            except ClusterError as e:
                raise ProcessError(str(e)) from e
            emit(
                on_event,
                make_event(
                    STAGE_CLUSTER,
                    KIND_COMPLETED,
                    run_id=run_id,
                    elapsed_s=clu.get("cluster_s"),
                    counts={
                        "clusters": int(clu.get("clusters") or 0),
                        "clustered": int(clu.get("clustered") or 0),
                        "unassigned": int(clu.get("unassigned") or 0),
                    },
                ),
            )
            progress(
                f"Cluster done. clusters={clu.get('clusters')} "
                f"clustered={clu.get('clustered')} unassigned={clu.get('unassigned')}"
            )

        progress(f"Writing review HTML: {out_path.resolve()}")
        emit(
            on_event,
            make_event(
                STAGE_EXPORT,
                KIND_STARTED,
                run_id=run_id,
                path=str(out_path.resolve()),
            ),
        )
        try:
            exp = export_review(store_path, run_id, out_path)
        except ExportError as e:
            raise ProcessError(str(e)) from e
        emit(
            on_event,
            make_event(
                STAGE_EXPORT,
                KIND_COMPLETED,
                run_id=run_id,
                path=str(exp["out"]),
            ),
        )
        progress(f"Review ready: {exp['out']}")

        opened = False
        if open_review:
            opened = _try_open(Path(exp["out"]), progress)

        rec = {
            "run_id": run_id,
            "store": str(store_path.resolve()),
            "out": exp["out"],
            "opened": opened,
            "ingest": ing,
            "cluster": clu,
            "export": exp,
        }
        emit(
            on_event,
            make_event(
                STAGE_PROCESS,
                KIND_COMPLETED,
                run_id=run_id,
                path=str(exp["out"]),
                elapsed_s=round(time.perf_counter() - t0, 3),
                files_total=ing.get("files"),
                files_processed=ing.get("files"),
                faces_found=ing.get("faces"),
            ),
        )
        return rec
    except Exception as e:
        emit(
            on_event,
            make_event(
                STAGE_PROCESS,
                KIND_FAILED,
                error=str(e),
                elapsed_s=round(time.perf_counter() - t0, 3),
            ),
        )
        raise


def _try_open(path: Path, progress) -> bool:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
            progress("Opened review in your default browser.")
            return True
        if sys.platform == "darwin":
            import subprocess

            subprocess.run(["open", str(path)], check=False)
            progress("Opened review.")
            return True
        import subprocess

        subprocess.run(["xdg-open", str(path)], check=False)
        progress("Opened review.")
        return True
    except OSError as e:
        progress(f"Could not open review automatically ({e}). Open it yourself:")
        progress(f"  {path}")
        return False
