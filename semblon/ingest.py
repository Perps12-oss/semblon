"""0.2 ingest: folder of stills → media / observations / faces. No cluster."""

from __future__ import annotations

import json
import os
import platform
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from semblon import __version__
from semblon.engine import (
    PACK_FAMILY,
    discover_weight_hashes,
    embed_image,
    load_app,
    pack_id,
    _sha256_file,
)
from semblon.store import connect, init_db

STILL_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DET_SCORE_MIN = 0.60
CLUSTER_MIN_SIDE = 80
DET_SIZE = (640, 640)


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
    m = platform.machine().lower()
    if m in {"amd64", "x86_64"}:
        return "x64"
    if m in {"arm64", "aarch64"}:
        return "arm64"
    return m


def _execution() -> str:
    proc = platform.machine().lower()
    if proc in {"amd64", "x86_64"}:
        if os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() == "ARM64":
            return "emulated"
        return "native"
    if proc in {"arm64", "aarch64"}:
        return "native"
    return "unknown"


def ingest(folder: Path, store: Path) -> dict:
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(folder)

    conn = connect(store)
    init_db(conn)

    import insightface
    import onnxruntime as ort

    t_load = time.perf_counter()
    app = load_app(DET_SIZE)
    load_s = time.perf_counter() - t_load
    hashes = discover_weight_hashes()
    ifver = getattr(insightface, "__version__", "unknown")
    pid = pack_id(ifver, hashes)

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
        "workers": 1,
        "embed_batch": 1,
        "model_load_s": round(load_s, 3),
        "software_version": __version__,
    }
    config = {
        "det_score_min": DET_SCORE_MIN,
        "cluster_min_side": CLUSTER_MIN_SIDE,
        "det_size": list(DET_SIZE),
        "folder": str(folder),
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

    files = sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in STILL_EXT
    )
    n_media = n_skip = n_faces = n_ok = n_lq = n_rej = n_fail = 0
    t0 = time.perf_counter()

    for path in files:
        try:
            digest = _sha256_file(path)
        except OSError:
            n_fail += 1
            continue

        row = conn.execute("SELECT media_id FROM media WHERE sha256=?", (digest,)).fetchone()
        if row:
            media_id = row[0]
            exists = conn.execute(
                "SELECT 1 FROM observations WHERE media_id=? AND run_id=? AND frame_id IS NULL",
                (media_id, run_id),
            ).fetchone()
            if exists:
                n_skip += 1
                continue
        else:
            img0 = cv2.imread(str(path))
            if img0 is None:
                n_fail += 1
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
            continue

        for f in faces:
            fw, fh = f["face_w"], f["face_h"]
            score = f["det_score"]
            band = size_band(fw, fh)
            if score < DET_SCORE_MIN:
                status, blob, pack, dim = "rejected", None, None, None
                n_rej += 1
            else:
                vec = np.asarray(f["embedding"], dtype=np.float32)
                blob, pack, dim = vec.tobytes(), pid, int(vec.size)
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
        conn.commit()

    timings = {
        "model_load_s": load_s,
        "ingest_s": time.perf_counter() - t0,
        "files": len(files),
        "new_media": n_media,
        "skipped": n_skip,
        "faces": n_faces,
        "ok": n_ok,
        "low_quality": n_lq,
        "rejected": n_rej,
        "failed": n_fail,
    }
    conn.execute(
        "UPDATE runs SET finished_at=?, timings_json=? WHERE run_id=?",
        (datetime.now(timezone.utc).isoformat(), json.dumps(timings), run_id),
    )
    conn.commit()
    conn.close()
    return {"run_id": run_id, "pack_id": pid, **timings}
