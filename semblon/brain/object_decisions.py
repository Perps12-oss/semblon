"""Human same-object and different-object decisions.

One H-OBJ observation, one evidence row, and one SAME_AS edge.
Latest human claim wins the edge state. Older evidence stays.
Does not write faces, persons, or review decisions.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

CAPABILITY = "H-OBJ"
PROVIDER = "human"
SAME_CLAIM = "human:same_object"
DIFF_CLAIM = "human:different_object"


class ObjectDecisionError(ValueError):
    """A correction the graph cannot record. The message is safe to show."""


def confirm_same(
    conn: sqlite3.Connection,
    *,
    media_id: str,
    left_id: int,
    right_id: int,
) -> dict:
    return _decide(conn, media_id=media_id, left_id=left_id, right_id=right_id, same=True)


def confirm_different(
    conn: sqlite3.Connection,
    *,
    media_id: str,
    left_id: int,
    right_id: int,
) -> dict:
    return _decide(conn, media_id=media_id, left_id=left_id, right_id=right_id, same=False)


def _decide(
    conn: sqlite3.Connection,
    *,
    media_id: str,
    left_id: int,
    right_id: int,
    same: bool,
) -> dict:
    lo, hi = _pair(left_id, right_id)
    _require_object(conn, lo)
    _require_object(conn, hi)
    media_id = str(media_id or "").strip()
    if not media_id or conn.execute(
        "SELECT 1 FROM media WHERE media_id=?",
        (media_id,),
    ).fetchone() is None:
        raise ObjectDecisionError("That photo is not in the archive.")
    if not _has_table(conn, "brain_observations") or not _has_table(conn, "brain_edges"):
        raise ObjectDecisionError("Memory is not ready for this correction.")
    claim = SAME_CLAIM if same else DIFF_CLAIM
    try:
        if _latest_claim(conn, lo, hi) == claim:
            return _align_existing(conn, lo, hi, same=same)
        stem = f"{'same' if same else 'diff'}:{lo}:{hi}"
        pack = _alloc_pack(conn, media_id, stem)
        now = _now()
        payload = json.dumps(
            {
                "decision": "same" if same else "different",
                "left": lo,
                "right": hi,
                "origin": "human",
            },
            sort_keys=True,
        )
        cur = conn.execute(
            """
            INSERT INTO brain_observations(
                media_id, region_x, region_y, region_w, region_h,
                capability_id, provider_name, model_pack_hash,
                payload_json, confidence, content_hash, created_at)
            VALUES (?, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (media_id, CAPABILITY, PROVIDER, pack, payload, 1.0, now),
        )
        observation_id = int(cur.lastrowid)
        edge = _find_edge(conn, lo, hi)
        if edge is None:
            edge_id = _insert_edge(
                conn,
                lo,
                hi,
                state="none" if same else "contradicted",
                confidence=1.0 if same else 0.0,
                support=1 if same else 0,
                contradict=0 if same else 1,
                now=now,
            )
        else:
            edge_id = int(edge["id"])
            if same:
                conn.execute(
                    """
                    UPDATE brain_edges
                       SET contradiction_state='none', confidence=1.0,
                           last_seen=?, updated_at=?
                     WHERE id=?
                    """,
                    (now, now, edge_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE brain_edges
                       SET contradiction_state='contradicted', confidence=0.0,
                           contradict_count=contradict_count + 1,
                           last_seen=?, updated_at=?
                     WHERE id=?
                    """,
                    (now, now, edge_id),
                )
        conn.execute(
            """
            INSERT INTO brain_evidence(
                observation_id, edge_id, node_id, role, weight, claim_key, created_at)
            VALUES (?, ?, NULL, ?, 1.0, ?, ?)
            """,
            (
                observation_id,
                edge_id,
                "supports" if same else "contradicts",
                claim,
                now,
            ),
        )
        conn.commit()
        return {
            "reused": False,
            "repaired": False,
            "edge_id": edge_id,
            "observation_id": observation_id,
            "state": "none" if same else "contradicted",
        }
    except ObjectDecisionError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise


def _align_existing(conn: sqlite3.Connection, lo: int, hi: int, *, same: bool) -> dict:
    """Repeat of the latest human claim. No second observation. Repair the edge."""
    edge = _find_edge(conn, lo, hi)
    now = _now()
    state = "none" if same else "contradicted"
    if edge is None:
        edge_id = _insert_edge(
            conn,
            lo,
            hi,
            state=state,
            confidence=1.0 if same else 0.0,
            support=1 if same else 0,
            contradict=0 if same else 1,
            now=now,
        )
        conn.commit()
        return {"reused": True, "repaired": True, "edge_id": edge_id, "state": state}
    edge_id = int(edge["id"])
    current = str(edge["contradiction_state"] or "")
    if same and current != "none":
        conn.execute(
            """
            UPDATE brain_edges
               SET contradiction_state='none', confidence=1.0,
                   last_seen=?, updated_at=?
             WHERE id=?
            """,
            (now, now, edge_id),
        )
        conn.commit()
        return {"reused": True, "repaired": True, "edge_id": edge_id, "state": state}
    if not same and current != "contradicted":
        conn.execute(
            """
            UPDATE brain_edges
               SET contradiction_state='contradicted', confidence=0.0,
                   last_seen=?, updated_at=?
             WHERE id=?
            """,
            (now, now, edge_id),
        )
        conn.commit()
        return {"reused": True, "repaired": True, "edge_id": edge_id, "state": state}
    return {"reused": True, "repaired": False, "edge_id": edge_id, "state": state}


def _pair(left_id: int, right_id: int) -> tuple[int, int]:
    left, right = int(left_id), int(right_id)
    if left <= 0 or right <= 0:
        raise ObjectDecisionError("That correction is not available.")
    if left == right:
        raise ObjectDecisionError("Pick two different objects.")
    return (left, right) if left < right else (right, left)


def _require_object(conn: sqlite3.Connection, node_id: int) -> None:
    if not _has_table(conn, "brain_nodes"):
        raise ObjectDecisionError("Memory is not ready for this correction.")
    row = conn.execute(
        "SELECT node_type FROM brain_nodes WHERE id=?",
        (int(node_id),),
    ).fetchone()
    if row is None or str(row["node_type"]) != "ObjectCluster":
        raise ObjectDecisionError("That correction only applies to objects.")


def _latest_claim(conn: sqlite3.Connection, lo: int, hi: int) -> str | None:
    same_stem = f"same:{lo}:{hi}"
    diff_stem = f"diff:{lo}:{hi}"
    row = conn.execute(
        """
        SELECT ev.claim_key
          FROM brain_evidence ev
          JOIN brain_observations o ON o.id = ev.observation_id
         WHERE o.capability_id = ?
           AND o.provider_name = ?
           AND ev.claim_key IN (?, ?)
           AND (
                o.model_pack_hash = ?
             OR o.model_pack_hash LIKE ?
             OR o.model_pack_hash = ?
             OR o.model_pack_hash LIKE ?
           )
         ORDER BY ev.created_at DESC, ev.id DESC
         LIMIT 1
        """,
        (
            CAPABILITY,
            PROVIDER,
            SAME_CLAIM,
            DIFF_CLAIM,
            same_stem,
            same_stem + ":%",
            diff_stem,
            diff_stem + ":%",
        ),
    ).fetchone()
    if row is None:
        return None
    return str(row["claim_key"])


def _alloc_pack(conn: sqlite3.Connection, media_id: str, stem: str) -> str:
    for generation in range(1000):
        candidate = stem if generation == 0 else f"{stem}:{generation + 1}"
        row = conn.execute(
            """
            SELECT 1 FROM brain_observations
             WHERE media_id = ? AND capability_id = ? AND IFNULL(model_pack_hash, '') = ?
            """,
            (media_id, CAPABILITY, candidate),
        ).fetchone()
        if row is None:
            return candidate
    raise ObjectDecisionError("That correction could not be saved.")


def _find_edge(conn: sqlite3.Connection, lo: int, hi: int):
    return conn.execute(
        """
        SELECT id, source_node_id, target_node_id, contradiction_state, contradict_count
          FROM brain_edges
         WHERE edge_type = 'SAME_AS'
           AND (
                (source_node_id = ? AND target_node_id = ?)
             OR (source_node_id = ? AND target_node_id = ?)
           )
         ORDER BY CASE WHEN source_node_id = ? THEN 0 ELSE 1 END, id
         LIMIT 1
        """,
        (lo, hi, hi, lo, lo),
    ).fetchone()


def _insert_edge(
    conn: sqlite3.Connection,
    lo: int,
    hi: int,
    *,
    state: str,
    confidence: float,
    support: int,
    contradict: int,
    now: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO brain_edges(
            source_node_id, target_node_id, edge_type, confidence,
            support_count, contradict_count, first_seen, last_seen,
            contradiction_state, created_at, updated_at)
        VALUES (?, ?, 'SAME_AS', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (lo, hi, float(confidence), int(support), int(contradict), now, now, state, now, now),
    )
    return int(cur.lastrowid)


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
