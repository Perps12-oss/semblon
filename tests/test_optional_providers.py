"""Optional object and VLM providers stay bring-your-own and off the identity path."""

from __future__ import annotations

from semblon.optional_providers import optional_model_providers


def test_optional_models_are_byo_and_not_identity(monkeypatch):
    monkeypatch.delenv("SEMBLON_VLM_MODEL", raising=False)
    monkeypatch.delenv("SEMBLON_VLM", raising=False)
    monkeypatch.delenv("SEMBLON_OBJECT_PACK", raising=False)
    rows = {row["id"]: row for row in optional_model_providers()}
    assert set(rows) == {"object", "vlm"}
    for row in rows.values():
        assert row["identity"] is False
        assert row["byo"] is True
        assert row["ready"] is False
        assert row["state"] != "AVAILABLE"
