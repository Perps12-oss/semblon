"""Live provider circuits. An open circuit is UNAVAILABLE, not an empty match."""

from __future__ import annotations

from semblon.runtime_contract import Circuit, StructuredResult, failure_disguised_as_empty, note_failure, note_success

_CIRCUITS: dict[str, Circuit] = {}


def reset_circuits() -> None:
    _CIRCUITS.clear()


def circuit_for(capability_id: str) -> Circuit:
    return _CIRCUITS.get(capability_id, Circuit())


def remember(capability_id: str, circuit: Circuit) -> None:
    _CIRCUITS[capability_id] = circuit


def before_call(capability_id: str) -> StructuredResult | None:
    circuit = circuit_for(capability_id)
    if circuit.state != "OPEN":
        return None
    return StructuredResult(
        status="UNAVAILABLE",
        capability_id=capability_id,
        provider_id=capability_id,
        model_state="AVAILABLE",
        provider_state="FAILED",
        reason="This capability is paused after repeated failures.",
        items=(),
        error_id=f"{capability_id}.CIRCUIT_OPEN",
    )


def after_call(result: StructuredResult) -> StructuredResult:
    if failure_disguised_as_empty(result) or (result.status == "SUCCESS" and not result.items):
        raise RuntimeError(f"{result.capability_id} disguised a failure as an empty match")
    circuit = circuit_for(result.capability_id)
    if result.status in {"ERROR", "TIMEOUT"} or (
        result.status == "UNAVAILABLE" and result.model_state == "CORRUPT"
    ):
        remember(result.capability_id, note_failure(circuit))
    elif result.status in {"SUCCESS", "NO_RESULT"}:
        remember(result.capability_id, note_success(circuit))
    return result
