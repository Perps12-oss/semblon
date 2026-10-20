"""Optional non-identity model providers.

Object detection and the local describer stay capability probes. A missing
weight is MISSING. It is not an empty match and it does not vote on face
identity. Probes do not download. A confirmed shell install is a separate step.
"""

from __future__ import annotations


def optional_model_providers() -> list[dict]:
    """Status rows for optional upgrades. Does not load weights or open the network."""
    from semblon.lens import probe_vlm
    from semblon.object_pack import probe_nanodet_status

    object_ready, object_note = probe_nanodet_status()
    vlm_state = probe_vlm()
    vlm_ready = vlm_state == "AVAILABLE"
    return [
        {
            "id": "object",
            "capability": "object",
            "modality": "object",
            "identity": False,
            "byo": True,
            "ready": bool(object_ready),
            "state": "AVAILABLE" if object_ready else "MISSING",
            "reason": None if object_ready else (object_note or "NanoDet weights are bring-your-own."),
        },
        {
            "id": "vlm",
            "capability": "vlm",
            "modality": "text",
            "identity": False,
            "byo": True,
            "ready": vlm_ready,
            "state": vlm_state if vlm_state else "MISSING",
            "reason": None
            if vlm_ready
            else (
                "Description is turned off."
                if vlm_state == "DISABLED"
                else "Description model is not installed."
            ),
        },
    ]


def install_choice(state: str, error_id: str, data: dict | None) -> tuple[str, str]:
    """One in-place install offer for the search that just ran.

    Region model first when that gap blocks the result. Otherwise the object
    model when that door or provider is missing. Otherwise the local description
    when that provider was reported missing. A result with no provider status
    does not invent an offer.
    """
    payload = data if isinstance(data, dict) else {}
    if state == "unavailable" and error_id == "region.NO_PACK":
        return "region_pack", "Install region model"
    channels = payload.get("channels") if isinstance(payload.get("channels"), list) else []
    object_blocked = any(
        isinstance(row, dict)
        and str(row.get("door") or "") == "object"
        and str(row.get("error_id") or "") == "object.PACK_MISSING"
        for row in channels
    )
    providers = payload.get("optional_providers")
    rows = providers if isinstance(providers, list) else None
    if object_blocked or _provider_missing(_provider_row(rows, "object")):
        return "object_pack", "Install object model"
    if _provider_missing(_provider_row(rows, "vlm")):
        return "vlm_local", "Install description model"
    return "", ""


def _provider_row(rows: list | None, provider_id: str) -> dict | None:
    if rows is None:
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("id") == provider_id:
            return row
    return None


def _provider_missing(row: dict | None) -> bool:
    if not isinstance(row, dict) or row.get("ready") is True:
        return False
    state = str(row.get("state") or "")
    return state not in {"DISABLED", "AVAILABLE"}
