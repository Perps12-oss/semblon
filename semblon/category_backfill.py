"""Category-specific full-library backfill.

One archive. One category per run. This module does not call process_folder,
does not set reprocess, and does not stamp the shared observe tier.

People writes face detections and embeddings only. It does not write persons
or faces.person_id and it does not cluster. Objects runs NanoDet only.
Regions runs the existing DINOv2 frame and detail index only. Words runs OCR only.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from semblon.progress import ProgressEvent
from semblon.store import connect, init_db, writer_lock

CATEGORY_PEOPLE = "people"
CATEGORY_OBJECTS = "objects"
CATEGORY_REGIONS = "regions"
CATEGORY_WORDS = "words"
CATEGORIES = (CATEGORY_PEOPLE, CATEGORY_OBJECTS, CATEGORY_REGIONS, CATEGORY_WORDS)

STATE_PENDING = "pending"
STATE_RUNNING = "running"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"
STATE_UNAVAILABLE = "unavailable"
STATE_INTERRUPTED = "interrupted"
STATE_SKIPPED = "skipped"

_LABELS = {
    CATEGORY_PEOPLE: "People",
    CATEGORY_OBJECTS: "Objects",
    CATEGORY_REGIONS: "Regions",
    CATEGORY_WORDS: "Words in photos",
}
_STILL_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_UNFINISHED = {STATE_PENDING, STATE_FAILED, STATE_INTERRUPTED, STATE_RUNNING}


@dataclass(frozen=True)
class ProviderProbe:
    available: bool
    provider_id: str
    provider_version: str
    reason: str = ""


@dataclass(frozen=True)
class ItemResult:
    state: str
    outcome: str
    error: str = ""
    frame_done: int = 0
    detail_done: int = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _label(category: str) -> str:
    return _LABELS.get(category, category)


def decode_image(path: Path):
    """Decode one still. None means the file could not be read."""
    from semblon.ingest import _decode_bgr

    return _decode_bgr(None, Path(path))


def people_detect(img) -> list[dict]:
    """YuNet + SFace on one image. No store writes."""
    from semblon.engine import embed_bgr, load_app

    app = load_app()
    return embed_bgr(app, img)


def objects_detect(img) -> list[dict]:
    """NanoDet labels only. Contours are not object labels."""
    from semblon.object_nanodet import detect_objects

    return detect_objects(img)


def regions_prepare(img, *, depth: str, cancelled):
    """DINOv2 prepare step. Persistence is separate so the lock stays short."""
    from semblon.region_encoder import prepare_region_index

    return prepare_region_index(img, depth=depth, cancelled=cancelled)


def words_ocr(img) -> dict | None:
    """OCR one image. None means the provider is missing."""
    from semblon.observers import ocr_image

    return ocr_image(img)


def probe_category(category: str) -> ProviderProbe:
    """Provider readiness for one category. Does not download weights."""
    if category == CATEGORY_PEOPLE:
        from semblon.engine import discover_weight_hashes, pack_id
        import cv2

        hashes = discover_weight_hashes()
        if not hashes:
            return ProviderProbe(
                False,
                "yunet_sface",
                "",
                "Face checking needs the face files already on this computer. Nothing was downloaded.",
            )
        version = pack_id(f"opencv-{cv2.__version__}", hashes)
        return ProviderProbe(True, "yunet_sface", version, "")
    if category == CATEGORY_OBJECTS:
        from semblon.object_pack import PROVIDER, probe_nanodet_status

        ready, note = probe_nanodet_status()
        if not ready:
            return ProviderProbe(
                False,
                PROVIDER,
                "",
                note or "Object labels need the optional object files on this computer. Nothing was downloaded.",
            )
        from semblon.object_pack import assert_nanodet_pack_ready

        meta = assert_nanodet_pack_ready()
        return ProviderProbe(True, PROVIDER, str(meta.get("sha256") or "")[:16], "")
    if category == CATEGORY_REGIONS:
        from semblon.region_encoder import PROVIDER, active_pack, probe_region_pack

        ready, note = probe_region_pack()
        if not ready:
            return ProviderProbe(
                False,
                PROVIDER,
                "",
                note or "Finding by look needs the region files already on this computer. Nothing was downloaded.",
            )
        packed = active_pack()
        version = packed[0] if packed else ""
        if not version:
            return ProviderProbe(False, PROVIDER, "", "Finding by look is not ready on this computer.")
        return ProviderProbe(True, PROVIDER, version, "")
    if category == CATEGORY_WORDS:
        from semblon.observers import OCR_PROVIDER, probe_ocr_status

        ready, note = probe_ocr_status()
        if not ready:
            return ProviderProbe(
                False,
                OCR_PROVIDER,
                "",
                note or "Reading words in photos needs the text reader already installed. Nothing was downloaded.",
            )
        version = "tesseract"
        try:
            import pytesseract

            version = f"tesseract/{pytesseract.get_tesseract_version()}"
        except Exception:
            version = "tesseract"
        return ProviderProbe(True, OCR_PROVIDER, version, "")
    raise ValueError(f"unknown category: {category}")


def _open_run(conn, *, pack_id: str, dim: int, category: str) -> str:
    from semblon import __version__

    run_id = _now().replace(":", "").replace("-", "")[:15] + "-" + uuid.uuid4().hex[:8]
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id,
            _now(),
            __version__,
            pack_id or category,
            int(dim),
            "l2",
            json.dumps({"category_backfill": category}),
            "{}",
            "x64",
            "native",
        ),
    )
    return run_id


def _ensure_observation(conn, media_id: str, run_id: str) -> str:
    row = conn.execute(
        """SELECT observation_id FROM observations
           WHERE media_id=? AND run_id=? AND frame_id IS NULL""",
        (media_id, run_id),
    ).fetchone()
    if row is not None:
        return str(row["observation_id"])
    observation_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
        (observation_id, media_id, None, None, run_id),
    )
    return observation_id


def _coverage_row(conn, media_id: str, category: str):
    return conn.execute(
        "SELECT * FROM category_coverage WHERE media_id=? AND category=?",
        (media_id, category),
    ).fetchone()


def _save_coverage(conn, *, media_id: str, category: str, sha256: str, probe: ProviderProbe, **fields) -> None:
    current = _coverage_row(conn, media_id, category)
    now = _now()
    payload = {
        "sha256": sha256 or "",
        "provider_id": probe.provider_id,
        "provider_version": probe.provider_version,
        "state": fields.get("state") or STATE_PENDING,
        "outcome": fields.get("outcome"),
        "attempt_count": int(fields.get("attempt_count") or 0),
        "last_error": fields.get("last_error"),
        "frame_done": int(fields.get("frame_done") or 0),
        "detail_done": int(fields.get("detail_done") or 0),
        "started_at": fields.get("started_at"),
        "finished_at": fields.get("finished_at"),
        "updated_at": now,
    }
    if current is None:
        conn.execute(
            """INSERT INTO category_coverage(
                 media_id, category, sha256, provider_id, provider_version, state, outcome,
                 attempt_count, last_error, frame_done, detail_done, started_at, finished_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                media_id,
                category,
                payload["sha256"],
                payload["provider_id"],
                payload["provider_version"],
                payload["state"],
                payload["outcome"],
                payload["attempt_count"],
                payload["last_error"],
                payload["frame_done"],
                payload["detail_done"],
                payload["started_at"],
                payload["finished_at"],
                payload["updated_at"],
            ),
        )
        return
    conn.execute(
        """UPDATE category_coverage
           SET sha256=?, provider_id=?, provider_version=?, state=?, outcome=?,
               attempt_count=?, last_error=?, frame_done=?, detail_done=?,
               started_at=?, finished_at=?, updated_at=?
           WHERE media_id=? AND category=?""",
        (
            payload["sha256"],
            payload["provider_id"],
            payload["provider_version"],
            payload["state"],
            payload["outcome"],
            payload["attempt_count"],
            payload["last_error"],
            payload["frame_done"],
            payload["detail_done"],
            payload["started_at"] or current["started_at"],
            payload["finished_at"],
            payload["updated_at"],
            media_id,
            category,
        ),
    )


