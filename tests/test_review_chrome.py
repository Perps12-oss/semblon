"""Cluster Review chrome — shared export + Home / review-ui document."""

from __future__ import annotations

import json
from pathlib import Path

from semblon.cluster import cluster_run
from semblon.export import EVIDENCE_SCRIPT_ID, STRONG_MIN_INTRA, export_review
from semblon.review_chrome import (
    build_chrome_board,
    render_review_document,
    render_review_document_from_store,
)
from tests.test_cluster import _seed


def _parse_evidence(html: str) -> dict:
    marker = f'id="{EVIDENCE_SCRIPT_ID}"'
    start = html.index(marker)
    open_gt = html.index(">", start) + 1
    close = html.index("</script>", open_gt)
    return json.loads(html[open_gt:close])


def test_chrome_board_binary_classification(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    board = build_chrome_board(store, "r1", mode="snapshot", include_thumbs=False)
    assert board["mode"] == "snapshot"
    assert STRONG_MIN_INTRA == 0.50
    classes = {c["classification"] for c in board["clusters"]}
    assert classes <= {"good", "review"}
    assert "check" not in classes
    for c in board["clusters"]:
        assert len(c["display_index"]) == 4
        if c["min_intra"] is not None and c["min_intra"] >= 0.50:
            assert c["classification"] == "good"
        else:
            assert c["classification"] == "review"


def test_export_html_matches_chrome_mock_markers(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    out = tmp_path / "review.html"
    export_review(store, "r1", out)
    text = out.read_text(encoding="utf-8")
    assert 'data-mode="snapshot"' in text
    assert "Cluster Review" in text
    assert "REVIEW REQUIRED (HIGHEST PRIORITY)" in text
    assert "STRONG" in text
    assert "UNASSIGNED" in text
    assert f'id="{EVIDENCE_SCRIPT_ID}"' in text
    assert 'id="review"' in text
    assert 'id="strong"' in text
    assert 'id="unassigned"' in text
    assert 'class="wordmark"' in text
    assert 'class="sidebar"' in text
    assert 'id="page-title"' in text
    assert 'class="page-head"' in text
    assert 'class="stats-toolbar"' in text
    assert 'class="topbar"' not in text
    assert "--bg-nav: #10161C" in text
    assert "--bg-app: #141A22" in text
    assert "box-shadow: -8px 0 24px" not in text
    assert 'data-op="same"' in text
    assert "disabled" in text
    assert "Open Semblon Home to decide" in text
    assert "not a person" in text
    payload = _parse_evidence(text)
    assert payload["schema_version"] == "1"
    assert payload["run_id"] == "r1"
    assert payload["strong_min_intra"] == 0.50


def test_live_document_enables_bridge_mode(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    html = render_review_document_from_store(store, "r1", mode="live", include_thumbs=False)
    assert 'data-mode="live"' in html
    assert "semblonApply" in html
    assert f'id="{EVIDENCE_SCRIPT_ID}"' not in html


def test_render_review_document_roundtrip_board(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    board = build_chrome_board(store, "r1", mode="snapshot", include_thumbs=False)
    html = render_review_document(board, mode="snapshot")
    marker = 'id="semblon-board"'
    start = html.index(marker)
    open_gt = html.index(">", start) + 1
    close = html.index("</script>", open_gt)
    parsed = json.loads(html[open_gt:close])
    assert parsed["run_id"] == "r1"
    assert parsed["stats"]["clusters"] == board["stats"]["clusters"]


def test_classic_export_flag(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    out = tmp_path / "classic.html"
    export_review(store, "r1", out, classic=True)
    text = out.read_text(encoding="utf-8")
    assert "background: #111" in text
    assert "Cluster Review" not in text
    assert f'id="{EVIDENCE_SCRIPT_ID}"' in text
