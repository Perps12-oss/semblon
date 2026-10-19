"""Optional non-identity model providers. Bring-your-own weights. No download.

Object detection and the vision-language describer stay capability probes.
A missing weight is MISSING. It is not an empty match and it does not vote
on face identity.
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
            "reason": None if vlm_ready else "VLM weights are bring-your-own. Nothing is downloaded.",
        },
    ]