def recover_interrupted(conn, category: str) -> int:
    """A killed run must not look finished. Running rows become interrupted."""
    now = _now()
    cur = conn.execute(
        """UPDATE category_coverage
           SET state=?, outcome=COALESCE(outcome, 'interrupted'), updated_at=?, finished_at=?
           WHERE category=? AND state=?""",
        (STATE_INTERRUPTED, now, now, category, STATE_RUNNING),
    )
    return int(cur.rowcount or 0)


def _fresh(row, *, sha256: str, probe: ProviderProbe, category: str) -> bool:
    """True when this photo's coverage is still valid and must not be redone."""
    if row is None:
        return False
    if str(row["state"]) != STATE_COMPLETED:
        return False
    if str(row["sha256"] or "") != str(sha256 or ""):
        return False
    if str(row["provider_version"] or "") != probe.provider_version:
        return False
    if category == CATEGORY_REGIONS and not (int(row["frame_done"] or 0) and int(row["detail_done"] or 0)):
        return False
    return True


def _needs_work(row, *, sha256: str, probe: ProviderProbe, category: str) -> bool:
    if _fresh(row, sha256=sha256, probe=probe, category=category):
        return False
    if row is None:
        return True
    if str(row["state"]) == STATE_SKIPPED and str(row["outcome"] or "") == "unsupported":
        return str(row["sha256"] or "") != str(sha256 or "")
    if str(row["state"]) == STATE_SKIPPED and str(row["outcome"] or "") == "missing_original":
        return True
    return True


