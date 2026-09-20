"""0.2 ingest: folder of stills (+ S7a sampled video) → media / observations / faces. No cluster.

Pipeline: one-pass discover → bounded hash → skip → bounded decode/embed workers →
batched SQLite writer. Video frames stream; never materialize all samples.
No --batch CLI knob until explicit batch inference exists.
Does not change detection/quality thresholds or pack/provider.
"""

from __future__ import annotations

import hashlib
import json
import platform
import signal
import threading
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from semblon import __version__
from semblon.engine import (
    PACK_FAMILY,
    discover_weight_hashes,
    embed_bgr,
    pack_id,
    process_arch,
    process_execution,
    select_execution_provider,
    _sha256_file,
)
from semblon.observers import ensure_face_item, observe_bgr, persist_derived_tracks
from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_PARTIAL,
    KIND_PROGRESS,
    KIND_STARTED,
    STAGE_DISCOVER,
    STAGE_INGEST,
    ProgressCallback,
    emit,
    make_event,
)
from semblon.providers import FaceKitProvider
from semblon.store import connect, init_db, stamp_unfinished_runs
from semblon.temporal import (
    DEFAULT_SAMPLE_HZ,
    VIDEO_EXT,
    VideoError,
    iter_sampled_frames,
)

CancelCallback = Callable[[], bool] | None

COMMIT_EVERY_N = 32
COMMIT_EVERY_S = 0.1
PROGRESS_THROTTLE_S = 0.1


class CancelledError(Exception):
    """Cooperative cancel. Batched commits already made remain; the run is stamped cancelled."""

    def __init__(self, message: str = "ingest cancelled", *, run_id: str | None = None, timings: dict | None = None):
        super().__init__(message)
        self.run_id = run_id
        self.timings = timings or {}


def _cancel_requested(cancel: CancelCallback) -> bool:
    if cancel is None:
        return False
    try:
        return bool(cancel())
    except Exception:
        return False


STILL_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DET_SCORE_MIN = 0.60
CLUSTER_MIN_SIDE = 80
DET_SIZE = (640, 640)


def load_app(det_size=DET_SIZE, *, prefer_gpu: bool = False):
    """FaceKit provider boundary. Tests may monkeypatch this name."""
    return FaceKitProvider().load(det_size, prefer_gpu=prefer_gpu).app


def size_band(w: int, h: int) -> str:
    m = min(w, h)
    if m < 40:
        return "<40"
    if m < 80:
        return "40-79"
    if m < 120:
        return "80-119"
    if m < 200:
        return "120-199"
    return "200+"


def _arch() -> str:
    return process_arch()


def _execution() -> str:
    return process_execution()


def discover_media(folder: Path) -> tuple[list[Path], list[Path]]:
    """One recursive walk → sorted (stills, videos)."""
    folder = Path(folder)
    stills: list[Path] = []
    videos: list[Path] = []
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in STILL_EXT:
            stills.append(p)
        elif ext in VIDEO_EXT:
            videos.append(p)
    stills.sort()
    videos.sort()
    return stills, videos


def discover_stills(folder: Path) -> list[Path]:
    """Sorted still paths under folder. Same filter ingest has always used."""
    return discover_media(folder)[0]


def media_skip_reason(
    conn,
    digest: str,
    run_id: str,
    *,
    reprocess: bool,
) -> tuple[str | None, str | None]:
    """Why this sha256 should be skipped, plus media_id if known.

    None reason → process (new file, or --reprocess of an old hash on this run).
    `seen` → already ingested on an earlier run (FACE-005 incremental).
    `same_run` → already observed on this run.
    """
    row = conn.execute("SELECT media_id FROM media WHERE sha256=?", (digest,)).fetchone()
    if row is None:
        return None, None
    media_id = row[0]
    same = conn.execute(
        "SELECT 1 FROM observations WHERE media_id=? AND run_id=? AND frame_id IS NULL",
        (media_id, run_id),
    ).fetchone()
    if same:
        return "same_run", media_id
    if not reprocess:
        return "seen", media_id
    return None, media_id


def _hash_path(path: Path, index: int) -> dict:
    """SHA-256 only. No decode, no embed, no SQLite."""
    try:
        digest = _sha256_file(path)
        st = path.stat()
    except OSError:
        return {"index": index, "path": path, "outcome": "failed", "error": "hash"}
    return {
        "index": index,
        "path": path,
        "digest": digest,
        "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
        "byte_size": st.st_size,
        "outcome": "hashed",
    }


