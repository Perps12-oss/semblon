"""Artifact 2 — Asset state = (Ingest, Analysis, Identity).

Three channels must not collide:
  Identity → corner notch (aggregate worst unresolved across faces)
  Analysis → border / ring (shape, not hue)
  Ingest   → center glyph only (ok=none · failed=⚠ · missing=broken)

Pure helpers — no Tk, no schema columns, never writes person_id.
Authority: docs/r3-artifacts/02-state-triple.md, R3-BRIEF §1–§2.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

INGEST_OK = "ok"
INGEST_FAILED = "failed"
INGEST_MISSING = "missing"
INGEST_VALUES = frozenset({INGEST_OK, INGEST_FAILED, INGEST_MISSING})

ANALYSIS_QUEUED = "queued"
ANALYSIS_RUNNING = "running"
ANALYSIS_PAUSED = "paused"
ANALYSIS_DONE = "done"
ANALYSIS_FAILED = "failed"
ANALYSIS_STALE = "stale"
ANALYSIS_VALUES = frozenset(
    {
        ANALYSIS_QUEUED,
        ANALYSIS_RUNNING,
        ANALYSIS_PAUSED,
        ANALYSIS_DONE,
        ANALYSIS_FAILED,
        ANALYSIS_STALE,
    }
)

IDENTITY_NONE = "none"
IDENTITY_UNKNOWN = "unknown"
IDENTITY_POSSIBLE = "possible"
IDENTITY_CONFIRMED = "confirmed"
IDENTITY_MIXED = "mixed"
IDENTITY_VALUES = frozenset(
    {
        IDENTITY_NONE,
        IDENTITY_UNKNOWN,
        IDENTITY_POSSIBLE,
        IDENTITY_CONFIRMED,
        IDENTITY_MIXED,
    }
)

FACE_UNKNOWN = "unknown"
FACE_POSSIBLE = "possible"
FACE_CONFIRMED = "confirmed"
FACE_RULED_OUT = "ruled_out"
FACE_IGNORED = "ignored"

NOTCH_EMPTY_DIM = "empty_outline_dim"
NOTCH_DASHED_6_4 = "dashed_6_4"
NOTCH_DASHED_3_2 = "dashed_3_2"
NOTCH_SOLID = "solid"
NOTCH_SOLID_NEQ = "solid_neq"

RING_HOLLOW = "hollow"
RING_PARTIAL = "partial"
RING_PARTIAL_PAUSED = "partial_paused"
RING_SOLID = "solid"
RING_GAP_BANG = "gap_bang"
RING_DOTTED = "dotted"

GLYPH_NONE = "none"
GLYPH_WARN = "warn"
GLYPH_BROKEN = "broken"


@dataclass(frozen=True)
class NotchSpec:
    aggregate: str
    style: str
    neq: bool = False


@dataclass(frozen=True)
class RingSpec:
    analysis: str
    style: str
    bang: bool = False
    pause_mark: bool = False


@dataclass(frozen=True)
class GlyphSpec:
    ingest: str
    style: str
    mark: str


@dataclass(frozen=True)
class StateTriple:
    ingest: str
    analysis: str
    identity: str
    notch: NotchSpec
    ring: RingSpec
    glyph: GlyphSpec

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_FACE_PRIORITY = (
    FACE_UNKNOWN,
    FACE_POSSIBLE,
    FACE_CONFIRMED,
    FACE_RULED_OUT,
    FACE_IGNORED,
)

_NOTCH_BY_IDENTITY = {
    IDENTITY_NONE: NotchSpec(IDENTITY_NONE, NOTCH_EMPTY_DIM, neq=False),
    IDENTITY_UNKNOWN: NotchSpec(IDENTITY_UNKNOWN, NOTCH_DASHED_6_4, neq=False),
    IDENTITY_POSSIBLE: NotchSpec(IDENTITY_POSSIBLE, NOTCH_DASHED_3_2, neq=False),
    IDENTITY_CONFIRMED: NotchSpec(IDENTITY_CONFIRMED, NOTCH_SOLID, neq=False),
    IDENTITY_MIXED: NotchSpec(IDENTITY_MIXED, NOTCH_SOLID_NEQ, neq=True),
}

_RING_BY_ANALYSIS = {
    ANALYSIS_QUEUED: RingSpec(ANALYSIS_QUEUED, RING_HOLLOW),
    ANALYSIS_RUNNING: RingSpec(ANALYSIS_RUNNING, RING_PARTIAL),
    ANALYSIS_PAUSED: RingSpec(ANALYSIS_PAUSED, RING_PARTIAL_PAUSED, pause_mark=True),
    ANALYSIS_DONE: RingSpec(ANALYSIS_DONE, RING_SOLID),
    ANALYSIS_FAILED: RingSpec(ANALYSIS_FAILED, RING_GAP_BANG, bang=True),
    ANALYSIS_STALE: RingSpec(ANALYSIS_STALE, RING_DOTTED),
}

_GLYPH_BY_INGEST = {
    INGEST_OK: GlyphSpec(INGEST_OK, GLYPH_NONE, ""),
    INGEST_FAILED: GlyphSpec(INGEST_FAILED, GLYPH_WARN, "⚠"),
    INGEST_MISSING: GlyphSpec(INGEST_MISSING, GLYPH_BROKEN, "broken"),
}

_LIST_NOTCH = {
    IDENTITY_NONE: "◇",
    IDENTITY_UNKNOWN: "⬚",
    IDENTITY_POSSIBLE: "◧",
    IDENTITY_CONFIRMED: "◆",
    IDENTITY_MIXED: "◆≠",
}
_LIST_RING = {
    ANALYSIS_QUEUED: "○",
    ANALYSIS_RUNNING: "◐",
    ANALYSIS_PAUSED: "◑",
    ANALYSIS_DONE: "●",
    ANALYSIS_FAILED: "○!",
    ANALYSIS_STALE: "◌",
}
_LIST_GLYPH = {
    INGEST_OK: "·",
    INGEST_FAILED: "⚠",
    INGEST_MISSING: "◻/",
}


def _policy(decision: Mapping[str, Any]) -> dict:
    raw = decision.get("policy_json")
    if raw is None and isinstance(decision.get("policy"), dict):
        return dict(decision["policy"])
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    try:
        pol = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return pol if isinstance(pol, dict) else {}


def decision_action_sets(
    decisions: Iterable[Mapping[str, Any]] | None,
) -> tuple[set[str], set[str], set[str], set[str]]:
    ignored_faces: set[str] = set()
    ignored_clusters: set[str] = set()
    ruled_out_faces: set[str] = set()
    ruled_out_clusters: set[str] = set()
    for d in decisions or ():
        if d.get("kind") != "reject":
            continue
        pol = _policy(d)
        action = pol.get("action")
        fid = d.get("face_id")
        cid = d.get("cluster_id")
        if action == "ignore":
            if fid:
                ignored_faces.add(str(fid))
            elif cid:
                ignored_clusters.add(str(cid))
        elif action == "rule_out":
            if fid:
                ruled_out_faces.add(str(fid))
            elif cid:
                ruled_out_clusters.add(str(cid))
    return ignored_faces, ignored_clusters, ruled_out_faces, ruled_out_clusters


def face_identity_state(
    face: Mapping[str, Any],
    *,
    ignored_faces: set[str] | None = None,
    ignored_clusters: set[str] | None = None,
    ruled_out_faces: set[str] | None = None,
    ruled_out_clusters: set[str] | None = None,
    cluster_status: Mapping[str, str] | None = None,
) -> str:
    fid = str(face.get("face_id") or "")
    cid = face.get("cluster_id")
    cid_s = str(cid) if cid else None
    ignored_faces = ignored_faces or set()
    ignored_clusters = ignored_clusters or set()
    ruled_out_faces = ruled_out_faces or set()
    ruled_out_clusters = ruled_out_clusters or set()
    cluster_status = cluster_status or {}

    if fid and fid in ignored_faces:
        return FACE_IGNORED
    if cid_s and (cid_s in ignored_clusters or cluster_status.get(cid_s) == "ignored"):
        return FACE_IGNORED
    if fid and fid in ruled_out_faces:
        return FACE_RULED_OUT
    if cid_s and cid_s in ruled_out_clusters:
        return FACE_RULED_OUT
    if face.get("person_id"):
        return FACE_CONFIRMED
    if cid_s:
        return FACE_POSSIBLE
    return FACE_UNKNOWN


def aggregate_identity(face_states: Iterable[str]) -> str:
    states = [s for s in face_states if s in _FACE_PRIORITY]
    if not states:
        return IDENTITY_NONE
    active = [s for s in states if s != FACE_IGNORED]
    if not active:
        return IDENTITY_NONE
    if any(s == FACE_UNKNOWN for s in active):
        return IDENTITY_UNKNOWN
    if any(s == FACE_POSSIBLE for s in active):
        return IDENTITY_POSSIBLE
    has_confirmed = any(s == FACE_CONFIRMED for s in active)
    has_ruled_out = any(s == FACE_RULED_OUT for s in active)
    if has_confirmed and has_ruled_out:
        return IDENTITY_MIXED
    if has_confirmed:
        return IDENTITY_CONFIRMED
    return IDENTITY_NONE


def notch_for(identity: str) -> NotchSpec:
    if identity not in _NOTCH_BY_IDENTITY:
        raise ValueError(f"unknown identity aggregate: {identity!r}")
    return _NOTCH_BY_IDENTITY[identity]


def ring_for(analysis: str) -> RingSpec:
    if analysis not in _RING_BY_ANALYSIS:
        raise ValueError(f"unknown analysis state: {analysis!r}")
    return _RING_BY_ANALYSIS[analysis]


def glyph_for(ingest: str) -> GlyphSpec:
    if ingest not in _GLYPH_BY_INGEST:
        raise ValueError(f"unknown ingest state: {ingest!r}")
    return _GLYPH_BY_INGEST[ingest]


def derive_ingest(
    *,
    path: str | Path | None = None,
    path_exists: bool | None = None,
    ingest_failed: bool = False,
    exists_fn: Callable[[Path], bool] | None = None,
) -> str:
    if ingest_failed:
        return INGEST_FAILED
    if path_exists is not None:
        return INGEST_OK if path_exists else INGEST_MISSING
    if path is None or path == "":
        return INGEST_MISSING
    p = Path(path)
    check = exists_fn or (lambda q: q.is_file())
    return INGEST_OK if check(p) else INGEST_MISSING


def derive_analysis(
    *,
    has_observation: bool = False,
    run_finished: bool | None = None,
    job_state: str | None = None,
    is_current_media: bool = False,
    stale: bool = False,
) -> str:
    if stale or job_state in (ANALYSIS_STALE, "stalled"):
        return ANALYSIS_STALE

    js = (job_state or "").lower() or None
    if js in ("started", "progress"):
        js = ANALYSIS_RUNNING
    elif js == "completed":
        js = ANALYSIS_DONE
    elif js == "cancelled":
        js = ANALYSIS_PAUSED
    elif js == "stalled":
        js = ANALYSIS_STALE

    if js == ANALYSIS_STALE:
        return ANALYSIS_STALE
    if is_current_media and js == ANALYSIS_FAILED:
        return ANALYSIS_FAILED
    if is_current_media and js == ANALYSIS_PAUSED:
        return ANALYSIS_PAUSED
    if is_current_media and js == ANALYSIS_RUNNING:
        return ANALYSIS_RUNNING
    if js == ANALYSIS_QUEUED and not has_observation:
        return ANALYSIS_QUEUED
    if js == ANALYSIS_FAILED and not has_observation:
        return ANALYSIS_FAILED
    if js == ANALYSIS_PAUSED and not has_observation:
        return ANALYSIS_PAUSED

    if has_observation:
        return ANALYSIS_DONE
    if run_finished is False:
        return ANALYSIS_QUEUED
    if run_finished is True:
        return ANALYSIS_DONE
    return ANALYSIS_QUEUED


def build_triple(*, ingest: str, analysis: str, identity: str) -> StateTriple:
    if ingest not in INGEST_VALUES:
        raise ValueError(f"invalid ingest: {ingest!r}")
    if analysis not in ANALYSIS_VALUES:
        raise ValueError(f"invalid analysis: {analysis!r}")
    if identity not in IDENTITY_VALUES:
        raise ValueError(f"invalid identity: {identity!r}")
    return StateTriple(
        ingest=ingest,
        analysis=analysis,
        identity=identity,
        notch=notch_for(identity),
        ring=ring_for(analysis),
        glyph=glyph_for(ingest),
    )


def state_triple_for_media(
    media: Mapping[str, Any],
    faces: Iterable[Mapping[str, Any]],
    *,
    decisions: Iterable[Mapping[str, Any]] | None = None,
    cluster_status: Mapping[str, str] | None = None,
    has_observation: bool | None = None,
    run_finished: bool | None = None,
    job_state: str | None = None,
    is_current_media: bool = False,
    stale: bool = False,
    path_exists: bool | None = None,
    ingest_failed: bool = False,
    exists_fn: Callable[[Path], bool] | None = None,
) -> StateTriple:
    ign_f, ign_c, rule_f, rule_c = decision_action_sets(decisions)
    face_list = list(faces)
    face_states = [
        face_identity_state(
            f,
            ignored_faces=ign_f,
            ignored_clusters=ign_c,
            ruled_out_faces=rule_f,
            ruled_out_clusters=rule_c,
            cluster_status=cluster_status,
        )
        for f in face_list
    ]
    identity = aggregate_identity(face_states)
    if has_observation is None:
        has_observation = bool(face_list) or bool(media.get("has_observation"))
    ingest = derive_ingest(
        path=media.get("path"),
        path_exists=path_exists,
        ingest_failed=ingest_failed,
        exists_fn=exists_fn,
    )
    analysis = derive_analysis(
        has_observation=bool(has_observation),
        run_finished=run_finished,
        job_state=job_state,
        is_current_media=is_current_media,
        stale=stale,
    )
    return build_triple(ingest=ingest, analysis=analysis, identity=identity)


def channel_markers(triple: StateTriple) -> str:
    n = _LIST_NOTCH[triple.identity]
    r = _LIST_RING[triple.analysis]
    g = _LIST_GLYPH[triple.ingest]
    return f"{n} {r} {g}"


def format_media_card_label(
    media: Mapping[str, Any],
    triple: StateTriple,
    *,
    face_count: int | None = None,
    item_count: int | None = None,
) -> str:
    mid_faces = face_count
    if mid_faces is None:
        mid_faces = int(media.get("face_count") or 0)
    mid_items = item_count
    if mid_items is None:
        mid_items = media.get("item_count")
    z = " zero-face" if mid_faces == 0 else ""
    src = media.get("source_type") or "?"
    path = media.get("path") or "?"
    marks = channel_markers(triple)
    if mid_items is None:
        return f"{marks}  {src}  faces={mid_faces}{z}  {path}"
    return f"{marks}  {src}  faces={mid_faces} items={mid_items}{z}  {path}"


def library_include_media(triple: StateTriple) -> bool:
    return triple.ingest != INGEST_FAILED


def media_inspector_triple_line(triple: StateTriple) -> str:
    return (
        f"state=({triple.ingest}, {triple.analysis}, {triple.identity})  "
        f"notch={triple.notch.style}  ring={triple.ring.style}  "
        f"glyph={triple.glyph.style}"
    )


def triples_for_board(
    board: Mapping[str, Any],
    *,
    media_rows: Iterable[Mapping[str, Any]] | None = None,
    decisions: Iterable[Mapping[str, Any]] | None = None,
    cluster_status: Mapping[str, str] | None = None,
    run_finished: bool | None = None,
    job_state: str | None = None,
    current_media_id: str | None = None,
    stale_media_ids: Iterable[str] | None = None,
    path_exists_by_id: Mapping[str, bool] | None = None,
    exists_fn: Callable[[Path], bool] | None = None,
    analysis_by_media: Mapping[str, str] | None = None,
    observed_media_ids: Iterable[str] | None = None,
) -> dict[str, StateTriple]:
    media_list = list(media_rows if media_rows is not None else board.get("media") or [])
    faces = list(board.get("faces") or [])
    items = list(board.get("items") or [])
    decs = list(decisions if decisions is not None else board.get("decisions") or [])
    stale_set = set(stale_media_ids or ())
    path_map = dict(path_exists_by_id or {})
    analysis_map = dict(analysis_by_media or {})

    faces_by: dict[str, list[dict]] = {}
    for f in faces:
        mid = f.get("media_id")
        if mid is None:
            continue
        faces_by.setdefault(str(mid), []).append(dict(f))

    if observed_media_ids is not None:
        obs_media: set[str] = {str(x) for x in observed_media_ids}
    else:
        obs_media = set(faces_by)
        for it in items:
            mid = it.get("media_id")
            if mid is not None:
                obs_media.add(str(mid))
        if board.get("media") is not None and media_rows is None:
            for m in media_list:
                mid = m.get("media_id")
                if mid is not None:
                    obs_media.add(str(mid))

    out: dict[str, StateTriple] = {}
    for m in media_list:
        mid = str(m.get("media_id") or "")
        if not mid:
            continue
        pe = path_map.get(mid)
        js = analysis_map.get(mid, job_state)
        analysis_override = None
        if mid in analysis_map and analysis_map[mid] in ANALYSIS_VALUES:
            analysis_override = analysis_map[mid]
        triple = state_triple_for_media(
            m,
            faces_by.get(mid, []),
            decisions=decs,
            cluster_status=cluster_status,
            has_observation=mid in obs_media or bool(faces_by.get(mid)),
            run_finished=run_finished,
            job_state=None if analysis_override else js,
            is_current_media=(mid == current_media_id),
            stale=mid in stale_set,
            path_exists=pe,
            exists_fn=exists_fn,
        )
        if analysis_override is not None:
            triple = build_triple(
                ingest=triple.ingest,
                analysis=analysis_override,
                identity=triple.identity,
            )
        out[mid] = triple
    return out
