"""0.2 ingest: folder of stills (+ S7a sampled video) → media / observations / faces. No cluster.

Optional experimental --workers > 1: thread-local FaceAnalysis for stills only,
single SQLite writer. Video sampling stays sequential on the main thread.
Does not change detection/quality thresholds or pack/provider.
"""

from __future__ import annotations

import json
import platform
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from semblon import __version__
from semblon.engine import (
    PACK_FAMILY,
    discover_weight_hashes,
    embed_bgr,
    embed_image,
    load_app,
    pack_id,
    process_arch,
    process_execution,
    _sha256_file,
)
from semblon.progress import (
    KIND_COMPLETED,
    KIND_PROGRESS,
    KIND_STARTED,
    STAGE_DISCOVER,
    STAGE_INGEST,
    ProgressCallback,
    emit,
    make_event,
)
from semblon.store import connect, init_db
from semblon.temporal import (
    DEFAULT_SAMPLE_HZ,
    VideoError,
    discover_videos,
    iter_sampled_frames,
)

STILL_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DET_SCORE_MIN = 0.60
CLUSTER_MIN_SIDE = 80
DET_SIZE = (640, 640)

_thread_local = threading.local()


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


def discover_stills(folder: Path) -> list[Path]:
    """Sorted still paths under folder. Same filter ingest has always used."""
    folder = Path(folder)
    return sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in STILL_EXT
    )


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


def _worker_app():
    app = getattr(_thread_local, "app", None)
    if app is None:
        app = load_app(DET_SIZE)
        _thread_local.app = app
    return app


