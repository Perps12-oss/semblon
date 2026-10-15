"""Home Inspector verb policy + thin apply wrappers (R3-BRIEF §4 / Artifact 1 §9–12).

Evidence relationship (machine) ≠ Proposed action (human).
Merge observations ≠ Assign to person — separate controls.

Mutations go through review_board.apply_* → review.py. No new schema columns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from semblon.gates import RULED_OUT, enabled as gate_enabled, require_human_note
from semblon.review_board import (
    ReviewUiError,
    apply_ignore,
    apply_merge,
    apply_name,
    apply_rule_out,
    apply_split,
)

# Verb ids used by Home + tests.
VERB_MERGE = "merge"
VERB_ASSIGN = "assign"
VERB_SPLIT = "split"
VERB_NAME = "name"
VERB_IGNORE = "ignore"
VERB_RULE_OUT = "rule_out"
VERB_NOTE = "note"

REASON_MERGE = "Select 2 or more items"
REASON_SPLIT = "Select a cluster to split"
REASON_NAME = "Select a face or cluster to name"
REASON_ASSIGN = "Open People and select a person first"
REASON_RULE_OUT_GATE = "Ruled out disabled (SEMBLON_RULED_OUT=0)"
REASON_RULE_OUT_SEL = "Select a cluster or face to rule out"
REASON_SPLIT_FACES = "Select faces within the cluster to split"
REASON_MERGE_CLUSTERS = "Select 2 or more clusters (Merge observations)"
REASON_NO_RUN = "No run selected"
REASON_NOTE = "Select a face or cluster to note"


def _clusters(selected: list[dict]) -> list[dict]:
    return [it for it in selected if it.get("kind") == "cluster" and it.get("cluster_id")]


def _faces(selected: list[dict]) -> list[dict]:
    return [it for it in selected if it.get("kind") in {"face", "unassigned"} and it.get("face_id")]


def _unique_cluster_ids(selected: list[dict]) -> list[str]:
    seen: list[str] = []
    for it in selected:
        cid = it.get("cluster_id")
        if cid and cid not in seen:
            seen.append(cid)
    return seen


def _nameable_item(selected: list[dict]) -> dict | None:
    """Prefer an explicit cluster; else a face/unassigned item."""
    clusters = _clusters(selected)
    if len(clusters) == 1 and len(_unique_cluster_ids(selected)) == 1:
        return clusters[0]
    faces = _faces(selected)
    if len(faces) == 1 and not clusters:
        return {"kind": "face", "face_id": faces[0]["face_id"]}
    if len(selected) == 1:
        it = selected[0]
        if it.get("kind") == "cluster" and it.get("cluster_id"):
            return it
        if it.get("face_id"):
            return {"kind": "face", "face_id": it["face_id"]}
    return None


def inspector_verb_states(
    selected: list[dict] | None,
    *,
    run_id: str | None = None,
    target_person_id: str | None = None,
    ruled_out_enabled: bool | None = None,
) -> dict[str, dict[str, Any]]:
    """Enablement + disable reasons for Inspector verbs.

    Artifact 1 §9–12:
    - Merge: ≥2 items; else "Select 2 or more items"
    - Split: cluster selected; else "Select a cluster to split"
    - Name: face or cluster; disabled when nothing selected
    - Ignore: never disabled
    - Assign to person: separate from Merge (needs one observation + person)
    - Rule out: gated by SEMBLON_RULED_OUT (default ON; opt out =0)
    """
    items = list(selected or [])
    if ruled_out_enabled is None:
        ruled_out_enabled = gate_enabled(RULED_OUT)

    def _state(enabled: bool, reason: str | None = None, **extra: Any) -> dict[str, Any]:
        return {"enabled": bool(enabled), "reason": reason, **extra}

    if not run_id:
        base_off = _state(False, REASON_NO_RUN)
        return {
            VERB_MERGE: dict(base_off),
            VERB_ASSIGN: dict(base_off),
            VERB_SPLIT: dict(base_off),
            VERB_NAME: dict(base_off),
            VERB_IGNORE: _state(True, None),  # never disabled
            VERB_NOTE: dict(base_off),
            VERB_RULE_OUT: (
                dict(base_off)
                if ruled_out_enabled
                else _state(False, REASON_RULE_OUT_GATE)
            ),
        }

    cluster_ids = _unique_cluster_ids(items)
    clusters = _clusters(items)
    faces = _faces(items)
    nameable = _nameable_item(items)

    # Merge observations — clusters only; never Assign.
    if len(cluster_ids) >= 2:
        merge = _state(True, None, cluster_ids=cluster_ids)
    elif len(items) < 2:
        merge = _state(False, REASON_MERGE)
    else:
        merge = _state(False, REASON_MERGE_CLUSTERS)

    # Assign to person — separate control from Merge.
    if nameable is not None and target_person_id:
        assign = _state(True, None, item=nameable, person_id=target_person_id)
    else:
        assign = _state(False, REASON_ASSIGN)

    # Split — needs a cluster; apply still needs face ids.
    if len(cluster_ids) == 1 and (clusters or any(it.get("cluster_id") for it in items)):
        cid = cluster_ids[0]
        face_ids = sorted(
            {
                f["face_id"]
                for f in faces
                if f.get("cluster_id") == cid and f.get("face_id")
            }
        )
        # Also accept face_ids nested on the cluster item.
        for c in clusters:
            if c.get("cluster_id") == cid:
                for m in c.get("members") or []:
                    fid = m.get("face_id") if isinstance(m, dict) else None
                    if fid and fid in {f.get("face_id") for f in faces}:
                        face_ids = sorted(set(face_ids) | {fid})
        # Faces selected that belong to this cluster (kind=face with cluster_id).
        for it in items:
            if it.get("kind") == "face" and it.get("cluster_id") == cid and it.get("face_id"):
                face_ids = sorted(set(face_ids) | {it["face_id"]})
        split = _state(True, None, cluster_id=cid, face_ids=face_ids)
    else:
        split = _state(False, REASON_SPLIT)

    # Name
    if nameable is not None:
        name = _state(True, None, item=nameable)
    elif not items:
        name = _state(False, REASON_NAME)
    else:
        name = _state(False, REASON_NAME)

    # Ignore — never disabled (Artifact 1 §12).
    ignore_item = nameable
    if ignore_item is None and items:
        # Best-effort: first cluster or face.
        if clusters:
            ignore_item = clusters[0]
        elif faces:
            ignore_item = {"kind": "face", "face_id": faces[0]["face_id"]}
        elif items[0].get("cluster_id"):
            ignore_item = {
                "kind": "cluster",
                "cluster_id": items[0]["cluster_id"],
            }
        elif items[0].get("face_id"):
            ignore_item = {"kind": "face", "face_id": items[0]["face_id"]}
    ignore = _state(True, None, item=ignore_item)

    # Rule out
    if not ruled_out_enabled:
        rule_out = _state(False, REASON_RULE_OUT_GATE, gate_note=require_human_note(RULED_OUT))
    elif nameable is not None:
        rule_out = _state(True, None, item=nameable)
    else:
        rule_out = _state(False, REASON_RULE_OUT_SEL)

    # Note — same subject as Ignore/Name when a cluster or face is selected.
    if ignore_item is not None:
        note = _state(True, None, item=ignore_item)
    else:
        note = _state(False, REASON_NOTE)

    return {
        VERB_MERGE: merge,
        VERB_ASSIGN: assign,
        VERB_SPLIT: split,
        VERB_NAME: name,
        VERB_IGNORE: ignore,
        VERB_NOTE: note,
        VERB_RULE_OUT: rule_out,
    }


def evidence_lines_for_selection(
    *,
    run_id: str | None,
    media_id: str | None = None,
    selected: list[dict] | None = None,
    board_lines: list[str] | None = None,
    candidate_person: str | None = None,
    decision_note: str | None = None,
) -> list[str]:
    """Machine evidence block. Never implies identity certainty."""
    items = list(selected or [])
    cluster_ids = _unique_cluster_ids(items)
    face_n = len(_faces(items))
    lines = [
        "Evidence relationship (machine)",
        f"run={run_id or '—'}",
    ]
    if media_id:
        lines.append(f"media={media_id}")
    if cluster_ids:
        lines.append(f"cluster membership: {', '.join(c[:12] for c in cluster_ids)}")
    else:
        lines.append("cluster membership: none selected")
    if face_n:
        lines.append(f"faces selected: {face_n}")
    if candidate_person:
        lines.append(f"candidate person: {candidate_person}  (not assigned)")
    else:
        lines.append("candidate person: —")
    if decision_note:
        lines.append(f"existing decision: {decision_note}")
    else:
        lines.append("existing decision: —")
    lines.append("Group ≠ person. Similarity is not identity.")
    if board_lines:
        lines.append("---")
        lines.extend(board_lines)
    return lines


def action_block_labels(states: dict[str, dict[str, Any]]) -> list[str]:
    """Human proposed-action labels with disable reasons (for text inspectors)."""
    labels = [
        ("Merge observations", VERB_MERGE),
        ("Assign to person", VERB_ASSIGN),
        ("Split", VERB_SPLIT),
        ("Name", VERB_NAME),
        ("Rule out", VERB_RULE_OUT),
        ("Ignore", VERB_IGNORE),
    ]
    out = ["Proposed action (human)"]
    out.append("Merge observations ≠ Assign to person")
    for label, key in labels:
        st = states.get(key) or {}
        if st.get("enabled"):
            out.append(f"{label}: available")
        else:
            reason = st.get("reason") or "unavailable"
            out.append(f"{label}: disabled — {reason}")
    return out


def items_from_media_board(board: dict, media_id: str | None) -> list[dict]:
    """Build selectable review-shaped items from a canvas board media selection.

    Clusters appear first; member faces are listed so Split can pick face ids.
    """
    if not media_id or not board:
        return []
    faces = [f for f in (board.get("faces") or []) if f.get("media_id") == media_id]
    by_cluster: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    for f in faces:
        cid = f.get("cluster_id")
        rec = {
            "kind": "face",
            "face_id": f.get("face_id"),
            "cluster_id": cid,
            "person_id": f.get("person_id"),
            "media_id": media_id,
        }
        if cid:
            by_cluster.setdefault(cid, []).append(rec)
        else:
            unassigned.append(rec)
    items: list[dict] = []
    for cid, members in by_cluster.items():
        person_names = sorted(
            {m.get("person_id") for m in members if m.get("person_id")}
        )
        items.append(
            {
                "kind": "cluster",
                "cluster_id": cid,
                "face_count": len(members),
                "members": members,
                "named": bool(person_names),
                "person_names": [str(p) for p in person_names],
                "media_id": media_id,
            }
        )
        # Member faces for Split multi-select (still observations, not persons).
        items.extend(members)
    for u in unassigned:
        u2 = dict(u)
        u2["kind"] = "face"
        items.append(u2)
    return items


def flatten_board_items_for_inspector(board_items: list[dict]) -> list[dict]:
    """Unknown/Review board items → Inspector selection rows (cluster + member faces)."""
    out: list[dict] = []
    for it in board_items:
        if it.get("kind") == "cluster":
            out.append(it)
            for m in it.get("members") or []:
                out.append(
                    {
                        "kind": "face",
                        "face_id": m.get("face_id"),
                        "cluster_id": it.get("cluster_id"),
                        "person_id": m.get("person_id"),
                        "media_id": m.get("media_id"),
                    }
                )
        elif it.get("kind") in {"face", "unassigned"} or it.get("face_id"):
            out.append(
                {
                    "kind": "face",
                    "face_id": it.get("face_id"),
                    "cluster_id": it.get("cluster_id"),
                    "person_id": it.get("person_id"),
                    "media_id": it.get("media_id"),
                }
            )
    return out


def apply_inspector_merge(store: Path, run_id: str, cluster_ids: list[str]) -> dict:
    """Merge observations (clusters). Not Assign to person."""
    if len(cluster_ids) < 2:
        raise ReviewUiError(REASON_MERGE)
    return apply_merge(store, run_id, list(cluster_ids))


def apply_inspector_split(
    store: Path, run_id: str, cluster_id: str, face_ids: list[str]
) -> dict:
    if not face_ids:
        raise ReviewUiError(REASON_SPLIT_FACES)
    return apply_split(store, run_id, cluster_id, list(face_ids))


def apply_inspector_name(store: Path, run_id: str, item: dict, display_name: str) -> dict:
    name = (display_name or "").strip()
    if not name:
        raise ReviewUiError("display name must be non-empty")
    return apply_name(store, run_id, item, name)


def apply_inspector_assign(
    store: Path,
    run_id: str,
    item: dict,
    *,
    person_id: str,
    display_name: str,
) -> dict:
    """Assign observation to an existing person — not Merge observations."""
    if not person_id:
        raise ReviewUiError(REASON_ASSIGN)
    from semblon.review import name_cluster, name_face

    if item.get("kind") == "cluster":
        return name_cluster(
            store,
            run_id,
            item["cluster_id"],
            display_name,
            attach_to_person_id=person_id,
            create_new=False,
        )
    fid = item.get("face_id")
    if not fid:
        raise ReviewUiError(REASON_ASSIGN)
    return name_face(
        store,
        run_id,
        fid,
        display_name,
        attach_to_person_id=person_id,
        create_new=False,
    )


def apply_inspector_ignore(store: Path, run_id: str, item: dict) -> dict:
    if item is None:
        raise ReviewUiError("select a cluster or face to ignore")
    return apply_ignore(store, run_id, item)


def apply_inspector_rule_out(store: Path, run_id: str, item: dict) -> dict:
    if item is None:
        raise ReviewUiError(REASON_RULE_OUT_SEL)
    return apply_rule_out(store, run_id, item)
