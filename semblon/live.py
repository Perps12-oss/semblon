"""Live webcam / RTSP sampling. source_type=live. Cancellable. Not identity."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from semblon.engine import embed_bgr, pack_id, process_arch, process_execution, select_execution_provider
from semblon.ingest import CancelledError, _persist_faces
from semblon.progress import KIND_CANCELLED, KIND_COMPLETED, KIND_PROGRESS, KIND_STARTED, emit, make_event
from semblon.store import connect, init_db
from semblon import __version__


class LiveError(ValueError):
    pass


def _open_capture(source):
    import cv2

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise LiveError(f"cannot open live source: {source}")
    return cap


def live_capture(
    store: Path,
    *,
    source: str | int = 0,
    seconds: float = 5.0,
    sample_hz: float = 1.0,
    cancel=None,
    on_event=None,
    prefer_gpu: bool = False,
    capture_factory=None,
) -> dict:
    """Sample frames from webcam index or RTSP URL into the store as live media."""
    store = Path(store)
    src = int(source) if str(source).isdigit() else str(source)
    factory = capture_factory or _open_capture
    cap = factory(src)
    conn = connect(store)
    init_db(conn)
    import insightface
    import onnxruntime as ort

    from semblon.engine import discover_weight_hashes
    from semblon.providers import FaceKitProvider

    ep = select_execution_provider(prefer_gpu=prefer_gpu)
    # Load first so a cold download is hashed into pack_id, not sha256:unhashed.
    app = FaceKitProvider().load((640, 640), prefer_gpu=prefer_gpu).app
    pid = pack_id(
        getattr(insightface, "__version__", "unknown"),
        discover_weight_hashes(),
    )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution, ort_version)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id,
            datetime.now(timezone.utc).isoformat(),
            __version__,
            pid,
            512,
            "l2",
            json.dumps({"source": str(src), "sample_hz": sample_hz, "seconds": seconds, "kind": "live"}),
            json.dumps({"execution_provider": ep["chosen"], "gpu": ep["gpu"], "device": ep["device"]}),
            process_arch(),
            process_execution(),
            getattr(ort, "__version__", None),
        ),
    )
    media_id = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO media(media_id, source_type, path, sha256, width, height, mtime_ns, byte_size)
           VALUES (?,?,?,?,?,?,?,?)""",
        (media_id, "live", str(src), uuid.uuid4().hex, None, None, 0, 0),
    )
    conn.commit()
    emit(on_event, make_event("live", KIND_STARTED, run_id=run_id, path=str(src)))
    interval = 1.0 / max(0.1, float(sample_hz))
    t0 = datetime.now(timezone.utc).timestamp()
    n_frames = 0
    n_faces = 0
    idx = 0
    import time

    try:
        while True:
            if cancel is not None:
                try:
                    if cancel():
                        emit(on_event, make_event("live", KIND_CANCELLED, run_id=run_id))
                        raise CancelledError("live cancelled", run_id=run_id)
                except CancelledError:
                    raise
                except Exception:
                    pass
            elapsed = datetime.now(timezone.utc).timestamp() - t0
            if elapsed >= float(seconds):
                break
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(interval)
                continue
            t_ms = int(elapsed * 1000)
            obs_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
                (obs_id, media_id, idx, t_ms, run_id),
            )
            try:
                faces = embed_bgr(app, frame)
            except Exception:
                faces = []
            nf, *_ = _persist_faces(conn, obs_id=obs_id, run_id=run_id, pack_id=pid, faces=faces)
            n_faces += nf
            n_frames += 1
            idx += 1
            conn.commit()
            emit(
                on_event,
                make_event("live", KIND_PROGRESS, current=n_frames, run_id=run_id, faces_found=n_faces),
            )
            time.sleep(interval)
    finally:
        try:
            cap.release()
        except Exception:
            pass
    conn.execute(
        "UPDATE runs SET finished_at=?, timings_json=? WHERE run_id=?",
        (
            datetime.now(timezone.utc).isoformat(),
            json.dumps({"frames": n_frames, "faces": n_faces, "seconds": seconds}),
            run_id,
        ),
    )
    conn.commit()
    conn.close()
    emit(on_event, make_event("live", KIND_COMPLETED, run_id=run_id, current=n_frames, faces_found=n_faces))
    return {"run_id": run_id, "frames": n_frames, "faces": n_faces, "source_type": "live", "media_id": media_id}
