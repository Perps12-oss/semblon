"""Deferred capabilities stay invocable. Failures are not empty matches."""

from semblon.runtime_contract import (
    REQUIRED_IDS,
    contract_checks,
    declare,
    default_catalog,
    failure_disguised_as_empty,
    invoke,
    status_report,
)


def test_catalog_lists_every_planned_capability():
    ids = default_catalog().ids()
    assert ids == REQUIRED_IDS
    deferred = [spec.id for spec in default_catalog().specs if spec.slice == "deferred"]
    assert "visual_embedding" in deferred
    assert "screen_capture" in deferred
    assert "face" not in deferred


def test_contract_checks_hold():
    failed = [row for row in contract_checks() if not row[1]]
    assert failed == []


def test_declare_does_not_pretend_a_run():
    ready = declare("ocr", model_state="AVAILABLE")
    assert ready.status == "UNAVAILABLE"
    assert ready.provider_state == "READY"
    assert ready.error_id == "ocr.NOT_INVOKED"
    assert ready.items == ()
    missing = declare("visual_embedding")
    assert missing.status == "UNAVAILABLE"
    assert missing.provider_state == "FAILED"
    report = status_report()
    assert [row["capability_id"] for row in report] == list(REQUIRED_IDS)
    assert all(row["status"] != "SUCCESS" for row in report)
    assert all(row["status"] != "NO_RESULT" for row in report)
    result, _ = invoke("visual_embedding")
    assert result.status == "UNAVAILABLE"
    assert result.items == ()
    assert result.status != "NO_RESULT"
    assert failure_disguised_as_empty(result) is False


def test_ready_provider_with_no_hits_is_no_result():
    result, _ = invoke("ocr", model_state="AVAILABLE", run=lambda: [])
    assert result.status == "NO_RESULT"
    assert result.provider_state == "READY"


def test_rectangle_is_not_a_mask():
    result, _ = invoke("grounding", region_label="watch")
    assert result.fallback == "RECTANGULAR_CROP"
    assert result.items[0].method == "RECTANGULAR_CROP"
    assert result.items[0].mask is None
    assert "not a segmentation mask" in result.reason
