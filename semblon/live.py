"""Live webcam/RTSP capture engine.

Loop: detect -> associate tracks -> selective embed -> identify vs persons.
Live faces never auto-assign person_id. Live/video remain out of DBSCAN.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from semblon import __version__
from semblon.engine import (
    embed_bgr,
    pack_id,
    process_arch,
    process_execution,
    select_execution_provider,
)
from semblon.eval import DEFAULT_THRESHOLD
from semblon.identify import _decide, _gallery, _person_scores, _write_decision
from semblon.ingest import CancelledError, _persist_faces
from semblon.observers import persist_derived_tracks
from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_PROGRESS,
    KIND_STARTED,
    emit,
    make_event,
)
from semblon.store import connect, init_db
from semblon.track_state import derive_track_states_from_conn
from semblon.tracks import DEFAULT_IOU_MIN, DEFAULT_MAX_T_MS_GAP, _associate_media, bbox_iou


class LiveError(ValueError):
    pass


def _open_capture(source):
    import cv2

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise LiveError(f"cannot open live source: {source}")
    return cap


def _should_cancel(cancel) -> bool:
    if cancel is None:
        return False
    try:
        return bool(cancel())
    except Exception:
        return False


def _detect_faces(app, frame) -> list[dict]:
    """FaceKit detection pass for association. Falls back to embed path if needed."""
    det_model = getattr(app, "det_model", None)
    if det_model is not None and hasattr(det_model, "detect"):
        fn = det_model.detect
        det = None
        try:
            det = fn(frame, max_num=0, metric="default")
        except TypeError:
            det = fn(frame)
        if isinstance(det, tuple):
            bboxes = det[0]
        else:
            bboxes = det
        if bboxes is None:
            return []
        out = []
        for row in bboxes:
            if len(row) < 4:
                continue
            x1, y1, x2, y2 = [float(v) for v in row[:4]]
            score = float(row[4]) if len(row) >= 5 else 1.0
            out.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "det_score": score,
                    "face_w": max(0, int(round(x2 - x1))),
                    "face_h": max(0, int(round(y2 - y1))),
                }
            )
        return out
    # Compatibility fallback for tests/adapters that only implement embed path.
    faces = embed_bgr(app, frame)
    return [
        {
            "bbox": f["bbox"],
            "det_score": float(f["det_score"]),
            "face_w": int(f["face_w"]),
            "face_h": int(f["face_h"]),
        }
        for f in faces
    ]


def _match_embeddings(
    embedded: list[dict],
    detections: list[dict],
    det_to_track: dict[str, str],
    embed_track_keys: set[str],
) -> tuple[list[dict], list[str]]:
    """Select embeddings for tracks that currently require a persisted embed."""
    selected_faces: list[dict] = []
    selected_track_keys: list[str] = []
    used_det_ids: set[str] = set()
    for face in embedded:
        best_det = None
        best_iou = -1.0
        for det in detections:
            det_id = det["det_id"]
            if det_id in used_det_ids:
                continue
            iou = bbox_iou(face["bbox"], det["bbox"])
            if iou >= DEFAULT_IOU_MIN and iou > best_iou:
                best_iou = iou
                best_det = det
        if best_det is None:
            continue
        used_det_ids.add(best_det["det_id"])
        track_key = det_to_track.get(best_det["det_id"], best_det["det_id"])
        if track_key not in embed_track_keys:
            continue
        selected_faces.append(face)
        selected_track_keys.append(track_key)
    return selected_faces, selected_track_keys


def _identify_persisted_face(conn, *, run_id: str, pack_id_value: str, face_id: str) -> dict:
    face = conn.execute(
        """
        SELECT face_id, embedding, embedding_pack, embedding_dim, status
        FROM faces WHERE face_id=? AND run_id=?
        """,
        (face_id, run_id),
    ).fetchone()
    if face is None or face["status"] != "ok":
        return {"decision": "UNKNOWN", "person_id": None, "display_name": None, "decision_id": None}
    gallery = _gallery(conn, pack_id_value, exclude_face=face_id)
    ranked = _person_scores(face, gallery, pack_id_value)
    verdict = _decide(ranked, DEFAULT_THRESHOLD)
    decision_id = _write_decision(
        conn,
        run_id=run_id,
        pack_id=pack_id_value,
        face_id=face_id,
        verdict=verdict,
        threshold=DEFAULT_THRESHOLD,
        source="live",
    )
    return {
        "decision_id": decision_id,
        "decision": verdict["decision"],
        "person_id": verdict["person_id"],
        "display_name": verdict["display_name"],
        "score_top1": verdict["score_top1"],
        "score_top2": verdict["score_top2"],
        "margin": verdict["margin"],
        "gallery_size": verdict["gallery_size"],
    }


def _apply_retention(
    conn,
    *,
    run_id: str,
    media_id: str,
    keep_after_t_ms: int,
) -> int:
    old_rows = conn.execute(
        """
        SELECT observation_id FROM observations
        WHERE run_id=? AND media_id=? AND t_ms IS NOT NULL AND t_ms < ?
        """,
        (run_id, media_id, keep_after_t_ms),
    ).fetchall()
    obs_ids = [r["observation_id"] for r in old_rows]
    if not obs_ids:
        return 0

    obs_q = ",".join("?" * len(obs_ids))
    face_rows = conn.execute(
        f"SELECT face_id FROM faces WHERE observation_id IN ({obs_q})",
        obs_ids,
    ).fetchall()
    face_ids = [r["face_id"] for r in face_rows]
    if face_ids:
        fq = ",".join("?" * len(face_ids))
        conn.execute(
            f"DELETE FROM decisions WHERE run_id=? AND face_id IN ({fq})",
            (run_id, *face_ids),
        )

    item_rows = conn.execute(
        f"SELECT item_id FROM observation_items WHERE observation_id IN ({obs_q})",
        obs_ids,
    ).fetchall()
    item_ids = [r["item_id"] for r in item_rows]
    if item_ids:
        iq = ",".join("?" * len(item_ids))
        conn.execute(f"DELETE FROM track_members WHERE item_id IN ({iq})", item_ids)
        conn.execute(f"DELETE FROM embeddings WHERE item_id IN ({iq})", item_ids)
        conn.execute(f"DELETE FROM observation_items WHERE item_id IN ({iq})", item_ids)

    if face_ids:
        fq = ",".join("?" * len(face_ids))
        conn.execute(f"DELETE FROM faces WHERE face_id IN ({fq})", face_ids)

    conn.execute(f"DELETE FROM observations WHERE observation_id IN ({obs_q})", obs_ids)
    return len(obs_ids)


def _track_mapping(all_detections: list[dict]) -> tuple[dict[str, str], int]:
    tracks, singles = _associate_media(
        all_detections,
        iou_min=DEFAULT_IOU_MIN,
        max_t_ms_gap=DEFAULT_MAX_T_MS_GAP,
    )
    mapping: dict[str, str] = {}
    for tr in tracks:
        key = tr[0]["face_id"]
        for m in tr:
            mapping[m["face_id"]] = key
    for s in singles:
        mapping[s["face_id"]] = s["face_id"]
    return mapping, len(set(mapping.values()))


def _track_state_counts(track_state: dict[str, dict]) -> dict[str, int]:
    identified = unknown = hypothesis = 0
    for st in track_state.values():
        state = st.get("state", "hypothesis")
        if state == "identified":
            identified += 1
        elif state == "unknown":
            unknown += 1
        else:
            hypothesis += 1
    return {
        "identified": identified,
        "unknown_state": unknown,
        "hypothesis": hypothesis,
    }


def live_capture(
    store: Path,
    *,
    source: str | int = 0,
    seconds: float = 5.0,
    sample_hz: float = 1.0,
    reembed_s: float = 2.0,
    retain_s: float | None = None,
    strict: bool = False,
    cancel=None,
    on_event=None,
    prefer_gpu: bool = False,
    capture_factory=None,
) -> dict:
    """Capture webcam/RTSP: detect -> track -> selective embed -> identify."""
    store = Path(store)
    if sample_hz <= 0:
        raise LiveError("hz must be > 0")
    if seconds < 0:
        raise LiveError("seconds must be >= 0")
    if reembed_s < 0:
        raise LiveError("reembed-s must be >= 0")
    if retain_s is not None and retain_s <= 0:
        raise LiveError("retain-s must be > 0 when provided")

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
    config = {
        "source": str(src),
        "sample_hz": float(sample_hz),
        "seconds": float(seconds),
        "kind": "live",
        "reembed_s": float(reembed_s),
        "retain_s": retain_s,
        "strict": bool(strict),
    }
    runtime = {
        "execution_provider": ep["chosen"],
        "gpu": ep["gpu"],
        "device": ep["device"],
    }
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
            json.dumps(config),
            json.dumps(runtime),
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
    t0 = time.monotonic()
    reembed_ms = int(round(float(reembed_s) * 1000.0))
    retain_ms = None if retain_s is None else int(round(float(retain_s) * 1000.0))

    n_frames = 0
    dropped_frames = 0
    failed_embeds = 0
    embedded = 0
    track_count = 0
    identified_accept = 0
    identified_unknown = 0
    retention_deletes = 0
    idx = 0
    decisions: list[dict] = []

    all_detections: list[dict] = []
    track_state: dict[str, dict] = {}

    def _finish(note: str | None) -> dict:
        timings = {
            "frames": n_frames,
            "dropped_frames": dropped_frames,
            "failed_embeds": failed_embeds,
            "embedded": embedded,
            "tracks": track_count,
            "identified_accept": identified_accept,
            "identified_unknown": identified_unknown,
            "seconds_requested": float(seconds),
            "unbounded": bool(seconds == 0),
            "retention_deleted_observations": retention_deletes,
            "strict": bool(strict),
        }
        conn.execute(
            "UPDATE runs SET finished_at=?, timings_json=?, notes=? WHERE run_id=?",
            (
                datetime.now(timezone.utc).isoformat(),
                json.dumps(timings),
                note,
                run_id,
            ),
        )
        conn.commit()
        return timings

    try:
        while True:
            if _should_cancel(cancel):
                emit(on_event, make_event("live", KIND_CANCELLED, run_id=run_id, message="cancelled"))
                timings = _finish("cancelled")
                conn.close()
                raise CancelledError("live cancelled", run_id=run_id, timings=timings)

            elapsed = time.monotonic() - t0
            if seconds > 0 and elapsed >= float(seconds):
                break

            ok, frame = cap.read()
            if not ok or frame is None:
                dropped_frames += 1
                time.sleep(interval)
                continue

            t_ms = int(round(elapsed * 1000.0))
            obs_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
                (obs_id, media_id, idx, t_ms, run_id),
            )

            try:
                detections_raw = _detect_faces(app, frame)
            except Exception as e:
                failed_embeds += 1
                emit(
                    on_event,
                    make_event(
                        "live",
                        KIND_FAILED,
                        run_id=run_id,
                        current=n_frames + 1,
                        error=str(e),
                        message="detect failed",
                    ),
                )
                conn.commit()
                if strict:
                    _finish("failed")
                    conn.close()
                    raise LiveError(str(e)) from e
                detections_raw = []

            frame_detections: list[dict] = []
            for j, det in enumerate(detections_raw):
                det_id = f"det-{obs_id[:8]}-{j}"
                rec = {
                    "det_id": det_id,
                    "face_id": det_id,
                    "observation_id": obs_id,
                    "media_id": media_id,
                    "path": str(src),
                    "frame_id": idx,
                    "t_ms": t_ms,
                    "bbox": det["bbox"],
                    "face_w": int(det.get("face_w") or 0),
                    "face_h": int(det.get("face_h") or 0),
                    "person_id": None,
                    "cluster_id": None,
                }
                frame_detections.append(rec)
                all_detections.append(rec)

            det_to_track, track_count = _track_mapping(all_detections)
            gallery_named = int(
                conn.execute("SELECT COUNT(*) FROM persons WHERE status='active'").fetchone()[0]
            )
            no_active_tracks = len(track_state) == 0
            embed_track_keys: set[str] = set()
            for det in frame_detections:
                track_key = det_to_track.get(det["det_id"], det["det_id"])
                state = track_state.setdefault(
                    track_key,
                    {
                        "last_seen_t_ms": None,
                        "last_embed_t_ms": None,
                        "has_decision": False,
                        "state": "hypothesis",
                        "person_id": None,
                        "display_name": None,
                    },
                )
                is_new_track = state["last_seen_t_ms"] is None
                state["last_seen_t_ms"] = t_ms
                stale = (
                    state["last_embed_t_ms"] is None
                    or (reembed_ms == 0 or (t_ms - int(state["last_embed_t_ms"])) >= reembed_ms)
                )
                needs_decision = bool(gallery_named >= 1 and not state["has_decision"])
                should_embed = no_active_tracks or is_new_track or stale or needs_decision
                if should_embed:
                    embed_track_keys.add(track_key)

            if frame_detections and embed_track_keys:
                try:
                    embedded_raw = embed_bgr(app, frame)
                except Exception as e:
                    failed_embeds += 1
                    emit(
                        on_event,
                        make_event(
                            "live",
                            KIND_FAILED,
                            run_id=run_id,
                            current=n_frames + 1,
                            error=str(e),
                            message="embed failed",
                        ),
                    )
                    conn.commit()
                    if strict:
                        _finish("failed")
                        conn.close()
                        raise LiveError(str(e)) from e
                    embedded_raw = []

                selected_faces, selected_track_keys = _match_embeddings(
                    embedded_raw,
                    frame_detections,
                    det_to_track,
                    embed_track_keys,
                )
                if selected_faces:
                    _persist_faces(conn, obs_id=obs_id, run_id=run_id, pack_id=pid, faces=selected_faces)
                    inserted = conn.execute(
                        """
                        SELECT face_id, status FROM faces
                        WHERE observation_id=?
                        ORDER BY rowid
                        """,
                        (obs_id,),
                    ).fetchall()
                    embedded += len(inserted)
                    for i, row in enumerate(inserted):
                        if i >= len(selected_track_keys):
                            break
                        track_key = selected_track_keys[i]
                        state = track_state.setdefault(
                            track_key,
                            {
                                "last_seen_t_ms": t_ms,
                                "last_embed_t_ms": None,
                                "has_decision": False,
                                "state": "hypothesis",
                                "person_id": None,
                                "display_name": None,
                            },
                        )
                        if row["status"] != "ok":
                            continue
                        state["last_embed_t_ms"] = t_ms
                        ident = _identify_persisted_face(
                            conn,
                            run_id=run_id,
                            pack_id_value=pid,
                            face_id=row["face_id"],
                        )
                        state["has_decision"] = True
                        if ident["decision"] == "ACCEPT":
                            identified_accept += 1
                            state["state"] = "identified"
                            state["person_id"] = ident["person_id"]
                            state["display_name"] = ident["display_name"]
                        else:
                            identified_unknown += 1
                            if state.get("state") != "identified":
                                state["state"] = "unknown"
                        decisions.append(
                            {
                                "track_id": track_key,
                                "face_id": row["face_id"],
                                "decision_id": ident["decision_id"],
                                "decision": ident["decision"],
                                "person_id": ident["person_id"],
                                "display_name": ident["display_name"],
                            }
                        )
            if retain_ms is not None:
                retention_deletes += _apply_retention(
                    conn,
                    run_id=run_id,
                    media_id=media_id,
                    keep_after_t_ms=max(0, t_ms - retain_ms),
                )

            conn.commit()
            persist_derived_tracks(store, run_id, conn=conn)
            n_frames += 1
            idx += 1
            emit(
                on_event,
                make_event(
                    "live",
                    KIND_PROGRESS,
                    run_id=run_id,
                    current=n_frames,
                    faces_found=embedded,
                    counts={
                        "detected": len(frame_detections),
                        "embedded": embedded,
                        "tracks": track_count,
                        "accept": identified_accept,
                        "unknown": identified_unknown,
                        **_track_state_counts(track_state),
                        "failed_embeds": failed_embeds,
                    },
                ),
            )
            time.sleep(interval)
    except KeyboardInterrupt as e:
        emit(on_event, make_event("live", KIND_CANCELLED, run_id=run_id, message="cancelled"))
        timings = _finish("cancelled")
        conn.close()
        raise CancelledError("live cancelled", run_id=run_id, timings=timings) from e
    except Exception:
        try:
            conn.close()
        except Exception as close_err:
            _ = close_err
        raise
    finally:
        try:
            cap.release()
        except Exception as release_err:
            _ = release_err

    if n_frames == 0:
        emit(
            on_event,
            make_event(
                "live",
                KIND_FAILED,
                run_id=run_id,
                error="no frames captured",
                message="no frames captured",
            ),
        )
        _finish("failed")
        conn.close()
        raise LiveError("no frames captured")

    tracks_rec = persist_derived_tracks(store, run_id, conn=conn)
    track_states = derive_track_states_from_conn(conn, run_id)
    timings = _finish(None)
    conn.close()
    emit(
        on_event,
        make_event(
            "live",
            KIND_COMPLETED,
            run_id=run_id,
            current=n_frames,
            faces_found=embedded,
            counts={
                "frames": n_frames,
                "embedded": embedded,
                "tracks": int(tracks_rec.get("tracks") or track_count),
                "accept": identified_accept,
                "unknown": identified_unknown,
                "state_identified": track_states["counts"]["identified"],
                "state_unknown": track_states["counts"]["unknown"],
                "state_hypothesis": track_states["counts"]["hypothesis"],
                "failed_embeds": failed_embeds,
                "dropped_frames": dropped_frames,
            },
        ),
    )
    return {
        "run_id": run_id,
        "media_id": media_id,
        "source_type": "live",
        "frames": n_frames,
        "dropped_frames": dropped_frames,
        "failed_embeds": failed_embeds,
        "embedded": embedded,
        "tracks": int(tracks_rec.get("tracks") or track_count),
        "identified_accept": identified_accept,
        "identified_unknown": identified_unknown,
        "decisions": decisions,
        "track_states": track_states,
        "seconds_requested": float(seconds),
        "unbounded": bool(seconds == 0),
        "timings": timings,
        "note": "live: detection -> track -> identity evidence; track != person",
    }