def _compute_file(path: Path, index: int) -> dict:
    """Hash + decode dims + embed. No SQLite. Used by workers>1 stills path."""
    try:
        digest = _sha256_file(path)
    except OSError:
        return {"index": index, "path": path, "outcome": "failed", "error": "hash"}

    img0 = cv2.imread(str(path))
    if img0 is None:
        return {
            "index": index,
            "path": path,
            "digest": digest,
            "outcome": "failed",
            "error": "decode",
        }
    h, w = img0.shape[:2]
    st = path.stat()
    try:
        faces = embed_image(_worker_app(), path)
    except Exception:
        return {
            "index": index,
            "path": path,
            "digest": digest,
            "width": w,
            "height": h,
            "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
            "byte_size": st.st_size,
            "outcome": "failed",
            "error": "embed",
        }
    return {
        "index": index,
        "path": path,
        "digest": digest,
        "width": w,
        "height": h,
        "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
        "byte_size": st.st_size,
        "faces": faces,
        "outcome": "ok",
    }


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
        conn.execute(
            """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
               det_score, face_w, face_h, size_band, embedding, embedding_pack, embedding_dim, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                uuid.uuid4().hex, obs_id, run_id, x1, y1, x2, y2,
                score, fw, fh, band, blob, pack, dim, status,
            ),
        )
        n_faces += 1
    return n_faces, n_ok, n_lq, n_rej


def ingest(
    folder: Path,
    store: Path,
    *,
    reprocess: bool = False,
    workers: int = 1,
    on_event: ProgressCallback = None,
) -> dict:
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    if workers < 1:
        raise ValueError("workers must be >= 1")

    conn = connect(store)
    init_db(conn)

    import insightface
    import onnxruntime as ort

    hashes = discover_weight_hashes()
    ifver = getattr(insightface, "__version__", "unknown")
    pid = pack_id(ifver, hashes)

    load_s = 0.0
    app = None
    if workers == 1:
        t_load = time.perf_counter()
        app = load_app(DET_SIZE)
        load_s = time.perf_counter() - t_load

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
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
        "device": "cpu",
        "execution_provider": "CPUExecutionProvider",
        "workers": int(workers),
        "embed_batch": 1,
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
    }
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

    emit(on_event, make_event(STAGE_DISCOVER, KIND_STARTED, path=str(folder), run_id=run_id))
    files = discover_stills(folder)
    videos = discover_videos(folder)
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
    t0 = time.perf_counter()

    def tick(index: int, path: Path, outcome: str) -> None:
        emit(
            on_event,
            make_event(
                STAGE_INGEST,
                KIND_PROGRESS,
                current=index,
                total=n_files,
                files_processed=index,
                files_total=n_files,
                faces_found=n_faces,
                path=str(path),
                run_id=run_id,
                outcome=outcome,
                elapsed_s=time.perf_counter() - t0,
            ),
        )

    def write_computed(rec: dict) -> None:
        nonlocal n_media, n_skip_seen, n_skip_same, n_faces, n_ok, n_lq, n_rej, n_fail
        index = rec["index"]
        path = Path(rec["path"])
        if rec.get("outcome") == "failed" and rec.get("error") == "hash":
            n_fail += 1
            tick(index, path, "failed")
            return

        digest = rec["digest"]
        reason, media_id = media_skip_reason(conn, digest, run_id, reprocess=reprocess)
        if reason == "seen":
            n_skip_seen += 1
            tick(index, path, "skipped_seen")
            return
        if reason == "same_run":
            n_skip_same += 1
            tick(index, path, "skipped_same_run")
            return

        if rec.get("outcome") == "failed":
            if rec.get("error") == "decode":
                n_fail += 1
                tick(index, path, "failed")
                return
            if media_id is None:
                media_id = uuid.uuid4().hex
                conn.execute(
                    """INSERT INTO media(media_id, source_type, path, sha256, width, height,
                       mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        media_id,
                        "folder",
                        str(path),
                        digest,
                        rec["width"],
                        rec["height"],
                        rec["mtime_ns"],
                        rec["byte_size"],
                    ),
                )
                n_media += 1
            obs_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
                (obs_id, media_id, None, None, run_id),
            )
            n_fail += 1
            conn.commit()
            tick(index, path, "failed")
            return

        if media_id is None:
            media_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO media(media_id, source_type, path, sha256, width, height,
                   mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    media_id,
                    "folder",
                    str(path),
                    digest,
                    rec["width"],
                    rec["height"],
                    rec["mtime_ns"],
                    rec["byte_size"],
                ),
            )
            n_media += 1

        obs_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
            (obs_id, media_id, None, None, run_id),
        )
        nf, nok, nlq, nrej = _persist_faces(
            conn, obs_id=obs_id, run_id=run_id, pack_id=pid, faces=rec["faces"]
        )
        n_faces += nf
        n_ok += nok
        n_lq += nlq
        n_rej += nrej
        conn.commit()
        tick(index, path, "processed")

    if workers == 1:
        assert app is not None
        for index, path in enumerate(files, start=1):
            try:
                digest = _sha256_file(path)
            except OSError:
                n_fail += 1
                tick(index, path, "failed")
                continue

            reason, media_id = media_skip_reason(conn, digest, run_id, reprocess=reprocess)
            if reason == "seen":
                n_skip_seen += 1
                tick(index, path, "skipped_seen")
                continue
            if reason == "same_run":
                n_skip_same += 1
                tick(index, path, "skipped_same_run")
                continue
            if media_id is None:
                img0 = cv2.imread(str(path))
                if img0 is None:
                    n_fail += 1
                    tick(index, path, "failed")
                    continue
                h, w = img0.shape[:2]
                media_id = uuid.uuid4().hex
                st = path.stat()
                conn.execute(
                    """INSERT INTO media(media_id, source_type, path, sha256, width, height,
                       mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        media_id,
                        "folder",
                        str(path),
                        digest,
                        w,
                        h,
                        getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
                        st.st_size,
                    ),
                )
                n_media += 1

            obs_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
                (obs_id, media_id, None, None, run_id),
            )
            try:
                faces = embed_image(app, path)
            except Exception:
                n_fail += 1
                conn.commit()
                tick(index, path, "failed")
                continue

            nf, nok, nlq, nrej = _persist_faces(
                conn, obs_id=obs_id, run_id=run_id, pack_id=pid, faces=faces
            )
            n_faces += nf
            n_ok += nok
            n_lq += nlq
            n_rej += nrej
            conn.commit()
            tick(index, path, "processed")
    else:
        # Warm one FaceAnalysis per worker thread; wall clock ≈ max load.
        t_load = time.perf_counter()

        def _warm(_i: int) -> float:
            t1 = time.perf_counter()
            _worker_app()
            return time.perf_counter() - t1

        with ThreadPoolExecutor(max_workers=workers) as pool:
            load_each = list(pool.map(_warm, range(workers)))
            load_s = time.perf_counter() - t_load
            runtime["model_load_s"] = round(load_s, 3)
            runtime["model_load_each_s"] = [round(x, 3) for x in load_each]
            conn.execute(
                "UPDATE runs SET runtime_json=? WHERE run_id=?",
                (json.dumps(runtime), run_id),
            )
            conn.commit()

            futures = {
                pool.submit(_compute_file, path, index): index
                for index, path in enumerate(files, start=1)
            }
            for fut in as_completed(futures):
                write_computed(fut.result())

        # Video path needs a main-thread app after worker stills.
        t_load_v = time.perf_counter()
        app = load_app(DET_SIZE)
        load_s = load_s + (time.perf_counter() - t_load_v)
        runtime["model_load_s"] = round(load_s, 3)
        conn.execute(
            "UPDATE runs SET runtime_json=? WHERE run_id=?",
            (json.dumps(runtime), run_id),
        )
        conn.commit()

    n_video_frames = 0
    assert app is not None
    for offset, path in enumerate(videos, start=1):
        index = len(files) + offset
        try:
            digest = _sha256_file(path)
        except OSError:
            n_fail += 1
            tick(index, path, "failed")
            continue

        reason, media_id = media_skip_reason(conn, digest, run_id, reprocess=reprocess)
        if reason == "seen":
            n_skip_seen += 1
            tick(index, path, "skipped_seen")
            continue
        if reason == "same_run":
            n_skip_same += 1
            tick(index, path, "skipped_same_run")
            continue

        st = path.stat()
        width = height = None
        sampled = []
        try:
            sampled = list(iter_sampled_frames(path, DEFAULT_SAMPLE_HZ))
        except VideoError:
            n_fail += 1
            tick(index, path, "failed")
            continue
        if sampled:
            height, width = sampled[0][2].shape[:2]

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
                    getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
                    st.st_size,
                ),
            )
            n_media += 1

        if not sampled:
            n_fail += 1
            conn.commit()
            tick(index, path, "failed")
            continue

        frames_ok = 0
        for frame_id, t_ms, img in sampled:
            obs_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
                (obs_id, media_id, int(frame_id), int(t_ms), run_id),
            )
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
            frames_ok += 1
        n_video_frames += frames_ok
        conn.commit()
        if frames_ok == 0:
            n_fail += 1
            tick(index, path, "failed")
        else:
            tick(index, path, "processed")

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
    }
    if n_files and timings["ingest_s"] > 0:
        timings["images_per_second"] = round(n_files / timings["ingest_s"], 4)
        timings["faces_per_second"] = round(n_faces / timings["ingest_s"], 4)
    conn.execute(
        "UPDATE runs SET finished_at=?, timings_json=? WHERE run_id=?",
        (datetime.now(timezone.utc).isoformat(), json.dumps(timings), run_id),
    )
    conn.commit()
    conn.close()
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
            counts={
                "new_media": n_media,
                "skipped_seen": n_skip_seen,
                "skipped_same_run": n_skip_same,
                "ok": n_ok,
                "low_quality": n_lq,
                "rejected": n_rej,
                "failed": n_fail,
            },
        ),
    )
    return {"run_id": run_id, "pack_id": pid, **timings}
