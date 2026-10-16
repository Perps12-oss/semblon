"""Ingest: folder of stills (+ S7a sampled video) → media / observations / faces. No cluster.

Pipeline: one-pass discover → bounded hash → skip → decode/embed (one FaceAnalysis) →
batched SQLite writer. Video frames stream; never materialize all samples.
Opt-in --workers > 1 parallelizes hashing only (product default 1; cap MAX_WORKERS).
No --batch until batched inference exists.
Does not change detection/quality thresholds or pack/provider.
"""

from __future__ import annotations

import hashlib
import json
import platform
import signal
import sqlite3
import struct
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
    identity_space_mismatch,
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
from semblon.store import connect, delete_observation_tree, init_db, stamp_unfinished_runs, writer_lock
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
# Hard cap: hash-phase ThreadPool only. Product default remains 1.
MAX_WORKERS = 32
# Re-check cancel/pause while a slow hash is in flight (JobEngine._gate).
_HASH_WAIT_S = 0.05
VIDEO_COMPLETE_PROVIDER = "semblon.video_sampling_complete"


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
    except CancelledError:
        raise
    except Exception:
        # Stop the pipeline. Swallowing this used to spin until the folder ended.
        return True


STILL_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
# Refuse a still before the full decode. Caps are resource limits, not identity.
MAX_STILL_BYTES = 256 * 1024 * 1024
MAX_IMAGE_PIXELS = 80_000_000
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
    row = conn.execute("SELECT media_id, source_type FROM media WHERE sha256=?", (digest,)).fetchone()
    if row is None:
        return None, None
    media_id, source_type = row
    any_observation = conn.execute(
        "SELECT 1 FROM observations WHERE media_id=? LIMIT 1",
        (media_id,),
    ).fetchone()
    if any_observation is None:
        return None, media_id

    if source_type == "video":
        same_video_run = conn.execute(
            "SELECT 1 FROM observations WHERE media_id=? AND run_id=? LIMIT 1",
            (media_id, run_id),
        ).fetchone()
        if same_video_run:
            if not video_sampling_complete(conn, media_id, run_id=run_id):
                return None, media_id
            return "same_run", media_id
        if video_sampling_complete(conn, media_id) and not reprocess:
            return "seen", media_id
        return None, media_id
    else:
        same = conn.execute(
            "SELECT 1 FROM observations WHERE media_id=? AND run_id=? AND frame_id IS NULL",
            (media_id, run_id),
        ).fetchone()
        if same:
            return "same_run", media_id
        same_video = conn.execute(
            "SELECT 1 FROM observations WHERE media_id=? AND run_id=? AND frame_id IS NOT NULL",
            (media_id, run_id),
        ).fetchone()
        if same_video:
            return None, media_id

    if not reprocess:
        return "seen", media_id
    return None, media_id


def _remember_path(conn, media_id: str | None, path: Path, mtime_ns: int, byte_size: int) -> bool:
    """Point the stored row at a moved file. A second copy that still has the original stays put."""
    if not media_id:
        return False
    row = conn.execute("SELECT path FROM media WHERE media_id=?", (media_id,)).fetchone()
    if row is None:
        return False
    old = Path(str(row["path"]))
    new = Path(path)
    if old == new:
        return False
    try:
        if old.is_file():
            return False
    except OSError:
        return False
    conn.execute(
        "UPDATE media SET path=?, mtime_ns=?, byte_size=? WHERE media_id=?",
        (str(new), int(mtime_ns), int(byte_size), media_id),
    )
    return True


def video_sampling_complete(conn, media_id: str, *, run_id: str | None = None) -> bool:
    run_filter = " AND i.run_id=?" if run_id is not None else ""
    params = (media_id, VIDEO_COMPLETE_PROVIDER, run_id) if run_id is not None else (
        media_id,
        VIDEO_COMPLETE_PROVIDER,
    )
    rows = conn.execute(
        """SELECT i.payload_json
           FROM observation_items i
           JOIN observations o ON o.observation_id=i.observation_id
           WHERE o.media_id=? AND i.provider=?""" + run_filter,
        params,
    ).fetchall()
    for row in rows:
        try:
            if json.loads(row[0]).get("sampling_complete") is True:
                return True
        except (AttributeError, TypeError, json.JSONDecodeError):
            continue
    return False


