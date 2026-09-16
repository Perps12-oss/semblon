"""Happy-path folder processing: ingest -> cluster -> export review.html.

Owns run_id so the user does not copy it. Does not change thresholds or clustering.
Optional on_event is the UI-agnostic progress contract. progress=print stays the CLI log.
"""

from __future__ import annotations

import os
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
