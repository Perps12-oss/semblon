"""P4 — available / unavailable / incompatible capability handshake."""

from __future__ import annotations

import pytest


def test_classify_readiness_three_states_only():
    from semblon.capability_manifest import (
        AVAILABLE,
        INCOMPATIBLE,
        UNAVAILABLE,
        classify_readiness,
    )

    assert classify_readiness(True, None) == AVAILABLE
    assert classify_readiness(False, "Face weights are missing.") == UNAVAILABLE
    assert classify_readiness(False, "Face pack hash does not match pin.") == INCOMPATIBLE
    assert classify_readiness(False, "unexpected LFS pointer") == INCOMPATIBLE
    assert classify_readiness(False, "weights did not load") == INCOMPATIBLE


def test_capability_status_rejects_unknown_state():
    from semblon.capability_manifest import CapabilityStatus

    with pytest.raises(ValueError, match="unsupported capability state"):
        CapabilityStatus(
            capability_id="identity",
            state="degraded",
            provider_id="x",
            contract="",
            message="",
        )


def test_identity_unavailable_when_weights_absent(monkeypatch):
    from semblon.capability_manifest import UNAVAILABLE, identity_capability

    monkeypatch.setattr(
        "semblon.engine.discover_weight_hashes", lambda: {}
    )
    status = identity_capability()
    assert status.state == UNAVAILABLE
    assert status.blocks_identity is True
    assert "Nothing was downloaded" in status.message


def test_identity_incompatible_when_pack_contract_fails(monkeypatch):
    from semblon.capability_manifest import (
        FACE_INCOMPATIBLE_MESSAGE,
        INCOMPATIBLE,
        identity_capability,
    )
    from semblon.engine import ModelPackError

    monkeypatch.setattr(
        "semblon.engine.discover_weight_hashes",
        lambda: {"yunet": "abc", "sface": "def"},
    )

    def boom():
        raise ModelPackError("Face pack hash does not match pin.")

    monkeypatch.setattr("semblon.engine.assert_face_pack_ready", boom)
    status = identity_capability()
    assert status.state == INCOMPATIBLE
    assert status.message == FACE_INCOMPATIBLE_MESSAGE
    assert status.blocks_identity is True


def test_identify_face_refuses_when_identity_not_available(tmp_path, monkeypatch):
    from semblon.capability_manifest import (
        FACE_INCOMPATIBLE_MESSAGE,
        CapabilityStatus,
        INCOMPATIBLE,
    )
    from semblon.identify import IdentifyError, identify_face

    blocked = CapabilityStatus(
        capability_id="identity",
        state=INCOMPATIBLE,
        provider_id="yunet_sface",
        contract="",
        message=FACE_INCOMPATIBLE_MESSAGE,
        blocks_identity=True,
    )
    monkeypatch.setattr(
        "semblon.capability_manifest.identity_work_allowed",
        lambda: (False, blocked),
    )
    with pytest.raises(IdentifyError, match="paused until update"):
        identify_face(tmp_path / "library.db", "r1", "f1")


def test_people_backfill_reports_incompatible_not_unavailable(tmp_path, monkeypatch):
    from semblon.capability_manifest import (
        FACE_INCOMPATIBLE_MESSAGE,
        CapabilityStatus,
        INCOMPATIBLE,
    )
    from semblon.category_backfill import ProviderProbe, run_category_backfill
    from semblon.store import connect, init_db

    store = tmp_path / "library.db"
    conn = connect(store)
    init_db(conn)
    conn.commit()
    conn.close()

    blocked = CapabilityStatus(
        capability_id="people",
        state=INCOMPATIBLE,
        provider_id="yunet_sface",
        contract="",
        message=FACE_INCOMPATIBLE_MESSAGE,
        blocks_identity=True,
    )
    monkeypatch.setattr(
        "semblon.capability_manifest.category_capability",
        lambda _category: blocked,
    )
    monkeypatch.setattr(
        "semblon.category_backfill.probe_category",
        lambda _category: ProviderProbe(
            False,
            "yunet_sface",
            "",
            "Face pack hash does not match pin.",
            state=INCOMPATIBLE,
        ),
    )
    rec = run_category_backfill(store, "people")
    assert rec["status"] == "incompatible"
    assert "paused until update" in rec["user_message"].lower()
    assert "not available" not in rec["user_message"].lower()


