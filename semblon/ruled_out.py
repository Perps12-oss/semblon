"""Ruled-out decision path scaffold — CONTRACTS gap; no new schema columns.

Durable negative decision (R3), distinct from Ignore (deferred). Default OFF
behind ``gates.ruled_out`` / ``SEMBLON_GATE_RULED_OUT``.

**PROPOSAL (pending human VERIFY):** reuse existing ``decisions`` columns only —
``kind='reject'`` + ``policy_json.action='ruled_out'`` (vs Ignore's ``action='ignore'``).
No DDL. No cluster/person identity mutation in this scaffold.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from semblon import gates
from semblon.review import ReviewError, _record_decision, _require_face, _require_run
from semblon.store import connect, init_db

# R3 display matrix labels (five display states).
DISPLAY_UNKNOWN = "Unknown"
DISPLAY_POSSIBLE = "Possible"
DISPLAY_CONFIRMED = "Confirmed"
DISPLAY_RULED_OUT = "Ruled out"
DISPLAY_IGNORED = "Ignored"

DISPLAY_STATES = (
    DISPLAY_UNKNOWN,
    DISPLAY_POSSIBLE,
    DISPLAY_CONFIRMED,
    DISPLAY_RULED_OUT,
    DISPLAY_IGNORED,
)

# Evidence axis (machine) — R3: none · detected · similar · clustered
_EVIDENCE_NONE = frozenset({"none", "no_evidence"})
_EVIDENCE_WEAK = frozenset({"detected", "similar", "weak"})
_EVIDENCE_STRONG = frozenset({"clustered", "strong"})

# Decision axis (human) — R3: undecided · affirmed · rejected · deferred
_DECISION_UNDECIDED = frozenset({"undecided", "none", ""})
_DECISION_AFFIRMED = frozenset({"affirmed", "confirm", "confirmed"})
_DECISION_REJECTED = frozenset({"rejected", "reject", "ruled_out"})
_DECISION_DEFERRED = frozenset({"deferred", "defer", "ignore", "ignored"})

POLICY_ACTION = "ruled_out"
DECISION_KIND = "reject"  # existing CHECK; not a new kind value


def display_state(evidence: str, decision: str) -> str:
    """Map R3 evidence × decision axes to one of five display labels.

    Pure function. Impossible cells (affirm/reject with no evidence) raise
    ``ValueError``. See ``docs/R3-BRIEF.md`` display matrix and
    ``docs/CONTRACTS.md`` Ruled out (FLAGGED).
    """
    ev = (evidence or "").strip().lower()
    dec = (decision or "").strip().lower()

    if ev in _EVIDENCE_NONE:
        row = "none"
    elif ev in _EVIDENCE_WEAK:
        row = "weak"
    elif ev in _EVIDENCE_STRONG:
        row = "strong"
    else:
        raise ValueError(
            f"unknown evidence {evidence!r}; expected none|detected|similar|clustered "
            f"(aliases: no_evidence|weak|strong)"
        )

    if dec in _DECISION_UNDECIDED:
        col = "undecided"
    elif dec in _DECISION_AFFIRMED:
        col = "affirmed"
    elif dec in _DECISION_REJECTED:
        col = "rejected"
    elif dec in _DECISION_DEFERRED:
        col = "deferred"
    else:
        raise ValueError(
            f"unknown decision {decision!r}; expected undecided|affirmed|rejected|deferred"
        )

    if row == "none":
        if col == "undecided":
            return DISPLAY_UNKNOWN
        if col == "deferred":
            return DISPLAY_IGNORED
        raise ValueError(
            f"impossible display cell: evidence=none with decision={col} "
            "(cannot affirm or reject with no evidence)"
        )

    # weak / strong share the same decision columns in the R3 matrix
    if col == "undecided":
        return DISPLAY_POSSIBLE
    if col == "affirmed":
        return DISPLAY_CONFIRMED
    if col == "rejected":
        return DISPLAY_RULED_OUT
    return DISPLAY_IGNORED


def propose_ruled_out_policy(
    *,
    face_id: str | None = None,
    cluster_id: str | None = None,
    person_id: str | None = None,
    disposition: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build ``policy_json`` for a ruled-out decision. Does not write the store.

    **PROPOSAL:** ``action='ruled_out'`` distinguishes this from Ignore's
    ``action='ignore'`` while keeping ``decisions.kind='reject'``.
    """
    if bool(face_id) == bool(cluster_id):
        raise ReviewError("ruled_out policy requires exactly one of face_id or cluster_id")
    policy: dict[str, Any] = {
        "action": POLICY_ACTION,
        "disposition": disposition or "not_this_person",
    }
    if person_id is not None:
        policy["person_id"] = person_id
    if reason is not None:
        policy["reason"] = reason
    if face_id is not None:
        policy["subject"] = "face"
    else:
        policy["subject"] = "cluster"
    return policy


