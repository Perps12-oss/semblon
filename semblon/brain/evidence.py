"""Persist observations + evidence; explain provenance. No graph nodes in Inc 2."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from semblon.brain.evaluations import write_tagged_evaluation
from semblon.brain.observation import Observation
from semblon.compare import CompareError, validate_identity_embedding


@dataclass(frozen=True)
class WriteResult:
    observation_ids: list[int]
    evidence_ids: list[int]
    evaluation_ids: list[str]
    reused: bool = False


@dataclass(frozen=True)
class EvidenceExplanation:
    evidence_id: int
    observation_id: int
    media_id: str
    capability_id: str
    provider_name: str
    model_pack_hash: str | None
    role: str
    claim_key: str
    payload: dict
    confidence: float | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_observations(
    conn: sqlite3.Connection,
    observations: list[Observation],
    *,
    run_id: str,
    write_tagged: bool = True,
) -> WriteResult:
    """Insert immutable observations + supporting evidence. Idempotent per cache key."""
    if not observations:
        return WriteResult([], [], [], reused=False)

    obs_ids: list[int] = []
    ev_ids: list[int] = []
    eval_ids: list[str] = []
    now = _now()

    for obs in observations:
        existing = conn.execute(
            """SELECT id FROM brain_observations
               WHERE media_id=? AND capability_id=?
                 AND IFNULL(model_pack_hash, '')=IFNULL(?, '')""",
            (obs.photo_id, obs.capability_id, obs.model_pack_hash),
        ).fetchone()
        if existing is not None:
            return WriteResult([int(existing[0])], [], [], reused=True)

        rx = ry = rw = rh = None
        if obs.region is not None:
            rx, ry, rw, rh = obs.region.x, obs.region.y, obs.region.w, obs.region.h
        cur = conn.execute(
            """INSERT INTO brain_observations(
                 media_id, region_x, region_y, region_w, region_h,
                 capability_id, provider_name, model_pack_hash,
                 payload_json, confidence, content_hash, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                obs.photo_id,
                rx,
                ry,
                rw,
                rh,
                obs.capability_id,
                obs.provider_name,
                obs.model_pack_hash,
                json.dumps(obs.payload, separators=(",", ":")),
                obs.confidence,
                obs.content_hash,
                now,
            ),
        )
        oid = int(cur.lastrowid)
        obs_ids.append(oid)

        tags = obs.payload.get("tags") if isinstance(obs.payload, dict) else None
        if isinstance(tags, list) and tags:
            for tag in tags:
                label = str(tag.get("label") if isinstance(tag, dict) else tag)
                claim = f"tag:{label}"
                ecur = conn.execute(
                    """INSERT INTO brain_evidence(
                         observation_id, edge_id, node_id, role, weight,
                         claim_key, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (oid, None, None, "supports", 1.0, claim, now),
                )
                ev_ids.append(int(ecur.lastrowid))
        else:
            claim = f"{obs.capability_id}:{obs.provider_name}"
            ecur = conn.execute(
                """INSERT INTO brain_evidence(
                     observation_id, edge_id, node_id, role, weight,
                     claim_key, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (oid, None, None, "supports", 1.0, claim, now),
            )
            ev_ids.append(int(ecur.lastrowid))

        if write_tagged and obs.capability_id == "C1":
            pack = obs.model_pack_hash or obs.provider_name
            eid = write_tagged_evaluation(
                conn,
                run_id=run_id,
                embedding_pack=pack,
                reason=f"c1:{obs.provider_name}",
                source="brain_c1",
                media_id=obs.photo_id,
            )
            eval_ids.append(eid)

    conn.commit()
    return WriteResult(obs_ids, ev_ids, eval_ids, reused=False)


def explain(conn: sqlite3.Connection, evidence_id: int) -> EvidenceExplanation:
    row = conn.execute(
        """SELECT e.id, e.observation_id, e.role, e.claim_key,
                  o.media_id, o.capability_id, o.provider_name, o.model_pack_hash,
                  o.payload_json, o.confidence
             FROM brain_evidence e
             JOIN brain_observations o ON o.id = e.observation_id
            WHERE e.id=?""",
        (evidence_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown evidence_id: {evidence_id}")
    payload = json.loads(row[8] or "{}")
    return EvidenceExplanation(
        evidence_id=int(row[0]),
        observation_id=int(row[1]),
        role=str(row[2]),
        claim_key=str(row[3]),
        media_id=str(row[4]),
        capability_id=str(row[5]),
        provider_name=str(row[6]),
        model_pack_hash=row[7],
        payload=payload if isinstance(payload, dict) else {"raw": payload},
        confidence=row[9],
    )


def record_face_observation(
    conn: sqlite3.Connection,
    observation: Observation,
    *,
    pack_id: str,
    dim: int,
    embedding_blob: bytes,
    run_id: str,
) -> WriteResult:
    """C4 path: validate_identity_embedding fail-closed before any write."""
    try:
        validate_identity_embedding(pack_id, dim, embedding_blob)
    except CompareError:
        conn.rollback()
        raise
    return record_observations(conn, [observation], run_id=run_id, write_tagged=False)
