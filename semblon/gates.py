"""Central feature-gate registry — code-ahead scaffolds, all defaults OFF.

Human verification authorizes wiring. Enabling a flag without the matching
VERIFY entry in ``docs/GATES-WIRE-PLAYBOOK.md`` is forbidden.

These flags do **not** change identity thresholds, pack_id, or FaceKit
compare. Optional modalities never vote on identity. No schema columns are
invented here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Gate:
    """One code-ahead surface. Default is always OFF."""

    key: str
    summary: str
    human_verify: str
    wire_after: str
    env_var: str
    default: bool = False

    def enabled(self) -> bool:
        raw = os.environ.get(self.env_var)
        if raw is None:
            return bool(self.default)
        return raw.strip().lower() in {"1", "true", "yes", "on"}


# All gates default OFF. Product behavior must not change until human VERIFY.
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
        summary="Ruled-out decision path scaffold (CONTRACTS gap; no new columns)",
        human_verify="Review docs/CONTRACTS.md Ruled-out slice; approve durable verb vs today's reject+ignore",
        wire_after="Wire review CLI/UI after named CONTRACTS slice lands; do not invent columns",
        env_var="SEMBLON_GATE_RULED_OUT",
    ),
    "live_overlay": Gate(
        key="live_overlay",
        summary="Live/canvas adaptive overlay scaffold (R3 three-layer; off by default)",
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
        summary="R3 §8.6 clickable hierarchy frames + collision ledger assets",
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
            f"gate {gate.key!r} is OFF (default). "
            f"Human VERIFY first: {gate.human_verify}. "
            f"Then set {gate.env_var}=1 to enable. "
            f"Wire step: {gate.wire_after}"
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
        "policy": "all defaults OFF; human verification authorizes wiring",
        "gates": gates,
        "any_enabled": any(g["enabled"] for g in gates),
    }