def _clear_items(conn, media_id: str, *, provider: str, kind: str) -> None:
    rows = conn.execute(
        """SELECT i.item_id FROM observation_items i
           JOIN observations o ON o.observation_id = i.observation_id
           WHERE o.media_id=? AND i.provider=? AND i.kind=?""",
        (media_id, provider, kind),
    ).fetchall()
    ids = [str(row["item_id"]) for row in rows]
    if not ids:
        return
    marks = ",".join("?" for _ in ids)
    conn.execute(f"DELETE FROM embeddings WHERE item_id IN ({marks})", ids)
    conn.execute(f"DELETE FROM observation_items WHERE item_id IN ({marks})", ids)


def process_people(conn, img, *, observation_id: str, run_id: str, probe: ProviderProbe) -> ItemResult:
    """Face detections and embeddings only. Never persons, person_id, or clusters."""
    from semblon.ingest import _persist_faces

    try:
        faces = people_detect(img)
    except Exception as exc:  # noqa: BLE001 — one photo must stay retryable
        return ItemResult(STATE_FAILED, "execution_failure", f"{type(exc).__name__}: {exc}")
    _persist_faces(
        conn,
        obs_id=observation_id,
        run_id=run_id,
        pack_id=probe.provider_version,
        faces=list(faces or []),
    )
    outcome = "faces" if faces else "no_faces"
    return ItemResult(STATE_COMPLETED, outcome)


def process_objects(conn, img, *, media_id: str, observation_id: str, run_id: str, probe: ProviderProbe) -> ItemResult:
    from semblon.object_pack import PROVIDER
    from semblon.observers import persist_item

    try:
        found = objects_detect(img)
    except Exception as exc:  # noqa: BLE001
        return ItemResult(STATE_FAILED, "execution_failure", f"{type(exc).__name__}: {exc}")
    _clear_items(conn, media_id, provider=PROVIDER, kind="object")
    for obj in found or []:
        persist_item(
            conn,
            observation_id=observation_id,
            run_id=run_id,
            kind="object",
            provider=PROVIDER,
            payload={
                "class": obj.get("class"),
                "label": obj.get("label"),
                "class_id": obj.get("class_id"),
                "source": "nanodet",
                "identity": "not facekit",
                "provider_version": probe.provider_version,
            },
            bbox=obj.get("bbox"),
            score=obj.get("score"),
        )
    return ItemResult(STATE_COMPLETED, "objects" if found else "no_objects")


