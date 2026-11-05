"""Pilot harness: small fixture, cluster flag, elapsed and RSS."""

from __future__ import annotations

import time

from semblon.brain.observation import Observation, PhotoRef
from semblon.brain.pilot import run_pilot


class _Tags:
    def observe(self, photo: PhotoRef):
        return [
            Observation(
                photo_id=photo.photo_id,
                capability_id="C1",
                provider_name="existing_nanodet_tags",
                model_pack_hash="test",
                payload={
                    "tags": [{"label": "dog", "score": 0.9}],
                    "provider": "test-nanodet",
                },
                confidence=0.9,
            )
        ]


def _corpus(tmp_path, n: int = 5):
    corpus = tmp_path / "photos"
    corpus.mkdir()
    for i in range(n):
        (corpus / f"p{i}.jpg").write_bytes(b"jpg")
    return corpus


def test_pilot_runs_on_small_fixture(tmp_path):
    corpus = _corpus(tmp_path)
    out = tmp_path / "PILOT.md"
    result = run_pilot(
        corpus=corpus,
        out=out,
        store=tmp_path / "pilot.sqlite",
        chunk=2,
        observer=_Tags(),
        no_cluster=True,
    )
    text = out.read_text(encoding="utf-8")
    assert result.code == 0
    assert result.photos == 5
    assert len(result.chunks) == 3
    assert out.is_file()
    assert "Total photos: 5" in text
    assert "| 1 | 2 |" in text
    assert "test-nanodet" in text or "Providers seen: test-nanodet" in text


def test_pilot_skips_cluster_when_no_cluster_flag(tmp_path, monkeypatch):
    calls: list[int] = []

    def _regions(_conn) -> int:
        return 3

    def _cluster(_conn):
        calls.append(1)
        time.sleep(0.01)
        return {"clusters": 0}

    monkeypatch.setattr("semblon.brain.pilot._region_embedding_count", _regions)
    corpus = _corpus(tmp_path)
    skipped = run_pilot(
        corpus=corpus,
        out=tmp_path / "skip.md",
        store=tmp_path / "skip.sqlite",
        chunk=5,
        no_cluster=True,
        observer=_Tags(),
        cluster_fn=_cluster,
    )
    assert skipped.code == 0
    assert calls == []
    assert all(chunk.cluster_s is None for chunk in skipped.chunks)

    ran = run_pilot(
        corpus=corpus,
        out=tmp_path / "run.md",
        store=tmp_path / "run.sqlite",
        chunk=5,
        no_cluster=False,
        observer=_Tags(),
        cluster_fn=_cluster,
    )
    assert ran.code == 0
    assert calls
    assert ran.chunks[0].cluster_s is not None and ran.chunks[0].cluster_s > 0


def test_pilot_records_elapsed_and_rss(tmp_path):
    corpus = _corpus(tmp_path)
    result = run_pilot(
        corpus=corpus,
        out=tmp_path / "rss.md",
        store=tmp_path / "rss.sqlite",
        chunk=5,
        no_cluster=True,
        observer=_Tags(),
    )
    assert result.chunks
    assert all(chunk.elapsed_s > 0 for chunk in result.chunks)
    assert all(chunk.rss_peak_mb > 0 for chunk in result.chunks)
    assert all(chunk.throughput_per_min > 0 for chunk in result.chunks)
