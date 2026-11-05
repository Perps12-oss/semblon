"""identify_evaluations writers for BRAIN outcomes. P1 seven-field shape preserved."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from semblon.brain.suggest_policy import (
    SUGGEST_FLOOR,
    SUGGEST_POLICY_VERSION,
    band_reason,
)

TAGGED_POLICY_VERSION = "brain-tag-v1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_tagged_evaluation(
    conn,
    *,
    run_id: str,
    embedding_pack: str,
    embedding_dim: int = 0,
    reason: str | None = None,
    source: str = "brain_c1",
    threshold: float = 0.0,
    media_id: str | None = None,
) -> str:
    """Record outcome='tagged' with the same columns as ACCEPT/UNKNOWN rows."""
    eid = uuid.uuid4().hex
    detail = reason or "tagged"
    if media_id:
        detail = f"{detail};media={media_id}"
    conn.execute(
        """INSERT INTO identify_evaluations(
             evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
             outcome, reason, threshold, policy_version, gallery_size,
             score_top1, score_top2, margin, person_id, source, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            eid,
            None,
            embedding_pack,
            int(embedding_dim),
            run_id,
            "tagged",
            detail,
            float(threshold),
            TAGGED_POLICY_VERSION,
            None,
            None,
            None,
            None,
            None,
            source,
            _now(),
        ),
    )
    return eid


def write_suggested_evaluation(
    conn,
    *,
    run_id: str,
    embedding_pack: str,
    embedding_dim: int,
    score_top1: float,
    score_top2: float | None,
    margin: float | None,
    gallery_size: int,
    person_id: str | None,
    probe_face_id: str | None = None,
    source: str = "brain_c4_suggest",
) -> str:
    """Record outcome='suggested' — resemblance below confirm, above suggest_floor.

    ``threshold`` stores SUGGEST_FLOOR (operative band). Confirm + floor also
    appear in ``policy_version`` and ``reason`` so both bands are auditable.
    Does not write faces.person_id or decisions.kind.
    """
    eid = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO identify_evaluations(
             evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
             outcome, reason, threshold, policy_version, gallery_size,
             score_top1, score_top2, margin, person_id, source, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            eid,
            probe_face_id,
            embedding_pack,
            int(embedding_dim),
            run_id,
            "suggested",
            band_reason(),
            float(SUGGEST_FLOOR),
            SUGGEST_POLICY_VERSION,
            int(gallery_size),
            float(score_top1),
            None if score_top2 is None else float(score_top2),
            None if margin is None else float(margin),
            person_id,
            source,
            _now(),
        ),
    )
    return eid
