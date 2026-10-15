"""UX Rescue §7 — Advanced Diagnostics collector (read-only)."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

from semblon.advanced_diagnostics import (
    build_advanced_diagnostics_lines,
    open_advanced_diagnostics,
)
from semblon.store import init_db


def _seed_run(store: Path, run_id: str = "r-diag-1") -> None:
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id,
            "2026-09-22T12:00:00Z",
            "2026-09-22T12:05:00Z",
            "0.0.1",
            "pack-a",
            2,
            "l2",
            "{}",
            "{}",
            "x64",
            "native",
            None,
        ),
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)"
    )
    conn.execute(
        "INSERT INTO observations VALUES ('o1','m1',NULL,NULL,?)", (run_id,)
    )
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "f1",
            "o1",
            run_id,
            0,
            0,
            20,
            20,
            0.9,
            20,
            20,
            "80-119",
            "ok",
            b"\x00" * 8,
            "pack-a",
            2,
        ),
    )
    conn.commit()
    conn.close()


def test_build_lines_sections_and_settings_content(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_run(store)
    text = "\n".join(build_advanced_diagnostics_lines(store))

    for heading in (
        "— Store —",
        "— Processing —",
        "— Observers —",
        "— Architecture —",
        "— Recent runs —",
    ):
        assert heading in text

    # Store + integrity (Activity-style line preserved).
    assert f"Store: {store}" in text
    assert "integrity ok=" in text

    # Processing / weights / EP (from Settings dump).
    assert "FaceKit" in text
    assert "Weights dir:" in text
    assert "onnx files:" in text
    assert "Provider: FaceKit" in text
    assert "ORT providers:" in text

    # Observers + firewall notes from modality_product_settings_lines.
    assert "Home observers (base):" in text
    assert "embeddings.modality=face" in text or "modality=face" in text
    assert "faces.person_id" in text

    # Architecture strings currently in _show_settings.
    assert "JobEngine job, not an application lock" in text
    assert "R3 chrome" in text
    assert "compatibility Tk" in text or "AppShell" in text

    # Recent runs best-effort.
    assert "r-diag-1" in text
    assert "faces=1" in text


def test_build_lines_missing_store(tmp_path):
    missing = tmp_path / "nope.sqlite"
    text = "\n".join(build_advanced_diagnostics_lines(missing))
    assert "Store:" in text
    assert "not present" in text.lower() or "integrity" in text.lower()
    assert "(no runs" in text


def test_open_advanced_diagnostics_is_public_and_import_safe():
    assert callable(open_advanced_diagnostics)
    src = inspect.getsource(open_advanced_diagnostics)
    assert "Copy all" in src
    assert "Toplevel" in src or "tk is None" in src


