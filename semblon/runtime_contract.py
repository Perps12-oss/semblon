"""Runtime failure contract. Optional capabilities stay tracked and invocable.

A provider that did not run must never look like a successful empty match.
Does not load models, touch the store, or decide identity.
FaceKit remains the only identity provider; this module does not call it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

ModelState = Literal[
    "AVAILABLE",
    "MISSING",
    "CORRUPT",
    "INCOMPATIBLE",
    "UNSUPPORTED_RUNTIME",
    "DISABLED",
]
ProviderState = Literal["READY", "DEGRADED", "FAILED"]
ResultStatus = Literal[
    "SUCCESS",
    "NO_RESULT",
    "UNAVAILABLE",
    "TIMEOUT",
    "CANCELLED",
    "ERROR",
]
Slice = Literal["shipping", "deferred"]

MODEL_STATES = (
    "AVAILABLE",
    "MISSING",
    "CORRUPT",
    "INCOMPATIBLE",
    "UNSUPPORTED_RUNTIME",
    "DISABLED",
)
FAILURE_STATUSES = frozenset({"UNAVAILABLE", "TIMEOUT", "CANCELLED", "ERROR"})


class ContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResultItem:
    id: str
    kind: str
    label: str
    detail: str = ""
    method: str | None = None
    mask: str | None = None


@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    provider_id: str
    label: str
    plain: str
    slice: Slice
    default_model: ModelState
    fallback_method: str | None = None
    fallback_on: tuple[ModelState, ...] = ()


@dataclass(frozen=True)
class StructuredResult:
    status: ResultStatus
    capability_id: str
    provider_id: str
    model_state: ModelState
    provider_state: ProviderState
    reason: str
    items: tuple[ResultItem, ...] = ()
    fallback: str | None = None
    error_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "capability_id": self.capability_id,
            "provider_id": self.provider_id,
            "model_state": self.model_state,
            "provider_state": self.provider_state,
            "reason": self.reason,
            "items": [item.__dict__ for item in self.items],
            "fallback": self.fallback,
            "error_id": self.error_id,
        }


@dataclass
class Circuit:
    state: Literal["CLOSED", "OPEN", "HALF_OPEN"] = "CLOSED"
    failures: int = 0
    threshold: int = 3


@dataclass(frozen=True)
class Catalog:
    specs: tuple[CapabilitySpec, ...] = field(default_factory=tuple)

    def get(self, capability_id: str) -> CapabilitySpec:
        for spec in self.specs:
            if spec.id == capability_id:
                return spec
        raise ContractError(f"untracked capability: {capability_id}")

    def ids(self) -> tuple[str, ...]:
        return tuple(spec.id for spec in self.specs)


Run = Callable[[], list[ResultItem] | dict]


def default_catalog() -> Catalog:
    """Every planned capability. Deferred rows are not omitted from this slice."""
    return Catalog(
        specs=(
            CapabilitySpec(
                "library_query",
                "library",
                "Library search",
                "Search what is already saved.",
                "shipping",
                "AVAILABLE",
            ),
            CapabilitySpec(
                "face",
                "facekit",
                "Face provider",
                "Detect and compare faces. A group is not a person until named.",
                "shipping",
                "MISSING",
            ),
            CapabilitySpec(
                "visual_embedding",
                "siglip",
                "Visual embedding",
                "Similar pictures. Not identity.",
                "deferred",
                "MISSING",
            ),
            CapabilitySpec(
                "ocr",
                "ocr",
                "Read text",
                "Read text. Stored text remains if a new read cannot run.",
                "deferred",
                "MISSING",
            ),
            CapabilitySpec(
                "translation",
                "translation",
                "Translation",
                "Does not replace the original text.",
                "deferred",
                "MISSING",
            ),
            CapabilitySpec(
                "grounding",
                "sam2",
                "Grounding",
                "Outline a selection. A missing model keeps the rectangle.",
                "deferred",
                "MISSING",
                "RECTANGULAR_CROP",
                ("MISSING", "UNSUPPORTED_RUNTIME", "INCOMPATIBLE"),
            ),
            CapabilitySpec(
                "barcode",
                "symbology",
                "Barcode",
                "Barcode evidence. OCR must not stand in for it.",
                "deferred",
                "MISSING",
            ),
            CapabilitySpec(
                "vlm",
                "vlm",
                "Describe",
                "A description cannot rename a person.",
                "deferred",
                "DISABLED",
            ),
            CapabilitySpec(
                "lkg",
                "lkg",
                "Knowledge",
                "A missing pack does not empty the library.",
                "deferred",
                "MISSING",
            ),
            CapabilitySpec(
                "screen_capture",
                "wgc",
                "Screen capture",
                "Windows capture. Import remains a separate path.",
                "deferred",
                "UNSUPPORTED_RUNTIME",
            ),
            CapabilitySpec(
                "ann_index",
                "vector-index",
                "Fast visual index",
                "Disposable. The library stays authoritative.",
                "deferred",
                "MISSING",
                "LIBRARY_SCAN",
                ("MISSING",),
            ),
        )
    )


REQUIRED_IDS = (
    "library_query",
    "face",
    "visual_embedding",
    "ocr",
    "translation",
    "grounding",
    "barcode",
    "vlm",
    "lkg",
    "screen_capture",
    "ann_index",
)


def provider_state_for(model: ModelState, spec: CapabilitySpec, circuit_open: bool) -> ProviderState:
    if circuit_open:
        return "FAILED"
    if model == "AVAILABLE":
        return "READY"
    if spec.fallback_method and model in spec.fallback_on:
        return "DEGRADED"
    return "FAILED"


def note_failure(circuit: Circuit) -> Circuit:
    failures = circuit.failures + 1
    state: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    if failures >= circuit.threshold or circuit.state == "HALF_OPEN":
        state = "OPEN"
    else:
        state = "CLOSED"
    return Circuit(state=state, failures=failures, threshold=circuit.threshold)


def note_success(circuit: Circuit) -> Circuit:
    if circuit.state == "HALF_OPEN":
        return Circuit(threshold=circuit.threshold)
    return Circuit(state=circuit.state, failures=0, threshold=circuit.threshold)


def assert_honest(result: StructuredResult) -> StructuredResult:
    if result.status == "SUCCESS" and not result.items:
        raise ContractError(
            f"{result.capability_id}: SUCCESS with no items is forbidden"
        )
    if result.provider_state == "FAILED" and result.status in {"SUCCESS", "NO_RESULT"}:
        raise ContractError(
            f"{result.capability_id}: FAILED provider cannot return {result.status}"
        )
    if result.status in FAILURE_STATUSES and not result.error_id:
        raise ContractError(f"{result.capability_id}: {result.status} needs an error id")
    for item in result.items:
        if item.method == "RECTANGULAR_CROP" and item.mask:
            raise ContractError("a rectangle must not be recorded as a mask")
    return result


def failure_disguised_as_empty(result: StructuredResult) -> bool:
    if result.provider_state != "FAILED":
        return False
    return result.status in {"SUCCESS", "NO_RESULT"}


def _result(
    spec: CapabilitySpec,
    model: ModelState,
    provider: ProviderState,
    status: ResultStatus,
    reason: str,
    *,
    items: tuple[ResultItem, ...] = (),
    fallback: str | None = None,
    error_id: str | None = None,
) -> StructuredResult:
    if status not in {"SUCCESS", "NO_RESULT"} and error_id is None:
        error_id = f"{spec.id}.{status}"
    return StructuredResult(
        status=status,
        capability_id=spec.id,
        provider_id=spec.provider_id,
        model_state=model,
        provider_state=provider,
        reason=reason,
        items=items,
        fallback=fallback,
        error_id=error_id,
    )


def invoke(
    capability_id: str,
    *,
    catalog: Catalog | None = None,
    model_state: ModelState | None = None,
    circuit: Circuit | None = None,
    run: Run | None = None,
    region_label: str | None = None,
    require_index: bool = False,
) -> tuple[StructuredResult, Circuit]:
    cat = catalog or default_catalog()
    spec = cat.get(capability_id)
    model: ModelState = model_state or spec.default_model
    circuit = circuit or Circuit()
    if circuit.state == "OPEN":
        result = assert_honest(
            _result(
                spec,
                model,
                "FAILED",
                "UNAVAILABLE",
                "This capability is paused after repeated failures.",
                error_id=f"{spec.id}.CIRCUIT_OPEN",
            )
        )
        return result, circuit

    provider = provider_state_for(model, spec, False)
    if provider == "FAILED":
        status: ResultStatus = "ERROR" if model == "CORRUPT" else "UNAVAILABLE"
        if model == "DISABLED":
            reason = f"{spec.label} is turned off."
        elif model == "CORRUPT":
            reason = f"{spec.label} failed its integrity check and did not run."
        elif model == "UNSUPPORTED_RUNTIME":
            reason = f"{spec.label} is not available in this session."
        elif model == "INCOMPATIBLE":
            reason = f"{spec.label} cannot run with this runtime."
        else:
            reason = f"{spec.label} is not installed. Nothing was searched."
        result = assert_honest(
            _result(spec, model, "FAILED", status, reason, error_id=f"{spec.id}.{model}")
        )
        return result, note_failure(circuit)

    if provider == "DEGRADED" and spec.fallback_method == "RECTANGULAR_CROP":
        if not region_label:
            result = assert_honest(
                _result(
                    spec,
                    model,
                    "FAILED",
                    "UNAVAILABLE",
                    "Draw a region first. Outlining did not run.",
                    error_id=f"{spec.id}.NO_REGION",
                )
            )
            return result, circuit
        item = ResultItem(
            id=f"crop-{spec.id}",
            kind="grounding",
            label=region_label,
            detail="Rectangle only",
            method="RECTANGULAR_CROP",
            mask=None,
        )
        result = assert_honest(
            _result(
                spec,
                model,
                "DEGRADED",
                "SUCCESS",
                "Outlined with the rectangle you drew. This is not a segmentation mask.",
                items=(item,),
                fallback="RECTANGULAR_CROP",
            )
        )
        return result, note_success(circuit)

    if provider == "DEGRADED" and spec.fallback_method == "LIBRARY_SCAN":
        if require_index:
            result = assert_honest(
                _result(
                    spec,
                    model,
                    "FAILED",
                    "UNAVAILABLE",
                    "The fast visual index is not built. A library scan was not used because this request demanded the index.",
                    error_id=f"{spec.id}.INDEX_REQUIRED",
                )
            )
            return result, circuit
        produced = run() if run else []
        return _finish(spec, model, "DEGRADED", "LIBRARY_SCAN", produced, circuit, empty_reason=(
            "The fast index is absent. The library was scanned and nothing matched."
        ), hit_reason="The fast index is absent. These matches came from the library.")

    produced = run() if run else []
    return _finish(spec, model, "READY", None, produced, circuit)


def _finish(
    spec: CapabilitySpec,
    model: ModelState,
    provider: ProviderState,
    fallback: str | None,
    produced: list[ResultItem] | dict,
    circuit: Circuit,
    *,
    empty_reason: str | None = None,
    hit_reason: str | None = None,
) -> tuple[StructuredResult, Circuit]:
    if isinstance(produced, dict):
        if produced.get("timeout"):
            result = assert_honest(
                _result(
                    spec,
                    model,
                    "FAILED",
                    "TIMEOUT",
                    f"{spec.label} did not finish in time.",
                    fallback=fallback,
                    error_id=f"{spec.id}.TIMEOUT",
                )
            )
            return result, note_failure(circuit)
        if produced.get("cancelled"):
            result = assert_honest(
                _result(
                    spec,
                    model,
                    provider,
                    "CANCELLED",
                    f"{spec.label} was cancelled.",
                    fallback=fallback,
                    error_id=f"{spec.id}.CANCELLED",
                )
            )
            return result, circuit
        result = assert_honest(
            _result(
                spec,
                model,
                "FAILED",
                "ERROR",
                f"{spec.label} failed: {produced.get('crash', 'provider error')}",
                fallback=fallback,
                error_id=f"{spec.id}.PROVIDER_CRASH",
            )
        )
        return result, note_failure(circuit)
    if not produced:
        result = assert_honest(
            _result(
                spec,
                model,
                provider,
                "NO_RESULT",
                empty_reason or f"{spec.label} ran and found nothing.",
                fallback=fallback,
            )
        )
        return result, note_success(circuit)
    result = assert_honest(
        _result(
            spec,
            model,
            provider,
            "SUCCESS",
            hit_reason or f"{spec.label} ran.",
            items=tuple(produced),
            fallback=fallback,
        )
    )
    return result, note_success(circuit)


def contract_checks(catalog: Catalog | None = None) -> list[tuple[str, bool, str]]:
    cat = catalog or default_catalog()
    checks: list[tuple[str, bool, str]] = []
    ids = set(cat.ids())
    checks.append(
        (
            "catalog-complete",
            all(item in ids for item in REQUIRED_IDS),
            "Deferred capabilities remain listed.",
        )
    )
    for capability_id in REQUIRED_IDS:
        if capability_id in {"library_query", "grounding", "ann_index"}:
            continue
        result, _ = invoke(capability_id, catalog=cat)
        ok = (
            result.status not in {"SUCCESS", "NO_RESULT"}
            and not result.items
            and not failure_disguised_as_empty(result)
        )
        checks.append((f"default-{capability_id}", ok, f"{capability_id} → {result.status}"))
    empty, _ = invoke("library_query", catalog=cat, model_state="AVAILABLE", run=lambda: [])
    checks.append(
        (
            "honest-empty",
            empty.status == "NO_RESULT" and empty.provider_state == "READY",
            "A real run with no hits is NO_RESULT.",
        )
    )
    hit, _ = invoke(
        "library_query",
        catalog=cat,
        model_state="AVAILABLE",
        run=lambda: [ResultItem("1", "person", "Mara")],
    )
    checks.append(("honest-hit", hit.status == "SUCCESS" and len(hit.items) == 1, "A real hit is SUCCESS."))
    corrupt, _ = invoke("face", catalog=cat, model_state="CORRUPT")
    checks.append(
        (
            "corrupt",
            corrupt.status == "ERROR" and corrupt.provider_state == "FAILED",
            "Corrupt is ERROR.",
        )
    )
    timed, _ = invoke("ocr", catalog=cat, model_state="AVAILABLE", run=lambda: {"timeout": True})
    checks.append(("timeout", timed.status == "TIMEOUT", "Timeout is not NO_RESULT."))
    crop, _ = invoke("grounding", catalog=cat, region_label="selection")
    checks.append(
        (
            "rect-fallback",
            crop.status == "SUCCESS"
            and crop.provider_state == "DEGRADED"
            and crop.fallback == "RECTANGULAR_CROP"
            and crop.items
            and crop.items[0].mask is None,
            "Rectangle is not a mask.",
        )
    )
    bare, _ = invoke("grounding", catalog=cat)
    checks.append(("grounding-without-region", bare.status == "UNAVAILABLE", "No region, no fake search."))
    circuit = Circuit(threshold=3)
    for _ in range(3):
        _, circuit = invoke("barcode", catalog=cat, model_state="CORRUPT", circuit=circuit)
    paused, _ = invoke("barcode", catalog=cat, model_state="AVAILABLE", circuit=circuit)
    checks.append(
        (
            "circuit",
            circuit.state == "OPEN" and paused.error_id == "barcode.CIRCUIT_OPEN",
            "Repeated failures pause the provider.",
        )
    )
    index_only, _ = invoke("ann_index", catalog=cat, require_index=True)
    checks.append(
        ("index-required", index_only.status == "UNAVAILABLE", "Missing index is not an empty match.")
    )
    sealed = False
    try:
        assert_honest(
            StructuredResult(
                status="SUCCESS",
                capability_id="face",
                provider_id="facekit",
                model_state="MISSING",
                provider_state="FAILED",
                reason="no",
                items=(),
            )
        )
    except ContractError:
        sealed = True
    checks.append(("seal", sealed, "SUCCESS on a failed provider is rejected."))
    return checks
