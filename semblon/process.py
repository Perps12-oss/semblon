"""Happy-path folder processing: ingest -> cluster.

Synchronous headless path. Does not construct a JobEngine — the product shell
owns that engine through Application. Does not write or open review.html.
The library is the review surface (`semblon shell`).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path, PureWindowsPath

from semblon.cluster import DEFAULT_EPS, DEFAULT_MIN_SAMPLES, ClusterError, cluster_run
from semblon.ingest import CancelledError, ingest, video_sampling_complete
from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_QUEUED,
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


class ProcessCancelled(ProcessError):
    """Cooperative cancel. Partial ingest remains on the store; this is not success."""

    def __init__(self, message: str = "process cancelled", *, run_id: str | None = None):
        super().__init__(message)
        self.run_id = run_id


def _looks_windows_path(path: Path | str) -> bool:
    s = str(path)
    return ("\\" in s) or (len(s) >= 2 and s[1] == ":")


def default_store_path() -> Path:
    """User-local SQLite store. Windows: %LOCALAPPDATA%\\Semblon\\store.sqlite."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            # Keep path parts addressable in cross-platform tests.
            return Path(base.replace("\\", "/")) / "Semblon" / "store.sqlite"
    return Path.home() / ".local" / "share" / "semblon" / "store.sqlite"


def default_review_out(store: Path) -> Path:
    """Path of a retired review.html artifact. Used only to delete leftovers."""
    if _looks_windows_path(store):
        p = PureWindowsPath(str(store))
        return Path(str(p.with_name("review.html")))
    return Path(store).resolve().parent / "review.html"


def latest_run_id(store: Path, *, with_faces: bool = False) -> str | None:
    """Newest run on the store. with_faces skips empty incremental runs."""
    p = Path(store)
    if not p.is_file():
        return None
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
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
    conn.execute("PRAGMA busy_timeout=5000")
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


_INCOMPLETE_NOTES = frozenset({"cancelled", "interrupted"})
_RUN_STAGES = frozenset({"ingest", "cluster", "export"})
_RUN_JOBS = frozenset(
    {"queued", "running", "paused", "cancelling", "completed", "failed", "cancelled"}
)


def _folder_matches(cfg_folder: str, folder: Path) -> bool:
    if not cfg_folder:
        return False
    try:
        return Path(cfg_folder).resolve() == Path(folder).resolve()
    except OSError:
        return os.path.normcase(str(cfg_folder).rstrip("\\/")) == os.path.normcase(
            str(folder).rstrip("\\/")
        )


