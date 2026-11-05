"""Inc 5: EP probe, governor, priority, checkpoint, status, throughput."""

from __future__ import annotations

from pathlib import Path

from semblon.brain.pilot import checkpoint_path, run_pilot, select_paths
from semblon.brain.resources import (
    AZURE_EP,
    CPU_EP,
    InputPriority,
    ThroughputMeter,
    admission,
    choose_execution_provider,
    classify_pressure,
    read_checkpoint,
    status_line,
    worker_cap,
    write_checkpoint,
)
from semblon.brain.observation import Observation, PhotoRef


class _Tags:
    def observe(self, photo: PhotoRef):
        return [
            Observation(
                photo_id=photo.photo_id,
                capability_id="C1",
                provider_name="existing_nanodet_tags",
                model_pack_hash="test",
                payload={"tags": [{"label": "dog", "score": 0.9}], "provider": "test-nanodet"},
                confidence=0.9,
            )
        ]


def _corpus(tmp_path, n: int = 4):
    corpus = tmp_path / "photos"
    corpus.mkdir()
    for i in range(n):
        (corpus / f"p{i}.jpg").write_bytes(b"jpg")
    return corpus


def test_ep_probe_isolates_failures_and_refuses_azure():
    def probe(name: str) -> bool:
        if name == "CUDAExecutionProvider":
            raise RuntimeError("cuda down")
        return name in {"DmlExecutionProvider", AZURE_EP, CPU_EP}

    choice = choose_execution_provider(probe)
    assert choice.chosen == "DmlExecutionProvider"
    assert choice.gpu is True
    assert choice.results["CUDAExecutionProvider"] is False
    assert choice.results[AZURE_EP] is True
    assert choice.identity_path == "opencv_dnn_cpu"

    azure_only = choose_execution_provider(lambda name: name == AZURE_EP)
    assert azure_only.chosen == CPU_EP
    assert azure_only.gpu is False


def test_governor_pause_wins_and_throttle_caps_workers():
    assert classify_pressure(100, 10) == "pause"
    assert classify_pressure(13_000, 8_000) == "throttle"
    assert classify_pressure(13_000, 10) == "pause"
    assert classify_pressure(100, 8_000) == "ok"
    assert worker_cap(4, "pause") == 0
    assert worker_cap(4, "throttle") == 1
    assert worker_cap(4, "ok") == 4


def test_priority_yields_until_hold_expires():
    priority = InputPriority()
    priority.note_input(now=10.0)
    assert priority.should_yield(now=11.0, hold_s=2.0) is True
    assert priority.should_yield(now=13.0, hold_s=2.0) is False
    assert admission("pause", True) == "pause"
    assert admission("ok", True) == "yield"
    assert admission("throttle", False) == "throttle"
    assert admission("ok", False) == "run"


def test_checkpoint_round_trip_and_corrupt_file(tmp_path):
    path = tmp_path / "pilot.sqlite.checkpoint.json"
    write_checkpoint(path, {"chunk_index": 2, "photos_done": 20, "corpus": "K", "limit": None})
    loaded = read_checkpoint(path)
    assert loaded is not None
    assert loaded["photos_done"] == 20
    assert loaded["version"] == 1
    path.write_text("{", encoding="utf-8")
    assert read_checkpoint(path) is None


def test_throughput_meter_uses_samples_only():
    meter = ThroughputMeter()
    assert meter.per_minute("c1") is None
    meter.add("c1", 10, 30)
    assert meter.per_minute("c1") == 20
    text = Path("semblon/brain/resources.py").read_text(encoding="utf-8")
    assert "506.7" not in text


def test_status_line_names_execution():
    line = status_line(
        photos=4,
        rss_mb=1200,
        pressure="ok",
        ep=CPU_EP,
        yielding=False,
        rates={"c1": 100.0},
        execution="emulated",
    )
    assert "execution=emulated" in line
    assert "ep=CPUExecutionProvider" in line
    assert "c1=100.0ph/min" in line


def test_pilot_status_checkpoint_and_no_region_crops(tmp_path):
    corpus = _corpus(tmp_path)
    store = tmp_path / "pilot.sqlite"
    paths, selection = select_paths(corpus, None)
    write_checkpoint(
        checkpoint_path(store),
        {
            "chunk_index": 1,
            "photos_done": 2,
            "corpus": str(corpus.resolve()),
            "limit": None,
            "selection": selection,
        },
    )
    out = tmp_path / "pilot.md"
    result = run_pilot(
        corpus=corpus,
        out=out,
        store=store,
        chunk=2,
        no_cluster=True,
        observer=_Tags(),
        ep_probe=lambda name: name == CPU_EP,
        pressure_fn=lambda: (13_000.0, 8_000.0),
    )
    text = out.read_text(encoding="utf-8")
    assert result.code == 0
    assert result.photos == len(paths) - 2
    assert "ep=CPUExecutionProvider" in text
    assert "execution=" in text
    assert "pressure=throttle" in text
    assert "Resumed at photo 2" in text
    pilot_src = Path("semblon/brain/pilot.py").read_text(encoding="utf-8")
    for banned in ("index_image_regions", "prepare_region_index", "persist_region_index"):
        assert banned not in pilot_src


def test_pilot_pauses_then_runs(tmp_path):
    waits: list[float] = []
    corpus = _corpus(tmp_path, n=2)
    result = run_pilot(
        corpus=corpus,
        out=tmp_path / "pause.md",
        store=tmp_path / "pause.sqlite",
        chunk=2,
        no_cluster=True,
        observer=_Tags(),
        ep_probe=lambda name: name == CPU_EP,
        pressure_fn=lambda: (100.0, 10.0),
        wait_fn=lambda seconds: waits.append(seconds),
    )
    assert result.code == 0
    assert result.photos == 2
    assert waits == [0.05, 0.05, 0.05]
    assert "pause held" in (tmp_path / "pause.md").read_text(encoding="utf-8")