def _intended_row(
    *,
    run_id: str,
    pack_id: str,
    face_id: str | None,
    cluster_id: str | None,
    person_id: str | None,
    policy: dict[str, Any],
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Shape matching a ``decisions`` insert — existing columns only."""
    return {
        "decision_id": decision_id or uuid.uuid4().hex,
        "kind": DECISION_KIND,
        "face_id": face_id,
        "person_id": person_id,
        "cluster_id": cluster_id,
        "pack_id": pack_id,
        "score_top1": None,
        "score_top2": None,
        "margin": None,
        "policy_json": dict(policy),
        "run_id": run_id,
        "created_at": None,  # filled on write; dry_run leaves unset
    }


def record_ruled_out(
    store: Path,
    run_id: str,
    *,
    face_id: str | None = None,
    cluster_id: str | None = None,
    person_id: str | None = None,
    disposition: str | None = None,
    reason: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Scaffold write path for ruled-out.

    Always requires gate ``ruled_out`` enabled. Default ``dry_run=True`` returns
    the intended decision row **without** writing. Writes only when
    ``dry_run=False`` using existing columns: ``kind='reject'`` +
    ``policy_json.action='ruled_out'``. Does not mutate cluster/person rows.
    """
    gates.require_enabled("ruled_out")
    if bool(face_id) == bool(cluster_id):
        raise ReviewError("ruled_out requires exactly one of face_id or cluster_id")

    policy = propose_ruled_out_policy(
        face_id=face_id,
        cluster_id=cluster_id,
        person_id=person_id,
        disposition=disposition,
        reason=reason,
    )

    conn = connect(store)
    init_db(conn)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        resolved_cluster = cluster_id
        if face_id is not None:
            face = _require_face(conn, run_id, face_id)
            resolved_cluster = face["cluster_id"]
        elif cluster_id is not None:
            row = conn.execute(
                "SELECT 1 FROM clusters WHERE cluster_id=? AND run_id=?",
                (cluster_id, run_id),
            ).fetchone()
            if row is None:
                raise ReviewError(f"unknown cluster for run: {cluster_id}")

        # Candidate lives in policy_json. decisions.person_id is FK — only set when present.
        row_person_id = None
        if person_id is not None:
            prow = conn.execute(
                "SELECT 1 FROM persons WHERE person_id=?", (person_id,)
            ).fetchone()
            if prow is not None:
                row_person_id = person_id

        intended = _intended_row(
            run_id=run_id,
            pack_id=pack_id,
            face_id=face_id,
            cluster_id=resolved_cluster,
            person_id=row_person_id,
            policy=policy,
        )

        if dry_run:
            return {
                "run_id": run_id,
                "dry_run": True,
                "written": False,
                "gate": "ruled_out",
                "decision": intended,
                "note": "PROPOSAL pending VERIFY; no store write (dry_run=True)",
            }

        decision_id = _record_decision(
            conn,
            kind=DECISION_KIND,
            run_id=run_id,
            pack_id=pack_id,
            cluster_id=resolved_cluster,
            person_id=row_person_id,
            face_id=face_id,
            policy=policy,
        )
        conn.commit()
        row = conn.execute(
            "SELECT created_at, policy_json FROM decisions WHERE decision_id=?",
            (decision_id,),
        ).fetchone()
        intended["decision_id"] = decision_id
        if row is not None:
            intended["created_at"] = row["created_at"]
            intended["policy_json"] = json.loads(row["policy_json"])
        return {
            "run_id": run_id,
            "dry_run": False,
            "written": True,
            "gate": "ruled_out",
            "decision_id": decision_id,
            "decision": intended,
            "note": "wrote reject+policy action=ruled_out; no cluster/person mutation",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
