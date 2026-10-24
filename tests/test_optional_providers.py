"""Optional object and VLM providers stay bring-your-own and off the identity path."""

from __future__ import annotations

import pytest

from semblon.optional_providers import install_choice, optional_model_providers


def test_optional_models_are_byo_and_not_identity(monkeypatch):
    monkeypatch.delenv("SEMBLON_VLM_MODEL", raising=False)
    monkeypatch.delenv("SEMBLON_VLM", raising=False)
    monkeypatch.delenv("SEMBLON_OBJECT_PACK", raising=False)
    rows = {row["id"]: row for row in optional_model_providers()}
    if any(row.get("ready") or row.get("state") == "AVAILABLE" for row in rows.values()):
        pytest.skip(
            "Optional extras are installed on this machine; this test asserts the clean-install state."
        )
    assert set(rows) == {"object", "vlm"}
    for row in rows.values():
        assert row["identity"] is False
        assert row["byo"] is True
        assert row["ready"] is False
        assert row["state"] != "AVAILABLE"


def test_install_choice_offers_one_model_for_the_current_search():
    assert install_choice(
        "unavailable",
        "region.NO_PACK",
        {"optional_providers": [{"id": "object", "ready": False, "state": "MISSING"}]},
    ) == ("region_pack", "Get finding-by-look ready")
    assert install_choice(
        "ready",
        "",
        {
            "optional_providers": [
                {"id": "object", "ready": False, "state": "MISSING"},
                {"id": "vlm", "ready": False, "state": "MISSING"},
            ]
        },
    ) == ("object_pack", "Get finding-by-object ready")
    assert install_choice(
        "ready",
        "",
        {"channels": [{"door": "object", "status": "UNAVAILABLE", "error_id": "object.PACK_MISSING"}]},
    ) == ("object_pack", "Get finding-by-object ready")
    assert install_choice(
        "ready",
        "",
        {
            "optional_providers": [
                {"id": "object", "ready": True, "state": "AVAILABLE"},
                {"id": "vlm", "ready": False, "state": "MISSING"},
            ]
        },
    ) == ("vlm_local", "Get photo descriptions ready")
    assert install_choice(
        "ready",
        "",
        {
            "optional_providers": [
                {"id": "object", "ready": True, "state": "AVAILABLE"},
                {"id": "vlm", "ready": False, "state": "DISABLED"},
            ]
        },
    ) == ("", "")
    assert install_choice("unavailable", "screen.NO_CAPTURE", {}) == ("", "")
