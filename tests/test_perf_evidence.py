from semblon import perf_evidence


def test_records_timings_but_never_names_or_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("SEMBLON_PERF", raising=False)
    store = tmp_path / "s.sqlite"
    assert perf_evidence.record(store, "search", latency_ms=12.3456, path="C:/me/x.jpg", query="beach")
    row = perf_evidence.read(store, "search")[0]
    assert row["latency_ms"] == 12.346
    assert "path" not in row and "query" not in row
    assert row["machine"]


def test_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_PERF", "0")
    store = tmp_path / "s.sqlite"
    assert perf_evidence.record(store, "search", latency_ms=1) is False
    assert perf_evidence.read(store) == []


def test_report_summarises_searches(tmp_path, monkeypatch):
    monkeypatch.delenv("SEMBLON_PERF", raising=False)
    store = tmp_path / "s.sqlite"
    for ms in (10, 20, 30):
        perf_evidence.record(store, "search", latency_ms=ms)
    summary = perf_evidence.report(store)
    assert summary["searches"] == 3
    assert summary["first_search_ms"] == 10
    assert summary["search_ms_p50"] == 20