def process_regions(
    conn,
    img,
    *,
    media_id: str,
    observation_id: str,
    run_id: str,
    probe: ProviderProbe,
    gate,
    frame_done: int,
    detail_done: int,
    sha256: str,
    attempt_count: int,
) -> ItemResult:
    """Frame first, then detail. Frame coverage is committed before detail starts."""
    from semblon.region_encoder import DEPTH_DETAIL, DEPTH_FRAME, PROVIDER, persist_region_index

    if frame_done and detail_done:
        return ItemResult(STATE_COMPLETED, "frame_and_detail", frame_done=1, detail_done=1)
    if not frame_done:
        if gate is not None and gate():
            return ItemResult(STATE_INTERRUPTED, "cancelled", frame_done=0, detail_done=int(detail_done))
        prepared = regions_prepare(img, depth=DEPTH_FRAME, cancelled=gate)
        if not isinstance(prepared, dict) or prepared.get("skip_persist"):
            note = ""
            if isinstance(prepared, dict):
                note = str((prepared.get("counts") or {}).get("note") or "region frame was not indexed")
            return ItemResult(
                STATE_FAILED,
                "execution_failure",
                note or "region frame was not indexed",
                frame_done=0,
                detail_done=int(detail_done),
            )
        with writer_lock():
            _clear_items(conn, media_id, provider=PROVIDER, kind="clip")
            persist_region_index(conn, observation_id=observation_id, run_id=run_id, prepared=prepared)
            _save_coverage(
                conn,
                media_id=media_id,
                category=CATEGORY_REGIONS,
                sha256=sha256,
                probe=probe,
                state=STATE_PENDING,
                outcome="frame_only",
                attempt_count=attempt_count,
                frame_done=1,
                detail_done=0,
                finished_at=None,
            )
            conn.commit()
        frame_done = 1
    if not detail_done:
        if gate is not None and gate():
            return ItemResult(STATE_INTERRUPTED, "frame_only", frame_done=1, detail_done=0)
        prepared = regions_prepare(img, depth=DEPTH_DETAIL, cancelled=gate)
        if not isinstance(prepared, dict) or prepared.get("skip_persist"):
            note = ""
            if isinstance(prepared, dict):
                note = str((prepared.get("counts") or {}).get("note") or "region detail was not indexed")
            return ItemResult(
                STATE_FAILED,
                "execution_failure",
                note or "region detail was not indexed",
                frame_done=1,
                detail_done=0,
            )
        with writer_lock():
            persist_region_index(conn, observation_id=observation_id, run_id=run_id, prepared=prepared)
        detail_done = 1
    return ItemResult(STATE_COMPLETED, "frame_and_detail", frame_done=1, detail_done=1)


def process_words(conn, img, *, media_id: str, observation_id: str, run_id: str, probe: ProviderProbe) -> ItemResult:
    from semblon.observers import OCR_PROVIDER, persist_item

    try:
        rec = words_ocr(img)
    except Exception as exc:  # noqa: BLE001
        return ItemResult(STATE_FAILED, "execution_failure", f"{type(exc).__name__}: {exc}")
    if rec is None:
        return ItemResult(STATE_UNAVAILABLE, "unavailable", "The text reader is not available.")
    if rec.get("error"):
        return ItemResult(STATE_FAILED, "execution_failure", str(rec.get("note") or rec.get("error"))[:240])
    text_read = str(rec.get("text") or "")
    _clear_items(conn, media_id, provider=OCR_PROVIDER, kind="text")
    persist_item(
        conn,
        observation_id=observation_id,
        run_id=run_id,
        kind="text",
        provider=OCR_PROVIDER,
        payload={
            "text": text_read,
            "identity": "not facekit",
            "contract_status": "SUCCESS" if text_read.strip() else "NO_RESULT",
            "provider_version": probe.provider_version,
        },
        score=rec.get("score"),
    )
    for word in rec.get("words") or []:
        token = str(word.get("text") or "").strip()
        box = word.get("bbox")
        if not token or not box:
            continue
        persist_item(
            conn,
            observation_id=observation_id,
            run_id=run_id,
            kind="text",
            provider=OCR_PROVIDER,
            payload={
                "text": token,
                "identity": "not facekit",
                "contract_status": "SUCCESS",
                "role": "word",
                "provider_version": probe.provider_version,
            },
            bbox=tuple(box),
            score=word.get("score"),
        )
    outcome = "text" if text_read.strip() else "empty"
    return ItemResult(STATE_COMPLETED, outcome)