def _read_and_hash(path: Path) -> tuple[str, bytes, int, int]:
    """One I/O: bytes + sha256 + mtime_ns + byte_size."""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    st = path.stat()
    return (
        digest,
        data,
        getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
        st.st_size,
    )


def _decode_bgr(data: bytes | None, path: Path):
    if data:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            return img
    return cv2.imread(str(path))


def _persist_faces(conn, *, obs_id: str, run_id: str, pack_id: str, faces: list) -> tuple[int, int, int, int]:
    """Insert face rows. Returns (n_faces, n_ok, n_lq, n_rej)."""
    n_faces = n_ok = n_lq = n_rej = 0
    for f in faces:
        fw, fh = f["face_w"], f["face_h"]
        score = f["det_score"]
        band = size_band(fw, fh)
        if score < DET_SCORE_MIN:
            status, blob, pack, dim = "rejected", None, None, None
            n_rej += 1
        else:
            vec = np.asarray(f["embedding"], dtype=np.float32)
            blob, pack, dim = vec.tobytes(), pack_id, int(vec.size)
            if min(fw, fh) < CLUSTER_MIN_SIDE:
                status = "low_quality"
                n_lq += 1
            else:
                status = "ok"
                n_ok += 1
        x1, y1, x2, y2 = f["bbox"]
        fid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
               det_score, face_w, face_h, size_band, embedding, embedding_pack, embedding_dim, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fid, obs_id, run_id, x1, y1, x2, y2,
                score, fw, fh, band, blob, pack, dim, status,
            ),
        )
        ensure_face_item(
            conn,
            face_id=fid,
            observation_id=obs_id,
            run_id=run_id,
            bbox=(x1, y1, x2, y2),
            score=score,
            status=status,
        )
        n_faces += 1
    return n_faces, n_ok, n_lq, n_rej


def _iter_hash_results(
    files: list[Path],
    *,
    workers: int,
    want_cancel: Callable[[], bool],
) -> Iterator[dict]:
    """Yield hash records with bounded in-flight futures (max workers*4)."""
    if not files:
        return
    if workers == 1:
        for index, path in enumerate(files, start=1):
            if want_cancel():
                return
            yield _hash_path(path, index)
        return

    limit = max(workers * 4, workers)
    pending: set = set()
    it = iter(enumerate(files, start=1))

    def _submit(pool: ThreadPoolExecutor) -> bool:
        try:
            index, path = next(it)
        except StopIteration:
            return False
        pending.add(pool.submit(_hash_path, path, index))
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while len(pending) < limit and _submit(pool):
            pass
        while pending:
            if want_cancel():
                for fut in pending:
                    fut.cancel()
                return
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                if want_cancel():
                    for rest in pending:
                        rest.cancel()
                    return
                yield fut.result()
                while len(pending) < limit and _submit(pool):
                    pass


_thread_ctx = threading.local()


def _thread_app(*, det_size, prefer_gpu: bool):
    app = getattr(_thread_ctx, "app", None)
    if app is None:
        app = load_app(det_size, prefer_gpu=prefer_gpu)
        _thread_ctx.app = app
    return app


def _infer_still(
    *,
    path: Path,
    data: bytes | None,
    det_size,
    prefer_gpu: bool,
) -> dict:
    """Decode + embed in a worker. Never writes SQLite."""
    img0 = _decode_bgr(data, path)
    if img0 is None:
        return {"ok": False, "reason": "decode"}
    app = _thread_app(det_size=det_size, prefer_gpu=prefer_gpu)
    faces = embed_bgr(app, img0)
    return {"ok": True, "img": img0, "faces": faces}


