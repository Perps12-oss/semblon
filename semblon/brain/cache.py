"""Evidence cache — prevents duplicate inference.

In-memory for fixtures; PersistEvidenceCache reads brain_observations.
"""

from __future__ import annotations

import sqlite3

from semblon.brain.observation import Observation


class EvidenceCache:
    """Lookup by (photo, capability, pack) and by content-addressed bytes."""

    def __init__(self) -> None:
        self._by_photo: dict[tuple[str, str, str | None], Observation] = {}
        self._by_content: dict[tuple[str, str | None], Observation] = {}
        self.hits = 0
        self.misses = 0

    def put(self, observation: Observation) -> None:
        key = (
            observation.photo_id,
            observation.capability_id,
            observation.model_pack_hash,
        )
        self._by_photo[key] = observation
        if observation.content_hash:
            self._by_content[(observation.content_hash, observation.model_pack_hash)] = (
                observation
            )

    def has_observation(
        self,
        photo_id: str,
        capability_id: str,
        pack_hash: str | None = None,
    ) -> bool:
        """Peek without affecting hit-rate counters."""
        if pack_hash is None:
            return any(
                k[0] == photo_id and k[1] == capability_id for k in self._by_photo
            )
        return (photo_id, capability_id, pack_hash) in self._by_photo

    def existing_observation(
        self,
        photo_id: str,
        capability_id: str,
        pack_hash: str | None = None,
    ) -> Observation | None:
        if pack_hash is None:
            for key, obs in self._by_photo.items():
                if key[0] == photo_id and key[1] == capability_id:
                    self.hits += 1
                    return obs
            self.misses += 1
            return None
        hit = self._by_photo.get((photo_id, capability_id, pack_hash))
        if hit is not None:
            self.hits += 1
            return hit
        self.misses += 1
        return None

    def content_address_hit(
        self,
        content_hash: str,
        model_pack: str | None,
    ) -> Observation | None:
        hit = self._by_content.get((content_hash, model_pack))
        if hit is not None:
            self.hits += 1
            return hit
        self.misses += 1
        return None

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


class PersistEvidenceCache:
    """SQLite-backed cache over brain_observations."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.hits = 0
        self.misses = 0

    def has_observation(
        self,
        photo_id: str,
        capability_id: str,
        pack_hash: str | None = None,
    ) -> bool:
        if pack_hash is None:
            row = self._conn.execute(
                """SELECT 1 FROM brain_observations
                   WHERE media_id=? AND capability_id=? LIMIT 1""",
                (photo_id, capability_id),
            ).fetchone()
        else:
            row = self._conn.execute(
                """SELECT 1 FROM brain_observations
                   WHERE media_id=? AND capability_id=?
                     AND IFNULL(model_pack_hash, '')=IFNULL(?, '') LIMIT 1""",
                (photo_id, capability_id, pack_hash),
            ).fetchone()
        return row is not None

    def existing_observation(
        self,
        photo_id: str,
        capability_id: str,
        pack_hash: str | None = None,
    ) -> Observation | None:
        if pack_hash is None:
            row = self._conn.execute(
                """SELECT media_id, capability_id, provider_name, model_pack_hash,
                          payload_json, confidence, content_hash
                     FROM brain_observations
                    WHERE media_id=? AND capability_id=?
                    ORDER BY id LIMIT 1""",
                (photo_id, capability_id),
            ).fetchone()
        else:
            row = self._conn.execute(
                """SELECT media_id, capability_id, provider_name, model_pack_hash,
                          payload_json, confidence, content_hash
                     FROM brain_observations
                    WHERE media_id=? AND capability_id=?
                      AND IFNULL(model_pack_hash, '')=IFNULL(?, '')
                    ORDER BY id LIMIT 1""",
                (photo_id, capability_id, pack_hash),
            ).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        import json

        payload = json.loads(row[4] or "{}")
        return Observation(
            photo_id=str(row[0]),
            capability_id=str(row[1]),
            provider_name=str(row[2]),
            model_pack_hash=row[3],
            payload=payload if isinstance(payload, dict) else {"raw": payload},
            confidence=row[5],
            content_hash=row[6],
        )

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