def _mark_video_sampling_complete(
    conn, *, media_id: str, run_id: str, frames: int
) -> None:
    row = conn.execute(
        """SELECT observation_id FROM observations
           WHERE media_id=? AND run_id=? ORDER BY frame_id DESC LIMIT 1""",
        (media_id, run_id),
    ).fetchone()
    if row is None:
        return
    payload = json.dumps({"sampling_complete": True, "frames": int(frames)})
    existing = conn.execute(
        """SELECT i.item_id FROM observation_items i
           JOIN observations o ON o.observation_id=i.observation_id
           WHERE o.media_id=? AND i.run_id=? AND i.provider=? LIMIT 1""",
        (media_id, run_id, VIDEO_COMPLETE_PROVIDER),
    ).fetchone()
    if existing is not None:
        conn.execute(
            "UPDATE observation_items SET observation_id=?, payload_json=? WHERE item_id=?",
            (row[0], payload, existing[0]),
        )
        return
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           payload_json) VALUES (?,?,?,?,?,?)""",
        (
            uuid.uuid4().hex,
            row[0],
            run_id,
            "object",
            VIDEO_COMPLETE_PROVIDER,
            payload,
        ),
    )


def _jpeg_sof_pixels(data: bytes) -> int | None:
    """Pixel count from a JPEG SOF, or None if the header is not usable.

    Fill bytes (0xFF) are not markers. Standalone markers have no length.
    """
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    standalone = {0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8}
    i = 2
    n = len(data)
    while i < n:
        if data[i] != 0xFF:
            return None
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            return None
        marker = data[i]
        i += 1
        if marker in (0xD9, 0xDA):
            return None
        if marker in standalone or marker == 0x00:
            continue
        if i + 1 >= n:
            return None
        seglen = int.from_bytes(data[i : i + 2], "big")
        if seglen < 2 or i + seglen > n:
            return None
        if marker in sof and seglen >= 7 and i + 7 <= n:
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            return int(width) * int(height)
        i += seglen
    return None


def _header_pixels(data: bytes) -> int | None:
    """Pixel count from a still header. None means decode, then measure."""
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", data[16:24])
        return int(width) * int(height)
    if len(data) >= 26 and data[:2] == b"BM":
        width, height = struct.unpack("<ii", data[18:26])
        return abs(int(width)) * abs(int(height))
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width * height
        return None
    if data[:2] == b"\xff\xd8":
        return _jpeg_sof_pixels(data)
    return None


def _hash_path(path: Path, index: int) -> dict:
    """One read: SHA-256 and the bytes persist will decode. No embed, no SQLite."""
    try:
        digest, data, mtime_ns, byte_size = _read_and_hash(path)
    except OSError as exc:
        error = "too_large" if "byte cap" in str(exc) else "hash"
        return {"index": index, "path": path, "outcome": "failed", "error": error}
    return {
        "index": index,
        "path": path,
        "digest": digest,
        "data": data,
        "mtime_ns": mtime_ns,
        "byte_size": byte_size,
        "outcome": "hashed",
    }


def _read_and_hash(path: Path) -> tuple[str, bytes, int, int]:
    """One I/O: bytes + sha256 + mtime_ns + byte_size. Refuses oversized stills."""
    st = path.stat()
    size = int(st.st_size)
    if size > MAX_STILL_BYTES:
        raise OSError("still exceeds byte cap")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    return (
        digest,
        data,
        getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
        size,
    )


def _decode_bgr(data: bytes | None, path: Path):
    payload = data
    if not payload:
        try:
            if path.stat().st_size > MAX_STILL_BYTES:
                return None
            payload = path.read_bytes()
        except OSError:
            return cv2.imread(str(path))
    elif len(payload) > MAX_STILL_BYTES:
        return None
    pixels = _header_pixels(payload) if payload else None
    if pixels is not None and pixels > MAX_IMAGE_PIXELS:
        return None
    img = None
    if payload:
        arr = np.frombuffer(payload, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        img = cv2.imread(str(path))
    if img is None:
        return None
    height, width = img.shape[:2]
    if int(height) * int(width) > MAX_IMAGE_PIXELS:
        return None
    return img


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
    """Yield hash records with bounded in-flight futures (max workers*4).

    Cancel/pause is polled on a short wait timeout so JobEngine._gate is not
    stuck behind a single slow SHA-256. On cancel, pending futures are cancelled
    and the pool shuts down with cancel_futures=True (no second SQLite writer —
    hash workers never touch the store).
    """
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
    pool = ThreadPoolExecutor(max_workers=workers)

    def _submit() -> bool:
        try:
            index, path = next(it)
        except StopIteration:
            return False
        pending.add(pool.submit(_hash_path, path, index))
        return True

    def _cancel_pending() -> None:
        for fut in list(pending):
            fut.cancel()
        pending.clear()

    try:
        while len(pending) < limit and _submit():
            pass
        while pending:
            if want_cancel():
                _cancel_pending()
                return
            done, pending = wait(
                pending,
                timeout=_HASH_WAIT_S,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                continue
            for fut in done:
                if want_cancel():
                    _cancel_pending()
                    return
                yield fut.result()
                while len(pending) < limit and _submit():
                    pass
    finally:
        _cancel_pending()
        pool.shutdown(wait=False, cancel_futures=True)


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
    if workers > MAX_WORKERS:
        raise ValueError(f"workers must be <= {MAX_WORKERS}")
    observer_list = tuple(x.strip() for x in str(observers).split(",") if x.strip()) or ("face",)
    extra_observers = tuple(x for x in observer_list if x != "face")

    conn = connect(store)
    init_db(conn)
    _sig_prev = {"fn": None}

    def _restore_installed_sig() -> None:
        prev = _sig_prev["fn"]
        _sig_prev["fn"] = None
        if prev is None:
            return
        try:
            signal.signal(signal.SIGINT, prev)
        except (ValueError, OSError):
            pass

    try:
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
            "opencv_version": cv2.__version__,
            "pack_family": PACK_FAMILY,
            "pack_id": pid,
            "det_size": list(DET_SIZE),
            "device": ep["device"],
            "execution_provider": ep["chosen"],
            "gpu": ep["gpu"],
            "onnx_providers": ep["available"],
            "provider": FaceKitProvider.info.name,
            "modality": FaceKitProvider.info.modality,
            "workers": int(workers),
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
                raise ValueError(f"unknown run: {resume_run_id}")
            mismatch = identity_space_mismatch(
                row["pack_id"],
                row["ort_version"],
                row["runtime_json"],
                live={
                    "pack_id": pid,
                    "ort_version": ort.__version__,
                    "opencv_version": cv2.__version__,
                },
            )
            if mismatch:
                raise ValueError(mismatch)
            run_id = str(row["run_id"])
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

        def _on_sigint(_signum, _frame):
            sigint["hit"] = True

        def want_cancel() -> bool:
            return sigint["hit"] or _cancel_requested(cancel)

        try:
            _sig_prev["fn"] = signal.signal(signal.SIGINT, _on_sigint)
        except (ValueError, OSError):
            _sig_prev["fn"] = None

        def _restore_sig() -> None:
            _restore_installed_sig()

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

        def persist_still(
            *,
            path: Path,
            digest: str,
            media_id: str | None,
            mtime_ns: int,
            byte_size: int,
            data: bytes | None,
        ) -> None:
            nonlocal n_media, n_faces, n_ok, n_lq, n_rej, n_fail, dirty
            if want_cancel():
                return
            with writer_lock():
                maybe_commit(force=True)
            img0 = _decode_bgr(data, path)
            if img0 is None:
                n_fail += 1
                tick(path, "failed", force=True)
                return
            h, w = img0.shape[:2]
            try:
                faces = embed_bgr(app, img0)
            except Exception:
                n_fail += 1
                tick(path, "failed", force=True)
                return

            with writer_lock():
                if media_id is None:
                    media_id = uuid.uuid4().hex
                    conn.execute(
                        """INSERT INTO media(media_id, source_type, path, sha256, width, height,
                           mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)""",
                        (media_id, "folder", str(path), digest, w, h, mtime_ns, byte_size),
                    )
                    n_media += 1
                    dirty += 1
                elif _remember_path(conn, media_id, path, mtime_ns, byte_size):
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
                maybe_commit(force=True)
            tick(path, "processed")

        # --- stills: hash → skip → decode/embed ---
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
                if reason in {"seen", "same_run"}:
                    if _remember_path(conn, media_id, path, mtime_ns, byte_size):
                        dirty += 1
                    if reason == "seen":
                        n_skip_seen += 1
                        tick(path, "skipped_seen")
                    else:
                        n_skip_same += 1
                        tick(path, "skipped_same_run")
                    continue
                persist_still(
                    path=path,
                    digest=digest,
                    media_id=media_id,
                    mtime_ns=mtime_ns,
                    byte_size=byte_size,
                    data=data,
                )
                if want_cancel():
                    cancelled = True
                    break
        else:
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
                if reason in {"seen", "same_run"}:
                    if _remember_path(conn, media_id, path, rec["mtime_ns"], rec["byte_size"]):
                        dirty += 1
                    if reason == "seen":
                        n_skip_seen += 1
                        tick(path, "skipped_seen")
                    else:
                        n_skip_same += 1
                        tick(path, "skipped_same_run")
                    continue
                persist_still(
                    path=path,
                    digest=digest,
                    media_id=media_id,
                    mtime_ns=rec["mtime_ns"],
                    byte_size=rec["byte_size"],
                    data=rec.get("data"),
                )
                if want_cancel():
                    cancelled = True
                    break

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
            if reason in {"seen", "same_run"}:
                if _remember_path(conn, media_id, path, mtime_ns, byte_size):
                    dirty += 1
                if reason == "seen":
                    n_skip_seen += 1
                    tick(path, "skipped_seen")
                else:
                    n_skip_same += 1
                    tick(path, "skipped_same_run")
                continue

            width = height = None
            frames_ok = 0
            frames_sampled = 0
            frames_failed = 0
            try:
                for frame_id, t_ms, img in iter_sampled_frames(path, DEFAULT_SAMPLE_HZ):
                    frames_sampled += 1
                    if want_cancel():
                        cancelled = True
                        break
                    fh, fw = img.shape[:2]
                    if int(fh) * int(fw) > MAX_IMAGE_PIXELS:
                        frames_failed += 1
                        continue
                    existing = None
                    if media_id is not None:
                        row = conn.execute(
                            """SELECT observation_id FROM observations
                               WHERE media_id=? AND frame_id=? AND run_id=?""",
                            (media_id, int(frame_id), run_id),
                        ).fetchone()
                        if row is not None:
                            existing = row[0]
                            have = conn.execute(
                                "SELECT COUNT(*) FROM faces WHERE observation_id=?",
                                (existing,),
                            ).fetchone()[0]
                            if have:
                                frames_ok += 1
                                continue
                    with writer_lock():
                        maybe_commit(force=True)
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
                            maybe_commit(force=True)
                        elif width is not None:
                            conn.execute(
                                "UPDATE media SET width=?, height=? WHERE media_id=? AND width IS NULL",
                                (width, height, media_id),
                            )
                    try:
                        faces = embed_bgr(app, img)
                    except Exception:
                        if existing is not None:
                            with writer_lock():
                                delete_observation_tree(conn, existing)
                                maybe_commit(force=True)
                        frames_failed += 1
                        continue
                    with writer_lock():
                        if existing is None:
                            obs_id = uuid.uuid4().hex
                            conn.execute(
                                "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
                                (obs_id, media_id, int(frame_id), int(t_ms), run_id),
                            )
                            dirty += 1
                        else:
                            obs_id = existing
                            dirty += 1
                        nf, nok, nlq, nrej = _persist_faces(
                            conn, obs_id=obs_id, run_id=run_id, pack_id=pid, faces=faces
                        )
                        n_faces += nf
                        n_ok += nok
                        n_lq += nlq
                        n_rej += nrej
                        dirty += max(nf, 1)
                        frames_ok += 1
                        maybe_commit(force=True)
            except VideoError:
                n_fail += 1
                with writer_lock():
                    maybe_commit(force=True)
                tick(path, "failed", force=True)
                continue

            if (
                frames_sampled
                and not cancelled
                and frames_failed == 0
                and media_id is not None
            ):
                _mark_video_sampling_complete(
                    conn, media_id=media_id, run_id=run_id, frames=frames_sampled
                )
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
            "observers": list(observer_list),
            "gpu": ep["gpu"],
            "cancelled": bool(cancelled),
        }
        if n_files and timings["ingest_s"] > 0:
            timings["images_per_second"] = round(n_files / timings["ingest_s"], 4)
            timings["faces_per_second"] = round(n_faces / timings["ingest_s"], 4)
        notes = "cancelled" if cancelled else None
        conn.execute(
            "UPDATE runs SET finished_at=?, timings_json=?, notes=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), json.dumps(timings), notes, run_id),
        )
        conn.commit()
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
    finally:
        _restore_installed_sig()
        try:
            conn.close()
        except Exception:
            pass