def persist_run_stage(
    store: Path, run_id: str, *, stage: str | None = None, job: str | None = None
) -> None:
    """Persist closed stage/job tokens in timings_json without changing the schema."""
    if stage not in _RUN_STAGES:
        stage = None
    if job not in _RUN_JOBS:
        job = None
    if stage is None and job is None:
        return
    conn = sqlite3.connect(Path(store))
    row = conn.execute(
        "SELECT timings_json FROM runs WHERE run_id=?", (run_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return
    try:
        timings = json.loads(row[0] or "{}")
    except (json.JSONDecodeError, TypeError):
        timings = {}
    if not isinstance(timings, dict):
        timings = {}
    if stage is not None:
        timings["stage"] = stage
    if job is not None:
        timings["job"] = job
    conn.execute(
        "UPDATE runs SET timings_json=? WHERE run_id=?",
        (json.dumps(timings), run_id),
    )
    conn.commit()
    conn.close()


def _raise_if_process_cancelled(cancel, *, run_id: str, progress, on_event, started: float) -> None:
    if cancel is None:
        return
    try:
        requested = bool(cancel())
    except Exception:
        requested = False
    if not requested:
        return
    progress("Cancelled.")
    emit(
        on_event,
        make_event(
            STAGE_PROCESS,
            KIND_CANCELLED,
            run_id=run_id,
            message="cancelled",
            outcome="cancelled",
            elapsed_s=round(time.perf_counter() - started, 3),
        ),
    )
    raise ProcessCancelled("process cancelled", run_id=run_id)


def _path_is_within(path: str, folder: Path) -> bool:
    try:
        candidate = Path(path).resolve()
        root = Path(folder).resolve()
        return candidate == root or root in candidate.parents
    except OSError:
        return False


def inspect_run_stages(
    store: Path, run_id: str, *, out: Path | None = None, folder: Path | None = None
) -> dict:
    """Which process stages already landed. No new columns."""
    p = Path(store)
    empty = {
        "run_id": run_id,
        "ingest_done": False,
        "cluster_done": False,
        "export_done": False,
        "notes": None,
        "stage": None,
        "job": None,
        "faces": 0,
        "ok": 0,
        "clusters": 0,
    }
    if not p.is_file():
        return empty
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    row = conn.execute(
        "SELECT notes, finished_at, timings_json FROM runs WHERE run_id=?", (run_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return empty
    notes = row["notes"]
    faces = conn.execute(
        """SELECT COUNT(*) AS n,
                  COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END), 0) AS ok
           FROM faces WHERE run_id=?""",
        (run_id,),
    ).fetchone()
    n_faces = int(faces["n"] or 0)
    n_ok = int(faces["ok"] or 0)
    n_clusters = int(
        conn.execute("SELECT COUNT(*) FROM clusters WHERE run_id=?", (run_id,)).fetchone()[0]
    )
    media_complete = True
    if folder is not None:
        media_rows = conn.execute(
            "SELECT media_id, source_type, path FROM media"
        ).fetchall()
        for media in media_rows:
            if not _path_is_within(str(media["path"]), folder):
                continue
            if media["source_type"] == "video":
                observed_in_run = conn.execute(
                    "SELECT 1 FROM observations WHERE media_id=? AND run_id=? LIMIT 1",
                    (media["media_id"], run_id),
                ).fetchone()
                complete = video_sampling_complete(
                    conn,
                    str(media["media_id"]),
                    run_id=run_id if observed_in_run is not None else None,
                )
            else:
                complete = conn.execute(
                    "SELECT 1 FROM observations WHERE media_id=? LIMIT 1",
                    (media["media_id"],),
                ).fetchone() is not None
            if not complete:
                media_complete = False
                break
    conn.close()
    ingest_done = (
        row["finished_at"] is not None
        and notes not in _INCOMPLETE_NOTES
        and media_complete
    )
    timings = {}
    try:
        timings = json.loads(row["timings_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        pass
    if not isinstance(timings, dict):
        timings = {}
    cluster_done = ingest_done and (n_ok == 0 or n_clusters > 0)
    # The library is the review surface. review.html is not a process stage.
    export_done = cluster_done
    return {
        "run_id": run_id,
        "ingest_done": ingest_done,
        "cluster_done": cluster_done,
        "export_done": export_done,
        "notes": notes,
        "stage": timings.get("stage"),
        "job": timings.get("job"),
        "faces": n_faces,
        "ok": n_ok,
        "clusters": n_clusters,
    }


def find_resumable_run(store: Path, folder: Path) -> str | None:
    """Latest run for this folder that still has an unfinished process stage."""
    p = Path(store)
    if not p.is_file():
        return None
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    rows = conn.execute(
        """SELECT run_id, config_json FROM runs
           ORDER BY COALESCE(finished_at, started_at) DESC, run_id DESC"""
    ).fetchall()
    conn.close()
    out = default_review_out(p)
    for row in rows:
        try:
            cfg = json.loads(row["config_json"] or "{}")
        except json.JSONDecodeError:
            cfg = {}
        if not _folder_matches(str(cfg.get("folder") or ""), folder):
            continue
        stages = inspect_run_stages(p, str(row["run_id"]), out=out, folder=folder)
        if not stages["ingest_done"] or not stages["cluster_done"] or not stages["export_done"]:
            return str(row["run_id"])
    return None


def _ingest_record_from_run(store: Path, run_id: str) -> dict:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    row = conn.execute("SELECT timings_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    n_faces = int(
        conn.execute("SELECT COUNT(*) FROM faces WHERE run_id=?", (run_id,)).fetchone()[0]
    )
    n_ok = int(
        conn.execute(
            "SELECT COUNT(*) FROM faces WHERE run_id=? AND status='ok'", (run_id,)
        ).fetchone()[0]
    )
    conn.close()
    timings = {}
    if row and row["timings_json"]:
        try:
            timings = json.loads(row["timings_json"])
        except json.JSONDecodeError:
            timings = {}
    return {
        "run_id": run_id,
        "new_media": int(timings.get("new_media") or 0),
        "faces": int(timings.get("faces") or n_faces),
        "ok": int(timings.get("ok") or n_ok),
        "skipped_seen": int(timings.get("skipped_seen") or 0),
        "files": int(timings.get("files") or 0),
        "resumed": True,
    }


def _cluster_record_from_run(store: Path, run_id: str) -> dict:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    n_clusters = int(
        conn.execute("SELECT COUNT(*) FROM clusters WHERE run_id=?", (run_id,)).fetchone()[0]
    )
    n_clustered = int(
        conn.execute(
            "SELECT COUNT(*) FROM faces WHERE run_id=? AND cluster_id IS NOT NULL",
            (run_id,),
        ).fetchone()[0]
    )
    n_ok = int(
        conn.execute(
            "SELECT COUNT(*) FROM faces WHERE run_id=? AND status='ok'", (run_id,)
        ).fetchone()[0]
    )
    conn.close()
    return {
        "run_id": run_id,
        "clusters": n_clusters,
        "clustered": n_clustered,
        "unassigned": max(0, n_ok - n_clustered),
        "note": "resumed; clusters already on run",
        "resumed": True,
    }


def process_folder(
    folder: Path,
    *,
    store: Path | None = None,
    out: Path | None = None,
    reprocess: bool = False,
    open_review: bool = False,
    progress=print,
    on_event: ProgressCallback = None,
    cancel=None,
    workers: int = 1,
    observers: str = "face",
    prefer_gpu: bool = False,
    resume: bool = False,
) -> dict:
    """Run ingest then cluster. Synchronous. Does not construct a JobEngine.

    The product UI is `semblon shell` (PySide6 → Application). This function is
    the headless CLI path. `out` and `open_review` are ignored: review.html is
    not written and nothing is opened in a browser.
    """
    del out, open_review
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
    store_path.parent.mkdir(parents=True, exist_ok=True)

    resume_run = find_resumable_run(store_path, folder) if resume else None
    stages = (
        inspect_run_stages(store_path, resume_run, folder=folder)
        if resume_run
        else None
    )
    start_msg = f"Ingesting media from: {folder.resolve()}"
    if resume_run and stages:
        nxt = "ingest"
        if stages["ingest_done"] and not stages["cluster_done"]:
            nxt = "cluster"
        elif stages["cluster_done"] and not stages["export_done"]:
            nxt = "export"
        elif stages["ingest_done"] and stages["cluster_done"] and stages["export_done"]:
            nxt = "already complete"
        start_msg = f"Resume run_id={resume_run} at {nxt}"

    emit(
        on_event,
        make_event(
            STAGE_PROCESS,
            KIND_QUEUED,
            path=str(folder.resolve()),
            message=f"Queued: {folder.resolve()}",
        ),
    )
    emit(
        on_event,
        make_event(
            STAGE_PROCESS,
            KIND_STARTED,
            path=str(folder.resolve()),
            run_id=resume_run,
            message=start_msg,
            outcome="resumed" if resume_run else None,
        ),
    )
    progress(start_msg)
    progress(f"Store: {store_path.resolve()}")
    try:
        try:
            if resume_run and stages and stages["ingest_done"]:
                progress(f"Resume: skip ingest (run_id={resume_run})")
                emit(
                    on_event,
                    make_event(
                        STAGE_PROCESS,
                        KIND_STARTED,
                        run_id=resume_run,
                        message=f"Resume: skip ingest (run_id={resume_run})",
                        outcome="skipped_stage",
                    ),
                )
                ing = _ingest_record_from_run(store_path, resume_run)
            else:
                ing = ingest(
                    folder,
                    store_path,
                    reprocess=reprocess,
                    on_event=on_event,
                    cancel=cancel,
                    workers=workers,
                    observers=observers,
                    prefer_gpu=prefer_gpu,
                    resume_run_id=resume_run if resume else None,
                )
        except CancelledError as e:
            progress("Cancelled.")
            emit(
                on_event,
                make_event(
                    STAGE_PROCESS,
                    KIND_CANCELLED,
                    run_id=e.run_id,
                    message="cancelled",
                    outcome="cancelled",
                    elapsed_s=round(time.perf_counter() - t0, 3),
                ),
            )
            raise ProcessCancelled("process cancelled", run_id=e.run_id) from e
        except FileNotFoundError as e:
            raise ProcessError(str(e)) from e

        run_id = ing["run_id"]
        ingest_run_id = run_id
        progress(f"Ingest done. run_id={run_id}")
        progress(
            f"  new_media={ing.get('new_media')} faces={ing.get('faces')} "
            f"ok={ing.get('ok')} skipped_seen={ing.get('skipped_seen', 0)}"
        )
        _raise_if_process_cancelled(
            cancel, run_id=run_id, progress=progress, on_event=on_event, started=t0
        )

        # FACE-005 skip-all creates a new empty run. Reviewing that run would
        # hide prior faces that still exist on the store.
        if resume_run and stages and stages["cluster_done"] and run_id == resume_run:
            clu = _cluster_record_from_run(store_path, run_id)
            progress(f"Resume: skip cluster (run_id={run_id})")
            emit(
                on_event,
                make_event(
                    STAGE_CLUSTER,
                    KIND_COMPLETED,
                    run_id=run_id,
                    message=f"Resume: skip cluster (run_id={run_id})",
                    outcome="skipped_stage",
                    counts={
                        "clusters": int(clu.get("clusters") or 0),
                        "clustered": int(clu.get("clustered") or 0),
                        "unassigned": int(clu.get("unassigned") or 0),
                    },
                ),
            )
        elif int(ing.get("faces") or 0) == 0:
            prior = latest_run_id(store_path, with_faces=True)
            if prior:
                progress(
                    f"No new faces this run; reviewing existing run_id={prior} "
                    f"(skipped_seen={ing.get('skipped_seen', 0)})"
                )
                if prior != ingest_run_id:
                    _drop_empty_run(store_path, ingest_run_id)
                run_id = prior
                clu = {
                    "clusters": 0,
                    "clustered": 0,
                    "unassigned": 0,
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

        _raise_if_process_cancelled(
            cancel, run_id=run_id, progress=progress, on_event=on_event, started=t0
        )

        exp = {
            "run_id": run_id,
            "out": None,
            "note": "review lives in the library; review.html is not written",
        }
        progress(f"Library ready. run_id={run_id}")
        emit(
            on_event,
            make_event(
                STAGE_EXPORT,
                KIND_STARTED,
                run_id=run_id,
                message="Library ready",
            ),
        )
        emit(
            on_event,
            make_event(
                STAGE_EXPORT,
                KIND_COMPLETED,
                run_id=run_id,
                message="Library ready",
                outcome="library",
            ),
        )

        opened = False

        rec = {
            "run_id": run_id,
            "store": str(store_path.resolve()),
            "out": None,
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
                path=str(store_path.resolve()),
                elapsed_s=round(time.perf_counter() - t0, 3),
                files_total=ing.get("files"),
                files_processed=ing.get("files"),
                faces_found=ing.get("faces"),
            ),
        )
        return rec
    except ProcessCancelled:
        raise
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


def _drop_empty_run(store: Path, run_id: str) -> bool:
    """Best-effort cleanup for FACE-005 skip-all empty runs."""
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        n_obs = int(conn.execute("SELECT COUNT(*) FROM observations WHERE run_id=?", (run_id,)).fetchone()[0])
        n_faces = int(conn.execute("SELECT COUNT(*) FROM faces WHERE run_id=?", (run_id,)).fetchone()[0])
        n_decisions = int(conn.execute("SELECT COUNT(*) FROM decisions WHERE run_id=?", (run_id,)).fetchone()[0])
        if n_obs == 0 and n_faces == 0 and n_decisions == 0:
            conn.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
            conn.commit()
            return True
        return False
    finally:
        conn.close()
