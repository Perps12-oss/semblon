"""Happy-path process command — no InsightFace."""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from semblon.cli import main
from semblon.process import (
    ProcessError,
    default_review_out,
    default_store_path,
    latest_run_id,
    process_folder,
)


def test_default_store_path_windows(monkeypatch):
    monkeypatch.setattr("semblon.process.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\me\AppData\Local")
    got = default_store_path()
    assert got.name == "store.sqlite"
    assert got.parent.name == "Semblon"


def test_default_review_out_beside_store(tmp_path):
    store = tmp_path / "Semblon" / "store.sqlite"
    store.parent.mkdir()
    assert default_review_out(store) == store.parent / "review.html"


def test_process_folder_orchestrates_and_owns_run_id(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"
    lines: list[str] = []

    with (
        patch(
            "semblon.process.ingest",
            return_value={
                "run_id": "RUN-ABC",
                "new_media": 3,
                "faces": 5,
                "ok": 4,
                "skipped_seen": 0,
            },
        ) as ing,
        patch(
            "semblon.process.cluster_run",
            return_value={
                "clusters": 2,
                "clustered": 4,
                "unassigned": 0,
            },
        ) as clu,
        patch(
            "semblon.process.export_review",
            return_value={
                "run_id": "RUN-ABC",
                "out": str(out),
                "clusters": 2,
                "faces": 5,
                "bytes": 100,
            },
        ) as exp,
        patch("semblon.process._try_open", return_value=False) as opener,
    ):
        rec = process_folder(
            folder,
            store=store,
            out=out,
            open_review=True,
            progress=lines.append,
        )

    ing.assert_called_once()
    assert ing.call_args.args[0] == folder.resolve() or ing.call_args.args[0] == folder
    assert ing.call_args.args[1] == store
    assert ing.call_args.kwargs.get("on_event") is None
    clu.assert_called_once()
    assert clu.call_args.args[0] == store
    assert clu.call_args.args[1] == "RUN-ABC"
    assert clu.call_args.kwargs["eps"] == 0.40
    assert clu.call_args.kwargs["min_samples"] == 2
    exp.assert_called_once_with(store, "RUN-ABC", out)
    opener.assert_called_once()
    assert rec["run_id"] == "RUN-ABC"
    assert any("Ingesting" in line for line in lines)
    assert any("Review ready" in line for line in lines)


def test_process_skip_all_exports_prior_run_with_faces(tmp_path):
    """A later empty ingest must not overwrite review.html with a blank page."""
    from semblon.export import EVIDENCE_SCRIPT_ID
    from tests.test_review_ui import _seed

    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"
    _seed(store)
    conn = sqlite3.connect(str(store))
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("r-empty", "t9", "t9b", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.commit()
    conn.close()
    assert latest_run_id(store) == "r-empty"
    assert latest_run_id(store, with_faces=True) == "r1"

    lines: list[str] = []
    with (
        patch(
            "semblon.process.ingest",
            return_value={
                "run_id": "r-empty",
                "new_media": 0,
                "faces": 0,
                "ok": 0,
                "skipped_seen": 2,
            },
        ),
        patch("semblon.process.cluster_run") as clu,
        patch("semblon.process._try_open", return_value=False),
    ):
        rec = process_folder(
            folder,
            store=store,
            out=out,
            open_review=False,
            progress=lines.append,
        )

    clu.assert_not_called()
    assert rec["run_id"] == "r1"
    html = out.read_text(encoding="utf-8")
    assert EVIDENCE_SCRIPT_ID in html
    assert "faces 5" in html
    assert any("reviewing existing run_id=r1" in line for line in lines)


def test_process_folder_missing_dir(tmp_path):
    with pytest.raises(ProcessError, match="folder not found"):
        process_folder(tmp_path / "nope", open_review=False, progress=lambda *_: None)


def test_cli_process_wires_flags(tmp_path, monkeypatch):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "s.sqlite"
    out = tmp_path / "r.html"
    seen = {}

    def fake_process(folder_arg, **kwargs):
        seen["folder"] = folder_arg
        seen["kwargs"] = kwargs
        return {"run_id": "x"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)

    rc = main(
        [
            "process",
            str(folder),
            "--store",
            str(store),
            "--out",
            str(out),
            "--no-open",
            "--reprocess",
        ]
    )
    assert rc == 0
    assert Path(seen["folder"]) == folder
    assert seen["kwargs"]["store"] == store
    assert seen["kwargs"]["out"] == out
    assert seen["kwargs"]["reprocess"] is True
    assert seen["kwargs"]["open_review"] is False
    assert seen["kwargs"]["resume"] is False
    assert callable(seen["kwargs"].get("on_event"))


def test_top_level_help_is_ascii():
    """Stock Windows cp1252 consoles must be able to print --help."""
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        with pytest.raises(SystemExit) as ei:
            main(["--help"])
    assert ei.value.code == 0
    text = buf.getvalue()
    assert "process" in text
    assert "ingest" in text
    assert text.isascii(), f"non-ASCII in help: {[c for c in text if not c.isascii()][:20]}"
