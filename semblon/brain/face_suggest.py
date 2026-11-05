"""FaceSuggestObserver — YES_WRAP existing face pack; suggested = reading (b).

Compares a validated probe embedding against confirmed Person gallery via
compare(). Writes C4 observation always (fail-closed). Writes suggested only
when suggest_floor <= top1 < confirm. Never assigns faces.person_id.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from semblon.brain.evaluations import write_suggested_evaluation
from semblon.brain.evidence import record_observations
from semblon.brain.observation import Observation, PhotoRef, Region
from semblon.brain.suggest_policy import CONFIRM_THRESHOLD, in_suggest_band
from semblon.compare import CompareError, compare, validate_identity_embedding


@dataclass(frozen=True)
class SuggestResult:
    observation_ids: list[int]
    evaluation_ids: list[str]
    reused: bool = False


class FaceSuggestObserver:
    capability_id = "C4"
    provider_name = "existing_face_embedder"

    def __init__(
        self,
        *,
        pack_id: str,
        dim: int,
        model_pack_hash: str | None = None,
        embed_fn: Callable[[PhotoRef], bytes] | None = None,
    ) -> None:
        self.pack_id = pack_id
        self.dim = int(dim)
        self.model_pack_hash = model_pack_hash or pack_id
        self._embed_fn = embed_fn

    def observe(
        self,
        photo: PhotoRef,
        regions: list[Region] | None = None,
        *,
        embedding_blob: bytes | None = None,
    ) -> tuple[list[Observation], bytes]:
        if embedding_blob is None:
            if self._embed_fn is None:
                raise ValueError("embedding_blob or embed_fn required (no silent model load)")
            embedding_blob = self._embed_fn(photo)
        validate_identity_embedding(self.pack_id, self.dim, embedding_blob)
        obs = Observation(
            photo_id=photo.photo_id,
            capability_id=self.capability_id,
            provider_name=self.provider_name,
            model_pack_hash=self.model_pack_hash,
            payload={"dim": self.dim, "pack_id": self.pack_id, "kind": "face_embed"},
            content_hash=photo.content_hash,
            confidence=1.0,
        )
        return [obs], embedding_blob


def _person_gallery(conn: sqlite3.Connection, pack_id: str) -> list[dict]:
    """Active confirmed persons' ok faces in this pack. Same contract as identify."""
    rows = conn.execute(
        """
        SELECT f.face_id, f.embedding, f.embedding_pack, f.embedding_dim,
               f.person_id, p.display_name
          FROM faces f
          JOIN persons p ON p.person_id = f.person_id
         WHERE f.status='ok' AND f.embedding IS NOT NULL
           AND p.status='active' AND f.person_id IS NOT NULL
           AND f.embedding_pack=?
         ORDER BY f.face_id
        """,
        (pack_id,),
    ).fetchall()
    out = []
    for g in rows:
        try:
            validate_identity_embedding(g[2], int(g[3]), g[1])
        except CompareError:
            continue
        out.append(
            {
                "face_id": g[0],
                "embedding": g[1],
                "embedding_pack": g[2],
                "embedding_dim": int(g[3]),
                "person_id": g[4],
                "display_name": g[5],
            }
        )
    return out


def _rank_persons(
    pack_id: str,
    dim: int,
    probe: bytes,
    gallery: list[dict],
) -> list[dict]:
    best: dict[str, dict] = {}
    for g in gallery:
        try:
            score = compare(
                pack_id,
                dim,
                probe,
                g["embedding_pack"],
                g["embedding_dim"],
                g["embedding"],
            )
        except CompareError:
            continue
        pid = g["person_id"]
        rec = best.get(pid)
        if rec is None or score > rec["score"]:
            best[pid] = {
                "person_id": pid,
                "display_name": g["display_name"],
                "score": float(score),
            }
    return sorted(best.values(), key=lambda r: (-r["score"], r["person_id"]))


def run_face_suggest(
    conn: sqlite3.Connection,
    observer: FaceSuggestObserver,
    photo: PhotoRef,
    *,
    run_id: str,
    embedding_blob: bytes | None = None,
) -> SuggestResult:
    """Record C4 observation; write suggested only when in band against Persons."""
    existing = conn.execute(
        """SELECT id FROM brain_observations
           WHERE media_id=? AND capability_id=?
             AND IFNULL(model_pack_hash, '')=IFNULL(?, '')""",
        (photo.photo_id, observer.capability_id, observer.model_pack_hash),
    ).fetchone()
    if existing is not None:
        return SuggestResult([int(existing[0])], [], reused=True)

    observations, probe = observer.observe(photo, embedding_blob=embedding_blob)
    write = record_observations(
        conn, observations, run_id=run_id, write_tagged=False
    )

    gallery = _person_gallery(conn, observer.pack_id)
    if not gallery:
        return SuggestResult(write.observation_ids, [], reused=False)

    ranked = _rank_persons(observer.pack_id, observer.dim, probe, gallery)
    if not ranked:
        return SuggestResult(write.observation_ids, [], reused=False)

    top1 = ranked[0]
    top2 = ranked[1] if len(ranked) > 1 else None
    score = top1["score"]
    # At/above confirm: existing P1 identify owns ACCEPT — brain does not suggest.
    if score >= CONFIRM_THRESHOLD:
        return SuggestResult(write.observation_ids, [], reused=False)
    if not in_suggest_band(score):
        return SuggestResult(write.observation_ids, [], reused=False)

    score_top2 = None if top2 is None else top2["score"]
    margin = None if score_top2 is None else float(score - score_top2)
    eid = write_suggested_evaluation(
        conn,
        run_id=run_id,
        embedding_pack=observer.pack_id,
        embedding_dim=observer.dim,
        score_top1=score,
        score_top2=score_top2,
        margin=margin,
        gallery_size=len(ranked),
        person_id=top1["person_id"],
        source="brain_c4_suggest",
    )
    conn.commit()
    return SuggestResult(write.observation_ids, [eid], reused=False)