def _still(row) -> bool:
    if str(row["source_type"] or "") == "video":
        return False
    suffix = Path(str(row["path"] or "")).suffix.lower()
    return suffix in _STILL_EXT and str(row["source_type"] or "") == "folder"


def _numbers(conn, category: str) -> dict:
    rows = conn.execute(
        """SELECT c.state, c.outcome, c.frame_done, c.detail_done, c.sha256, c.provider_version,
                  m.sha256 AS media_sha
           FROM category_coverage c
           LEFT JOIN media m ON m.media_id = c.media_id
           WHERE c.category=?""",
        (category,),
    ).fetchall()
    eligible = conn.execute("SELECT path, source_type FROM media").fetchall()
    n_eligible = sum(1 for row in eligible if _still(row))
    completed = 0
    failed = 0
    skipped = 0
    missing = 0
    read_failed = 0
    execution_failed = 0
    frame = 0
    detail = 0
    tracked = 0
    for row in rows:
        tracked += 1
        state = str(row["state"])
        same = str(row["sha256"] or "") == str(row["media_sha"] or "")
        if state == STATE_COMPLETED and same:
            if category == CATEGORY_REGIONS and not (int(row["frame_done"] or 0) and int(row["detail_done"] or 0)):
                pass
            else:
                completed += 1
        elif state == STATE_FAILED:
            failed += 1
        elif state == STATE_SKIPPED:
            skipped += 1
        if int(row["frame_done"] or 0):
            frame += 1
        if int(row["detail_done"] or 0):
            detail += 1
        if state == STATE_FAILED and str(row["outcome"] or "") == "read_failure":
            read_failed += 1
        elif state == STATE_FAILED and str(row["outcome"] or "") == "execution_failure":
            execution_failed += 1
        if state == STATE_SKIPPED and str(row["outcome"] or "") == "missing_original":
            missing += 1
    return {
        "category": category,
        "label": _label(category),
        "eligible": n_eligible,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "missing_original": missing,
        "read_failed": read_failed,
        "execution_failed": execution_failed,
        "frame_indexed": frame,
        "detail_indexed": detail,
        "tracked": tracked,
    }


def coverage_report(store: Path, category: str | None = None) -> dict:
    """Durable per-category coverage. Failed and unavailable rows are not complete."""
    conn = connect(store)
    try:
        init_db(conn)
        categories = (category,) if category else CATEGORIES
        out = {name: _numbers(conn, name) for name in categories}
        return out if category is None else out[category]
    finally:
        conn.close()


def coverage_detail(report: dict, *, category: str) -> str | None:
    """One sentence about an incomplete tracked category. None when there is nothing to add."""
    if int(report.get("tracked") or 0) <= 0:
        return None
    eligible = int(report.get("eligible") or 0)
    if eligible <= 0:
        return None
    completed = int(report.get("completed") or 0)
    failed = int(report.get("failed") or 0)
    missing = int(report.get("missing_original") or 0)
    read_failed = int(report.get("read_failed") or 0)
    execution_failed = int(report.get("execution_failed") or 0)
    if category == CATEGORY_REGIONS:
        frame = int(report.get("frame_indexed") or 0)
        detail = int(report.get("detail_indexed") or 0)
        if completed >= eligible and failed == 0 and missing == 0 and detail >= eligible:
            return None
        parts = [
            f"{frame} of {eligible} photos have a whole-picture look",
            f"{detail} of {eligible} have fine detail",
        ]
    else:
        if completed >= eligible and failed == 0 and missing == 0:
            return None
        parts = [f"{completed} of {eligible} photos checked"]
        unchecked = eligible - completed - failed - missing
        if unchecked > 0:
            parts.append("the rest have not been checked")
    if read_failed:
        parts.append(f"{read_failed} could not be read" if read_failed != 1 else "1 could not be read")
    if execution_failed:
        parts.append(
            f"{execution_failed} failed while checking" if execution_failed != 1 else "1 failed while checking"
        )
    other = failed - read_failed - execution_failed
    if other > 0:
        parts.append(f"{other} need another try")
    if missing:
        parts.append("1 original is missing" if missing == 1 else f"{missing} originals are missing")
    return ". ".join(part[0].upper() + part[1:] for part in parts) + "."


