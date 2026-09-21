"""Central feature-gate registry — verified; product defaults ON.

Human VERIFY (2026-09-21) authorized wiring. Env still overrides:
``SEMBLON_GATE_<NAME>=0`` disables a surface. Defaults do **not** change
identity thresholds, pack_id, or FaceKit compare. Optional modalities never
vote on identity. No schema columns invented here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

_FALSE = frozenset({"0", "false", "no", "off"})
_TRUE = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class Gate:
    """One gated surface. Product default ON after VERIFY; env may disable."""

    key: str
    summary: str
    human_verify: str
    wire_after: str
    env_var: str
    default: bool = True

    def enabled(self) -> bool:
        raw = os.environ.get(self.env_var)
        if raw is None:
            return bool(self.default)
        token = raw.strip().lower()
        if token in _FALSE:
            return False
        if token in _TRUE:
            return True
        return bool(self.default)


# Verified 2026-09-21 — wired into product paths. Set env=0 to disable one gate.
GATES: dict[str, Gate] = {
    "r3_bakeoff": Gate(
        key="r3_bakeoff",
        summary="R3 toolkit bake-off harness (six criteria; measure, don't prefer)",
        human_verify="Run tools/r3_bakeoff on a real Windows host; confirm no criterion emits PASS without measurement",
        wire_after="Expose `semblon lab r3-bakeoff` and record results under artifacts/",
        env_var="SEMBLON_GATE_R3_BAKEOFF",
    ),
    "r3_measure": Gate(
        key="r3_measure",
        summary="R3 §6 measurement runners — refuse fake PASS",
        human_verify="Confirm each criterion returns unverified/fail when not measured; never invent PASS",
        wire_after="Hook measurement outputs into bake-off report aggregation",
        env_var="SEMBLON_GATE_R3_MEASURE",
    ),
    "ruled_out": Gate(
        key="ruled_out",
        summary="Ruled-out decision path (CONTRACTS: reject + policy action=ruled_out)",
        human_verify="Review docs/CONTRACTS.md Ruled-out slice; approve durable verb vs today's reject+ignore",
        wire_after="Wire review CLI/UI after named CONTRACTS slice lands; do not invent columns",
        env_var="SEMBLON_GATE_RULED_OUT",
    ),
    "live_overlay": Gate(
        key="live_overlay",
        summary="Live/canvas adaptive overlay (R3 three-layer)",
        human_verify="Visual check of identity notch grammar at smallest face size; no identity auto-assign",
        wire_after="Enable in canvas/live preview behind this flag only",
        env_var="SEMBLON_GATE_LIVE_OVERLAY",
    ),
    "observer_honesty": Gate(
        key="observer_honesty",
        summary="Pose/OCR/CLIP status truth probes (import ≠ capability)",
        human_verify="lab providers output matches real runnable capability on target machine",
        wire_after="Replace optional_status notes with probe results when VERIFY passes",
        env_var="SEMBLON_GATE_OBSERVER_HONESTY",
    ),
    "hierarchy_frames": Gate(
        key="hierarchy_frames",
        summary="R3 §8.6 hierarchy frames + collision ledger catalog",
        human_verify="Reviewer walks frames; hesitation on a pair = fail the rule or the render",
        wire_after="Attach frames to R3 decision packet after APP-1 C.3 + R2",
        env_var="SEMBLON_GATE_HIERARCHY_FRAMES",
    ),
    "perf_workers_measure": Gate(
        key="perf_workers_measure",
        summary="PERF workers=1/2/4 measure harness; product default stays 1",
        human_verify="Run harness on native Windows; do not change default workers from evidence alone",
        wire_after="Publish measurements to docs/PERF-WORKERS.md; keep ingest --workers default=1",
        env_var="SEMBLON_GATE_PERF_WORKERS_MEASURE",
    ),
}


def get_gate(key: str) -> Gate:
    try:
        return GATES[key]
    except KeyError as e:
        raise KeyError(f"unknown gate: {key}") from e


def is_enabled(key: str) -> bool:
    return get_gate(key).enabled()


def require_enabled(key: str) -> None:
    """Raise if a gated surface is invoked while OFF."""
    gate = get_gate(key)
    if not gate.enabled():
        raise RuntimeError(
            f"gate {gate.key!r} is OFF. "
            f"Default is ON after VERIFY; set {gate.env_var}=1 to re-enable "
            f"(or unset it). Wire: {gate.wire_after}"
        )


def status_report(keys: Iterable[str] | None = None) -> dict:
    """Read-only status for labs / playbook. Never writes the store."""
    selected = list(keys) if keys is not None else sorted(GATES)
    gates = []
    for key in selected:
        g = get_gate(key)
        gates.append(
            {
                "key": g.key,
                "enabled": g.enabled(),
                "default": g.default,
                "env_var": g.env_var,
                "summary": g.summary,
                "human_verify": g.human_verify,
                "wire_after": g.wire_after,
            }
        )
    return {
        "registry": "semblon.gates",
        "policy": "defaults ON after human VERIFY; set SEMBLON_GATE_*=0 to disable",
        "verified_wired": True,
        "gates": gates,
        "any_enabled": any(g["enabled"] for g in gates),
    }