def test_objects_unavailable_stays_unavailable(tmp_path, monkeypatch):
    from semblon.capability_manifest import (
        UNAVAILABLE,
        CapabilityStatus,
    )
    from semblon.category_backfill import ProviderProbe, run_category_backfill
    from semblon.store import connect, init_db

    store = tmp_path / "library.db"
    conn = connect(store)
    init_db(conn)
    conn.commit()
    conn.close()

    cap = CapabilityStatus(
        capability_id="objects",
        state=UNAVAILABLE,
        provider_id="nanodet",
        contract="",
        message="Object model is missing.",
    )
    monkeypatch.setattr(
        "semblon.capability_manifest.category_capability",
        lambda _category: cap,
    )
    monkeypatch.setattr(
        "semblon.category_backfill.probe_category",
        lambda _category: ProviderProbe(
            False, "nanodet", "", "Object model is missing.", state=UNAVAILABLE
        ),
    )
    rec = run_category_backfill(store, "objects")
    assert rec["status"] == "unavailable"
    assert "not available" in rec["user_message"].lower() or "missing" in rec["reason"].lower()


def test_preflight_maps_face_hash_mismatch_to_incompatible():
    from semblon.preflight import collect_rows

    rows = {
        row["id"]: row
        for row in collect_rows(
            runtime_text="#\npillow==13.0.0\n",
            dev_text="#\npytest==9.1.1\n",
            python_version=(3, 12),
            installed={"pillow": "13.0.0", "pytest": "9.1.1"},
            venv=True,
            probes={
                "region": lambda: (False, "region model missing"),
                "object": lambda: (False, "object model missing"),
                "vlm": lambda: "MISSING",
                "ocr": lambda: (False, "tesseract missing"),
                "clip": lambda: (False, "clip weights missing"),
                "face": lambda: (False, "Face pack hash does not match pin."),
                "opencv_load": lambda: (True, "5.0.0.93", None),
                "arch": lambda: ("native", "x64"),
            },
        )
    }
    assert rows["face_pack"]["status"] == "incompatible"
    assert rows["face_pack"]["installable"] is False
    assert rows["region_pack"]["status"] == "missing"
    assert rows["region_pack"]["installable"] is True


def test_preflight_keeps_missing_face_as_missing():
    from semblon.preflight import collect_rows

    rows = {
        row["id"]: row
        for row in collect_rows(
            runtime_text="#\npillow==13.0.0\n",
            dev_text="#\npytest==9.1.1\n",
            python_version=(3, 12),
            installed={"pillow": "13.0.0", "pytest": "9.1.1"},
            venv=True,
            probes={
                "region": lambda: (False, "region model missing"),
                "object": lambda: (False, "object model missing"),
                "vlm": lambda: "MISSING",
                "ocr": lambda: (False, "tesseract missing"),
                "clip": lambda: (False, "clip weights missing"),
                "face": lambda: (False, "face weights missing"),
                "opencv_load": lambda: (True, "5.0.0.93", None),
                "arch": lambda: ("native", "x64"),
            },
        )
    }
    assert rows["face_pack"]["status"] == "missing"


def test_incompatible_notice_is_identity_specific():
    from semblon.capability_manifest import (
        FACE_INCOMPATIBLE_MESSAGE,
        AVAILABLE,
        INCOMPATIBLE,
        CapabilityStatus,
        incompatible_notice,
    )

    notice = incompatible_notice(
        [
            CapabilityStatus(
                capability_id="objects",
                state=AVAILABLE,
                provider_id="nanodet",
                contract="x",
                message="",
            ),
            CapabilityStatus(
                capability_id="identity",
                state=INCOMPATIBLE,
                provider_id="yunet_sface",
                contract="",
                message=FACE_INCOMPATIBLE_MESSAGE,
                blocks_identity=True,
            ),
        ]
    )
    assert notice == FACE_INCOMPATIBLE_MESSAGE
    assert "paused until update" in notice.lower()


def test_identity_pause_does_not_block_object_capability(monkeypatch):
    from semblon import capability_manifest as caps
    from semblon.capability_manifest import (
        AVAILABLE,
        INCOMPATIBLE,
        CapabilityStatus,
        category_capability,
    )
    from semblon.category_backfill import ProviderProbe

    monkeypatch.setattr(
        caps,
        "identity_capability",
        lambda: CapabilityStatus(
            capability_id="identity",
            state=INCOMPATIBLE,
            provider_id="yunet_sface",
            contract="",
            message="paused",
            blocks_identity=True,
        ),
    )
    monkeypatch.setattr(
        "semblon.category_backfill.probe_category",
        lambda category: ProviderProbe(
            True, "nanodet", "abc", "", state=AVAILABLE
        )
        if category == "objects"
        else ProviderProbe(False, "yunet_sface", "", "paused", state=INCOMPATIBLE),
    )
    people = category_capability("people")
    objects = category_capability("objects")
    assert people.state == INCOMPATIBLE
    assert people.blocks_identity is True
    assert objects.state == AVAILABLE
    assert objects.blocks_identity is False