def partial_coverage_clause(store: Path, category: str) -> str | None:
    """Plain 'N of M photos checked' when this category has been tracked and is incomplete.

    Libraries with no category_coverage rows are left alone so older searches
    keep their existing wording.
    """
    from semblon.store import connect_readonly

    try:
        conn = connect_readonly(store)
    except Exception:
        return None
    try:
        found = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='category_coverage'"
        ).fetchone()
        if found is None:
            return None
        numbers = _numbers(conn, category)
    except Exception:
        return None
    finally:
        conn.close()
    if numbers["tracked"] <= 0 or numbers["eligible"] <= 0:
        return None
    return coverage_detail(numbers, category=category)


def discover_coverage_text(store: Path) -> str:
    """What Discover can say before anyone starts a scan. Does not scan."""
    lines = []
    try:
        reports = coverage_report(store)
    except Exception:
        reports = {}
    for category in CATEGORIES:
        report = reports.get(category) or {
            "eligible": 0,
            "completed": 0,
            "frame_indexed": 0,
            "detail_indexed": 0,
        }
        try:
            probe = probe_category(category)
        except Exception as exc:  # noqa: BLE001 — the sheet must still open
            probe = ProviderProbe(False, category, "", f"{_label(category)} is not available on this computer.")
        lines.append(_discover_line(category, report, probe))
    return "\n".join(lines)


def _discover_line(category: str, report: dict, probe: ProviderProbe) -> str:
    label = _label(category)
    eligible = int(report.get("eligible") or 0)
    completed = int(report.get("completed") or 0)
    detail = coverage_detail(report, category=category)
    if not probe.available and completed <= 0:
        reason = (probe.reason or f"{label} is not available on this computer.").strip()
        if "downloaded" not in reason.lower():
            reason = reason.rstrip(".") + ". Nothing was downloaded."
        return f"{label}: {reason}"
    if eligible <= 0:
        return f"{label}: no photos to check yet."
    if not probe.available:
        reason = (probe.reason or f"{label} is not available on this computer now.").strip()
        if "downloaded" not in reason.lower():
            reason = reason.rstrip(".") + ". Nothing was downloaded."
        lead = detail or f"{completed} of {eligible} photos checked."
        return f"{label}: {lead} {reason}"
    if detail:
        return f"{label}: {detail}"
    if completed >= eligible:
        return f"{label}: all {eligible} photos checked."
    return f"{label}: not checked yet. {eligible} photos are in the library."


def _message(category: str, *, status: str, completed: int, total: int, skipped_done: int, failed: int, reason: str) -> str:
    label = _label(category)
    if status == "unavailable":
        return reason or f"{label} is not available on this computer."
    if total == 0 and status == "completed":
        return f"No photos to check for {label.lower()}."
    if status == "cancelled":
        return f"Stopped {label.lower()}. {completed} of {total} checked. The rest are not finished."
    if status == "failed" and completed == 0 and reason:
        return reason
    extra = ""
    if skipped_done:
        extra += f" {skipped_done} already checked."
    if failed:
        extra += f" {failed} need another try."
    if total and completed >= total and failed == 0:
        return f"{label} checked. {completed} of {total}.{extra}"
    return f"{label}: {completed} of {total} checked.{extra}"