def ingest(
    folder: Path,
    store: Path,
    *,
    reprocess: bool = False,
    workers: int = 1,
    on_event: ProgressCallback = None,
    cancel: CancelCallback = None,
    observers: str = "face",
    prefer_gpu: bool = False,
    resume_run_id: str | None = None,
) -> dict:
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    if workers < 1:
        raise ValueError("workers must be >= 1")
    observer_list = tuple(x.strip() for x in str(observers).split(",") if x.strip()) or ("face",)
    extra_observers = tuple(x for x in observer_list if x != "face")

    conn = connect(store)
    init_db(conn)

    import insightface
    import onnxruntime as ort

    hashes = discover_weight_hashes()
    ifver = getattr(insightface, "__version__", "unknown")

    ep = select_execution_provider(prefer_gpu=prefer_gpu)
    t_load = time.perf_counter()
    app = load_app(DET_SIZE, prefer_gpu=prefer_gpu)
    load_s = time.perf_counter() - t_load
    # Re-hash after load so first-run download is captured in pack_id.
    hashes = discover_weight_hashes() or hashes
    pid = pack_id(ifver, hashes)

    runtime = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "os": platform.system().lower(),
        "os_version": platform.version(),
        "arch": _arch(),
        "execution": _execution(),
        "python": sys.version.split()[0],
        "python_arch": platform.architecture()[0],
        "ort_package": "onnxruntime",
        "ort_version": ort.__version__,
        "insightface_version": ifver,
        "pack_family": PACK_FAMILY,
        "pack_id": pid,
        "det_size": list(DET_SIZE),
        "device": ep["device"],
        "execution_provider": ep["chosen"],
        "gpu": ep["gpu"],
        "onnx_providers": ep["available"],
        "fallback_providers": ["CPUExecutionProvider"] if ep["chosen"] != "CPUExecutionProvider" else [],
        "provider_note": ep.get("note"),
        "provider": FaceKitProvider.info.name,
        "modality": FaceKitProvider.info.modality,
        "workers": int(workers),
        "hash_workers": int(workers),
        "inference_workers": int(workers),
        "observers": list(observer_list),
        "model_load_s": round(load_s, 3),
        "software_version": __version__,
    }
    config = {
        "det_score_min": DET_SCORE_MIN,
        "cluster_min_side": CLUSTER_MIN_SIDE,
        "det_size": list(DET_SIZE),
        "folder": str(folder),
        "reprocess": bool(reprocess),
        "incremental": not reprocess,
        "sample_hz": DEFAULT_SAMPLE_HZ,
        "workers": int(workers),
        "observers": list(observer_list),
        "prefer_gpu": bool(prefer_gpu),
    }
    if resume_run_id:
        row = conn.execute("SELECT * FROM runs WHERE run_id=?", (resume_run_id,)).fetchone()
        if row is None:
            conn.close()
            raise ValueError(f"unknown run: {resume_run_id}")
        run_id = str(row["run_id"])
        pid = str(row["pack_id"])
        conn.execute(
            "UPDATE runs SET finished_at=NULL, notes=NULL WHERE run_id=?",
            (run_id,),
        )
        conn.commit()
    else:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        conn.execute(
            """INSERT INTO runs(run_id, started_at, software_version, pack_id,
               embedding_dim, embedding_norm, config_json, runtime_json, arch, execution,
               ort_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id,
                datetime.now(timezone.utc).isoformat(),
                __version__,
                pid,
                512,
                "l2",
                json.dumps(config),
                json.dumps(runtime),
                _arch(),
                _execution(),
                ort.__version__,
            ),
        )
        conn.commit()
    stamp_unfinished_runs(conn, except_run_id=run_id)

    emit(on_event, make_event(STAGE_DISCOVER, KIND_STARTED, path=str(folder), run_id=run_id))
    files, videos = discover_media(folder)
    n_files = len(files) + len(videos)
    emit(
        on_event,
        make_event(
            STAGE_DISCOVER,
            KIND_PROGRESS,
            current=n_files,
            total=n_files,
            files_total=n_files,
            run_id=run_id,
        ),
    )
    emit(
        on_event,
        make_event(
            STAGE_DISCOVER,
            KIND_COMPLETED,
            current=n_files,
            total=n_files,
            files_total=n_files,
            run_id=run_id,
        ),
    )
    emit(
        on_event,
        make_event(
            STAGE_INGEST,
            KIND_STARTED,
            current=0,
            total=n_files,
            files_processed=0,
            files_total=n_files,
            faces_found=0,
            run_id=run_id,
        ),
    )

    n_media = n_skip_seen = n_skip_same = n_faces = n_ok = n_lq = n_rej = n_fail = 0
    n_video_frames = 0
    cancelled = False
    completed = 0
    dirty = 0
    t0 = time.perf_counter()
    last_commit = t0
    last_emit = 0.0
    sigint = {"hit": False}
    prev_sigint = None

    def _on_sigint(_signum, _frame):
        sigint["hit"] = True

    def want_cancel() -> bool:
        return sigint["hit"] or _cancel_requested(cancel)

    try:
        prev_sigint = signal.signal(signal.SIGINT, _on_sigint)
    except (ValueError, OSError):
        prev_sigint = None

    def _restore_sig() -> None:
        if prev_sigint is not None:
            try:
                signal.signal(signal.SIGINT, prev_sigint)
            except (ValueError, OSError):
                pass

    def maybe_commit(*, force: bool = False) -> None:
        nonlocal dirty, last_commit
        if dirty <= 0:
            return
        now = time.perf_counter()
        if force or dirty >= COMMIT_EVERY_N or (now - last_commit) >= COMMIT_EVERY_S:
            conn.commit()
            dirty = 0
            last_commit = now

    def tick(path: Path, outcome: str, *, force: bool = False) -> None:
        nonlocal completed, last_emit
        completed += 1
        now = time.perf_counter()
        if (
            force
            or completed >= n_files
            or last_emit == 0.0
            or (now - last_emit) >= PROGRESS_THROTTLE_S
        ):
            last_emit = now
            emit(
                on_event,
                make_event(
                    STAGE_INGEST,
                    KIND_PROGRESS,
                    current=completed,
                    total=n_files,
                    files_processed=completed,
                    files_total=n_files,
                    faces_found=n_faces,
                    path=str(path),
                    run_id=run_id,
                    outcome=outcome,
                    elapsed_s=now - t0,
                ),
            )

    def persist_still_record(
        *,
        path: Path,
        digest: str,
        media_id: str | None,
        mtime_ns: int,
        byte_size: int,
        img0,
        faces: list,
    ) -> None:
        nonlocal n_media, n_faces, n_ok, n_lq, n_rej, dirty
        if img0 is None:
            tick(path, "failed", force=True)
            return
        h, w = img0.shape[:2]
        if media_id is None:
            media_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO media(media_id, source_type, path, sha256, width, height,
                   mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)""",
                (media_id, "folder", str(path), digest, w, h, mtime_ns, byte_size),
            )
            n_media += 1
            dirty += 1

        obs_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
            (obs_id, media_id, None, None, run_id),
        )
        dirty += 1

        nf, nok, nlq, nrej = _persist_faces(
            conn, obs_id=obs_id, run_id=run_id, pack_id=pid, faces=faces
        )
        n_faces += nf
        n_ok += nok
        n_lq += nlq
        n_rej += nrej
        dirty += max(nf, 1)
        if extra_observers:
            observe_bgr(
                conn,
                observation_id=obs_id,
                run_id=run_id,
                img=img0,
                observers=extra_observers,
            )
            dirty += 1
        maybe_commit()
        tick(path, "processed")

    # --- stills: hash → skip → bounded decode/embed workers ---
    if workers == 1:
        for index, path in enumerate(files, start=1):
            if want_cancel():
                cancelled = True
                break
            try:
                digest, data, mtime_ns, byte_size = _read_and_hash(path)
            except OSError:
                n_fail += 1
                tick(path, "failed", force=True)
                continue
            reason, media_id = media_skip_reason(conn, digest, run_id, reprocess=reprocess)
            if reason == "seen":
                n_skip_seen += 1
                tick(path, "skipped_seen")
                continue
            if reason == "same_run":
                n_skip_same += 1
                tick(path, "skipped_same_run")
                continue
            img0 = _decode_bgr(data, path)
            if img0 is None:
                n_fail += 1
                tick(path, "failed", force=True)
                continue
            try:
                if want_cancel():
                    cancelled = True
                    break
                faces = embed_bgr(app, img0)
            except Exception:
                n_fail += 1
                dirty += 1
                maybe_commit(force=True)
                tick(path, "failed", force=True)
                continue
            persist_still_record(
                path=path,
                digest=digest,
                media_id=media_id,
                mtime_ns=mtime_ns,
                byte_size=byte_size,
                img0=img0,
                faces=faces,
            )
            if want_cancel():
                cancelled = True
                break
    else:
        infer_limit = max(workers * 2, workers)
        pending_infer: set = set()
        infer_meta: dict = {}

        def _drain_infer_once() -> None:
            nonlocal pending_infer, cancelled, n_fail
            if not pending_infer:
                return
            done, pending_infer = wait(pending_infer, return_when=FIRST_COMPLETED)
            for fut in done:
                meta = infer_meta.pop(fut, None)
                if meta is None:
                    continue
                path = meta["path"]
                if want_cancel():
                    cancelled = True
                    continue
                try:
                    rec = fut.result()
                except Exception:
                    n_fail += 1
                    tick(path, "failed", force=True)
                    continue
                if not rec.get("ok"):
                    n_fail += 1
                    tick(path, "failed", force=True)
                    continue
                persist_still_record(
                    path=path,
                    digest=meta["digest"],
                    media_id=meta["media_id"],
                    mtime_ns=meta["mtime_ns"],
                    byte_size=meta["byte_size"],
                    img0=rec.get("img"),
                    faces=rec.get("faces") or [],
                )

        with ThreadPoolExecutor(max_workers=workers) as infer_pool:
            for rec in _iter_hash_results(files, workers=workers, want_cancel=want_cancel):
                if want_cancel():
                    cancelled = True
                    break
                path = Path(rec["path"])
                if rec.get("outcome") == "failed":
                    n_fail += 1
                    tick(path, "failed", force=True)
                    continue
                digest = rec["digest"]
                reason, media_id = media_skip_reason(conn, digest, run_id, reprocess=reprocess)
                if reason == "seen":
                    n_skip_seen += 1
                    tick(path, "skipped_seen")
                    continue
                if reason == "same_run":
                    n_skip_same += 1
                    tick(path, "skipped_same_run")
                    continue
                fut = infer_pool.submit(
                    _infer_still,
                    path=path,
                    data=None,
                    det_size=DET_SIZE,
                    prefer_gpu=prefer_gpu,
                )
                pending_infer.add(fut)
                infer_meta[fut] = {
                    "path": path,
                    "digest": digest,
                    "media_id": media_id,
                    "mtime_ns": rec["mtime_ns"],
                    "byte_size": rec["byte_size"],
                }
                while len(pending_infer) >= infer_limit:
                    _drain_infer_once()
                    if cancelled:
                        break
                if cancelled:
                    break

            while pending_infer and not cancelled:
                _drain_infer_once()

            if cancelled and pending_infer:
                for fut in pending_infer:
                    fut.cancel()
                pending_infer.clear()
                infer_meta.clear()

    # --- videos: hash → skip → stream frames (never list()) ---
    for offset, path in enumerate(videos, start=1):
        if cancelled:
            break
        if want_cancel():
            cancelled = True
            break
        try:
            digest = _sha256_file(path)
            st = path.stat()
            mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
            byte_size = st.st_size
        except OSError:
            n_fail += 1
            tick(path, "failed", force=True)
            continue

        reason, media_id = media_skip_reason(conn, digest, run_id, reprocess=reprocess)
        if reason == "seen":
            n_skip_seen += 1
            tick(path, "skipped_seen")
            continue
        if reason == "same_run":
            n_skip_same += 1
            tick(path, "skipped_same_run")
            continue

        width = height = None
        frames_ok = 0
        try:
            for frame_id, t_ms, img in iter_sampled_frames(path, DEFAULT_SAMPLE_HZ):
                if want_cancel():
                    cancelled = True
                    break
                if width is None:
                    height, width = img.shape[:2]
                    if media_id is None:
                        media_id = uuid.uuid4().hex
                        conn.execute(
                            """INSERT INTO media(media_id, source_type, path, sha256, width, height,
                               mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)""",
                            (
                                media_id,
                                "video",
                                str(path),
                                digest,
                                width,
                                height,
                                mtime_ns,
                                byte_size,
                            ),
                        )
                        n_media += 1
                        dirty += 1
                obs_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
                    (obs_id, media_id, int(frame_id), int(t_ms), run_id),
                )
                dirty += 1
                try:
                    faces = embed_bgr(app, img)
                except Exception:
                    continue
                nf, nok, nlq, nrej = _persist_faces(
                    conn, obs_id=obs_id, run_id=run_id, pack_id=pid, faces=faces
                )
                n_faces += nf
                n_ok += nok
                n_lq += nlq
                n_rej += nrej
                dirty += max(nf, 1)
                frames_ok += 1
                maybe_commit()
        except VideoError:
            n_fail += 1
            maybe_commit(force=True)
            tick(path, "failed", force=True)
            continue

        if width is None and media_id is None:
            # No frames decoded — insert media row with null dims so hash skip works later.
            media_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO media(media_id, source_type, path, sha256, width, height,
                   mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)""",
                (media_id, "video", str(path), digest, None, None, mtime_ns, byte_size),
            )
            n_media += 1
            dirty += 1

        n_video_frames += frames_ok
        maybe_commit(force=True)
        if cancelled:
            tick(path, "cancelled", force=True)
        elif frames_ok == 0:
            n_fail += 1
            tick(path, "failed", force=True)
        else:
            tick(path, "processed", force=True)

    maybe_commit(force=True)

    if videos and not cancelled:
        persist_derived_tracks(store, run_id, conn=conn)

    timings = {
        "model_load_s": load_s,
        "ingest_s": time.perf_counter() - t0,
        "files": n_files,
        "stills": len(files),
        "videos": len(videos),
        "video_frames": n_video_frames,
        "new_media": n_media,
        "skipped": n_skip_seen + n_skip_same,
        "skipped_seen": n_skip_seen,
        "skipped_same_run": n_skip_same,
        "faces": n_faces,
        "ok": n_ok,
        "low_quality": n_lq,
        "rejected": n_rej,
        "failed": n_fail,
        "incremental": not reprocess,
        "workers": int(workers),
        "hash_workers": int(workers),
        "inference_workers": int(workers),
        "observers": list(observer_list),
        "gpu": ep["gpu"],
        "execution_provider": ep["chosen"],
        "cancelled": bool(cancelled),
    }
    if n_files and timings["ingest_s"] > 0:
        images_per_s = n_files / timings["ingest_s"]
        timings["images_per_second"] = round(images_per_s, 4)
        timings["seconds_per_image"] = round(1.0 / images_per_s, 6) if images_per_s > 0 else None
    if timings["ingest_s"] > 0:
        if n_faces <= 0:
            timings["faces_per_second"] = 0.0
            timings["seconds_per_face"] = None
            # keep key presence stable for reporting pipelines
            faces_per_s = None
        else:
            faces_per_s = n_faces / timings["ingest_s"]
            timings["faces_per_second"] = round(faces_per_s, 4)
            timings["seconds_per_face"] = round(1.0 / faces_per_s, 6) if faces_per_s > 0 else None
    notes = "cancelled" if cancelled else None
    conn.execute(
        "UPDATE runs SET finished_at=?, timings_json=?, notes=? WHERE run_id=?",
        (datetime.now(timezone.utc).isoformat(), json.dumps(timings), notes, run_id),
    )
    conn.commit()
    conn.close()
    counts = {
        "new_media": n_media,
        "skipped_seen": n_skip_seen,
        "skipped_same_run": n_skip_same,
        "ok": n_ok,
        "low_quality": n_lq,
        "rejected": n_rej,
        "failed": n_fail,
    }
    if cancelled:
        done = completed
        if done > 0 or n_faces > 0:
            emit(
                on_event,
                make_event(
                    STAGE_INGEST,
                    KIND_PARTIAL,
                    current=done,
                    total=n_files,
                    files_processed=done,
                    files_total=n_files,
                    faces_found=n_faces,
                    run_id=run_id,
                    elapsed_s=timings["ingest_s"],
                    message="partial",
                    outcome="partial",
                    counts=counts,
                ),
            )
        emit(
            on_event,
            make_event(
                STAGE_INGEST,
                KIND_CANCELLED,
                current=done,
                total=n_files,
                files_processed=done,
                files_total=n_files,
                faces_found=n_faces,
                run_id=run_id,
                elapsed_s=timings["ingest_s"],
                message="cancelled",
                outcome="cancelled",
                counts=counts,
            ),
        )
        _restore_sig()
        raise CancelledError("ingest cancelled", run_id=run_id, timings=timings)
    _restore_sig()
    emit(
        on_event,
        make_event(
            STAGE_INGEST,
            KIND_COMPLETED,
            current=n_files,
            total=n_files,
            files_processed=n_files,
            files_total=n_files,
            faces_found=n_faces,
            run_id=run_id,
            elapsed_s=timings["ingest_s"],
            counts=counts,
        ),
    )
    return {"run_id": run_id, "pack_id": pid, **timings}