def run_category_backfill(store: Path, category: str, *, gate=None, on_event=None) -> dict:
    """Scan every eligible archive still for one category.

    ``gate`` matches JobEngine: it blocks while paused and returns True when
    the job should stop. Stopping does not mark unfinished photos complete.
    """
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category}")
    store = Path(store)
    probe = probe_category(category)
    conn = connect(store)
    try:
        init_db(conn)
        recover_interrupted(conn, category)
        conn.commit()
        if not probe.available:
            rec = {
                "category": category,
                "status": "unavailable",
                "provider_id": probe.provider_id,
                "provider_version": probe.provider_version,
                "reason": probe.reason,
                "eligible": 0,
                "completed": 0,
                "skipped_already": 0,
                "failed": 0,
                "cancelled": False,
                "user_message": _message(
                    category, status="unavailable", completed=0, total=0, skipped_done=0, failed=0, reason=probe.reason
                ),
            }
            if on_event is not None:
                on_event(ProgressEvent(stage="category", kind="failed", message=rec["user_message"], outcome="unavailable"))
            return rec

        media_rows = conn.execute(
            "SELECT media_id, path, sha256, source_type FROM media ORDER BY path"
        ).fetchall()
        eligible = [row for row in media_rows if _still(row)]
        total = len(eligible)
        dim = 128 if category == CATEGORY_PEOPLE else 1
        with writer_lock():
            run_id = _open_run(conn, pack_id=probe.provider_version or probe.provider_id or category, dim=dim, category=category)
            conn.commit()

        completed = 0
        skipped_already = 0
        failed = 0
        checked = 0
        stopped = False

        def _emit(kind: str, message: str, outcome: str = "") -> None:
            if on_event is None:
                return
            on_event(
                ProgressEvent(
                    stage="category",
                    kind=kind,
                    current=checked,
                    total=total,
                    files_processed=checked,
                    files_total=total,
                    path=None,
                    message=message,
                    outcome=outcome or category,
                    counts={"completed": completed, "failed": failed, "skipped_already": skipped_already},
                )
            )

        _emit("started", _message(category, status="running", completed=0, total=total, skipped_done=0, failed=0, reason=""))

        for row in media_rows:
            media_id = str(row["media_id"])
            sha = str(row["sha256"] or "")
            path = Path(str(row["path"] or ""))
            if not _still(row):
                prior = _coverage_row(conn, media_id, category)
                if prior is None or str(prior["state"]) != STATE_SKIPPED or str(prior["sha256"] or "") != sha:
                    with writer_lock():
                        _save_coverage(
                            conn,
                            media_id=media_id,
                            category=category,
                            sha256=sha,
                            probe=probe,
                            state=STATE_SKIPPED,
                            outcome="unsupported",
                            finished_at=_now(),
                        )
                        conn.commit()
                continue
            if gate is not None and gate():
                stopped = True
                break
            prior = _coverage_row(conn, media_id, category)
            if _fresh(prior, sha256=sha, probe=probe, category=category):
                skipped_already += 1
                checked += 1
                completed += 1
                _emit(
                    "progress",
                    _message(category, status="running", completed=completed, total=total, skipped_done=skipped_already, failed=failed, reason=""),
                    "skipped",
                )
                continue
            if not path.is_file():
                with writer_lock():
                    _save_coverage(
                        conn,
                        media_id=media_id,
                        category=category,
                        sha256=sha,
                        probe=probe,
                        state=STATE_SKIPPED,
                        outcome="missing_original",
                        last_error="The original file is missing.",
                        finished_at=_now(),
                        frame_done=int(prior["frame_done"] or 0) if prior is not None else 0,
                        detail_done=int(prior["detail_done"] or 0) if prior is not None else 0,
                    )
                    conn.commit()
                failed += 0
                checked += 1
                _emit(
                    "progress",
                    _message(category, status="running", completed=completed, total=total, skipped_done=skipped_already, failed=failed, reason=""),
                    "missing",
                )
                continue
            attempts = int(prior["attempt_count"] or 0) + 1 if prior is not None else 1
            frame_done = int(prior["frame_done"] or 0) if prior is not None else 0
            detail_done = int(prior["detail_done"] or 0) if prior is not None else 0
            if prior is not None and (
                str(prior["sha256"] or "") != sha
                or str(prior["provider_version"] or "") != probe.provider_version
            ):
                frame_done = 0
                detail_done = 0
            with writer_lock():
                _save_coverage(
                    conn,
                    media_id=media_id,
                    category=category,
                    sha256=sha,
                    probe=probe,
                    state=STATE_RUNNING,
                    outcome=None,
                    attempt_count=attempts,
                    started_at=_now(),
                    finished_at=None,
                    frame_done=frame_done,
                    detail_done=detail_done,
                )
                conn.commit()
            img = decode_image(path)
            if gate is not None and gate():
                with writer_lock():
                    _save_coverage(
                        conn,
                        media_id=media_id,
                        category=category,
                        sha256=sha,
                        probe=probe,
                        state=STATE_INTERRUPTED,
                        outcome="cancelled",
                        attempt_count=attempts,
                        frame_done=frame_done,
                        detail_done=detail_done,
                        finished_at=_now(),
                    )
                    conn.commit()
                stopped = True
                break
            if img is None:
                result = ItemResult(STATE_FAILED, "read_failure", "The photo could not be read.")
            elif category == CATEGORY_PEOPLE:
                with writer_lock():
                    observation_id = _ensure_observation(conn, media_id, run_id)
                    result = process_people(conn, img, observation_id=observation_id, run_id=run_id, probe=probe)
                    conn.commit()
            elif category == CATEGORY_OBJECTS:
                with writer_lock():
                    observation_id = _ensure_observation(conn, media_id, run_id)
                    result = process_objects(
                        conn, img, media_id=media_id, observation_id=observation_id, run_id=run_id, probe=probe
                    )
                    conn.commit()
            elif category == CATEGORY_REGIONS:
                with writer_lock():
                    observation_id = _ensure_observation(conn, media_id, run_id)
                    conn.commit()
                result = process_regions(
                    conn,
                    img,
                    media_id=media_id,
                    observation_id=observation_id,
                    run_id=run_id,
                    probe=probe,
                    gate=gate,
                    frame_done=frame_done,
                    detail_done=detail_done,
                    sha256=sha,
                    attempt_count=attempts,
                )
            else:
                with writer_lock():
                    observation_id = _ensure_observation(conn, media_id, run_id)
                    result = process_words(
                        conn, img, media_id=media_id, observation_id=observation_id, run_id=run_id, probe=probe
                    )
                    conn.commit()
            if category == CATEGORY_REGIONS:
                with writer_lock():
                    finished_state = result.state
                    if finished_state == STATE_COMPLETED and not (result.frame_done and result.detail_done):
                        finished_state = STATE_PENDING
                    _save_coverage(
                        conn,
                        media_id=media_id,
                        category=category,
                        sha256=sha,
                        probe=probe,
                        state=finished_state,
                        outcome=result.outcome,
                        attempt_count=attempts,
                        last_error=result.error or None,
                        frame_done=result.frame_done,
                        detail_done=result.detail_done,
                        finished_at=_now() if finished_state in {STATE_COMPLETED, STATE_FAILED, STATE_INTERRUPTED} else None,
                    )
                    conn.commit()
            else:
                with writer_lock():
                    _save_coverage(
                        conn,
                        media_id=media_id,
                        category=category,
                        sha256=sha,
                        probe=probe,
                        state=result.state,
                        outcome=result.outcome,
                        attempt_count=attempts,
                        last_error=result.error or None,
                        finished_at=_now(),
                    )
                    conn.commit()
            if result.state == STATE_COMPLETED:
                completed += 1
            elif result.state == STATE_FAILED:
                failed += 1
            elif result.state == STATE_INTERRUPTED:
                stopped = True
                break
            elif result.state == STATE_UNAVAILABLE:
                stopped = True
                probe = ProviderProbe(False, probe.provider_id, probe.provider_version, result.error or probe.reason)
                break
            checked += 1
            _emit(
                "progress",
                _message(category, status="running", completed=completed, total=total, skipped_done=skipped_already, failed=failed, reason=""),
            )
            if gate is not None and gate():
                stopped = True
                break

        if stopped and not probe.available:
            status = "unavailable"
        elif stopped:
            status = "cancelled"
        elif failed and completed == 0:
            status = "failed"
        else:
            status = "completed"
        reason = probe.reason
        message = _message(
            category,
            status=status,
            completed=completed,
            total=total,
            skipped_done=skipped_already,
            failed=failed,
            reason=reason,
        )
        _emit("cancelled" if status == "cancelled" else "completed" if status == "completed" else "failed", message, status)
        return {
            "category": category,
            "status": status,
            "provider_id": probe.provider_id,
            "provider_version": probe.provider_version,
            "reason": reason,
            "eligible": total,
            "completed": completed,
            "skipped_already": skipped_already,
            "failed": failed,
            "cancelled": status == "cancelled",
            "user_message": message,
            "coverage": coverage_report(store, category),
        }
    finally:
        conn.close()
