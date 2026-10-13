"""Regressions for the audit fixes. No InsightFace download and no identity retune."""

from __future__ import annotations

import json
import os
import signal
import socket
import sqlite3
import struct
import subprocess
import threading
import zlib
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import numpy as np
import pytest

from semblon.cluster import cluster_run
from semblon.eval import MIN_DIFFERENT, MIN_SAME, add_pair, create_set, freeze_set, score_set
from semblon.identify import IdentifyError, identify_image
from semblon.ingest import MAX_IMAGE_PIXELS, CancelledError, ingest, video_sampling_complete
from semblon.memory import read_still_exif, when_where
from semblon.process import find_resumable_run
from semblon.store import connect, init_db
from tests.test_cluster import _seed
from tests.test_eval import _face, _pairs_same, _seed_eval, _vec


def _jpeg(tiff: bytes) -> bytes:
    payload = b"Exif\x00\x00" + tiff
    # Fill 0xFF before APP1 is padding, not a marker.
    return b"\xff\xd8\xff\xff\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def _le_tiff(records: list[tuple[int, int, bytes]]) -> bytes:
    n = len(records)
    cursor = 8 + 2 + n * 12 + 4
    packed = bytearray()
    extras = bytearray()
    for tag, typ, payload in records:
        if typ == 4:
            packed += struct.pack("<HHI", tag, 4, 1) + payload
        elif typ == 2 and len(payload) <= 4:
            packed += struct.pack("<HHI", tag, 2, len(payload)) + payload.ljust(4, b"\x00")
        else:
            packed += struct.pack("<HHI", tag, typ, len(payload)) + struct.pack("<I", cursor)
            extras += payload
            cursor += len(payload)
    return b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", n) + bytes(packed) + struct.pack("<I", 0) + bytes(extras)


def _run_ingest(folder: Path, store: Path, embed, **kwargs) -> dict:
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", side_effect=embed),
        patch("semblon.ingest.cv2.imread", return_value=image),
        patch("semblon.ingest.cv2.imdecode", return_value=image),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        return ingest(folder, store, workers=1, **kwargs)


def _counts(store: Path) -> tuple[int, int, int]:
    conn = sqlite3.connect(str(store))
    try:
        obs = int(conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
        media = int(conn.execute("SELECT COUNT(*) FROM media").fetchone()[0])
        faces = int(conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0])
    finally:
        conn.close()
    return obs, media, faces


def _folder(tmp_path: Path, name: str = "a.jpg", payload: bytes | None = None) -> tuple[Path, Path]:
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / name).write_bytes(payload if payload is not None else b"\xff\xd8\xfffake")
    return folder, tmp_path / "s.sqlite"


def test_embed_failure_is_retried(tmp_path):
    folder, store = _folder(tmp_path)
    calls = {"n": 0}

    def embed(_app, _img):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("embed failed")
        return [{"bbox": (0, 0, 10, 10), "det_score": 0.9, "face_w": 100, "face_h": 100, "dim": 4, "embedding": np.zeros(4, np.float32)}]

    first = _run_ingest(folder, store, embed)
    assert first["failed"] == 1
    assert _counts(store) == (0, 0, 0)
    second = _run_ingest(folder, store, embed)
    assert second["ok"] >= 1
    obs, media, faces = _counts(store)
    assert obs == 1 and media == 1 and faces >= 1


def test_cancel_before_embed_drops_observation(tmp_path):
    folder, store = _folder(tmp_path)
    seen = {"n": 0}

    def cancel():
        seen["n"] += 1
        return seen["n"] >= 3

    def embed(_app, _img):
        raise AssertionError("embed ran after cancel")

    with pytest.raises(CancelledError):
        _run_ingest(folder, store, embed, cancel=cancel)
    assert _counts(store)[0] == 0
    store.unlink()


def test_video_frame_failure_is_not_sampling_complete(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"not-a-real-video")
    store = tmp_path / "s.sqlite"
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    calls = {"n": 0}

    def frames(_path, _hz):
        yield 0, 0, frame

    def embed(_app, _img):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("frame embed failed")
        return [{"bbox": (0, 0, 4, 4), "det_score": 0.9, "face_w": 100, "face_h": 100, "dim": 4, "embedding": np.zeros(4, np.float32)}]

    with patch("semblon.ingest.iter_sampled_frames", side_effect=frames):
        first = _run_ingest(folder, store, embed)
    assert first["failed"] == 1
    conn = connect(store)
    try:
        media_id = conn.execute("SELECT media_id FROM media").fetchone()[0]
        assert video_sampling_complete(conn, media_id) is False
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    finally:
        conn.close()
    with patch("semblon.ingest.iter_sampled_frames", side_effect=frames):
        second = _run_ingest(folder, store, embed)
    assert second["ok"] >= 1
    conn = connect(store)
    try:
        assert video_sampling_complete(conn, media_id) is True
    finally:
        conn.close()


def test_resume_refuses_pack_mismatch_and_closes(tmp_path):
    folder, store = _folder(tmp_path)
    vec = [{"bbox": (0, 0, 8, 8), "det_score": 0.9, "face_w": 40, "face_h": 40, "dim": 4, "embedding": np.zeros(4, np.float32)}]
    rec = _run_ingest(folder, store, lambda *_a: vec)
    conn = sqlite3.connect(str(store))
    conn.execute(
        "UPDATE runs SET pack_id=? WHERE run_id=?",
        ("insightface/buffalo_l@2.0/adapter-1/sha256:aaaaaaaaaaaaaaaa", rec["run_id"]),
    )
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="pack_id mismatch"):
        _run_ingest(folder, store, lambda *_a: vec, resume_run_id=rec["run_id"])
    store.unlink()


def test_null_ort_and_missing_opencv_still_resume(tmp_path):
    folder, store = _folder(tmp_path)
    vec = [{"bbox": (0, 0, 8, 8), "det_score": 0.9, "face_w": 40, "face_h": 40, "dim": 4, "embedding": np.zeros(4, np.float32)}]
    rec = _run_ingest(folder, store, lambda *_a: vec)
    conn = sqlite3.connect(str(store))
    runtime = json.loads(conn.execute("SELECT runtime_json FROM runs WHERE run_id=?", (rec["run_id"],)).fetchone()[0])
    runtime.pop("opencv_version", None)
    conn.execute(
        "UPDATE runs SET ort_version=NULL, runtime_json=? WHERE run_id=?",
        (json.dumps(runtime), rec["run_id"]),
    )
    conn.commit()
    conn.close()
    again = _run_ingest(folder, store, lambda *_a: vec, resume_run_id=rec["run_id"])
    assert again["run_id"] == rec["run_id"]


def test_cluster_s_marks_zero_cluster_run_finished(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    conn.execute(
        "UPDATE runs SET finished_at=?, notes=NULL, config_json=?, timings_json=? WHERE run_id='r1'",
        ("t", json.dumps({"folder": str(folder.resolve())}), "{}"),
    )
    conn.commit()
    conn.close()
    assert find_resumable_run(store, folder) == "r1"
    conn = sqlite3.connect(str(store))
    conn.execute(
        "UPDATE runs SET timings_json=? WHERE run_id='r1'",
        (json.dumps({"ingest_s": 1.0, "cluster_s": 0.2}),),
    )
    conn.commit()
    conn.close()
    assert find_resumable_run(store, folder) is None


def _insert_run(store: Path, pack: str) -> None:
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", pack, 4, "l2", "{}", "{}", "x64", "native"),
    )
    conn.commit()
    conn.close()


def test_identify_refuses_pack_mismatch_without_writing_faces(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    _insert_run(store, "stored-pack")
    monkeypatch.setattr(
        "semblon.engine.current_identity_space",
        lambda: {"pack_id": "live-pack", "ort_version": "9", "opencv_version": "9"},
    )
    image = tmp_path / "a.jpg"
    image.write_bytes(b"\xff\xd8\xff")
    with pytest.raises(IdentifyError, match="pack_id mismatch"):
        identify_image(store, "r1", image, app=object())
    conn = sqlite3.connect(str(store))
    try:
        assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    finally:
        conn.close()


def test_identify_allows_older_run_without_ort_or_opencv(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    _insert_run(store, "stored-pack")
    monkeypatch.setattr(
        "semblon.engine.current_identity_space",
        lambda: {"pack_id": "stored-pack", "ort_version": "9.9.9", "opencv_version": "9"},
    )
    monkeypatch.setattr("semblon.engine.embed_image", lambda _app, _image: [])
    image = tmp_path / "a.jpg"
    image.write_bytes(b"\xff\xd8\xff")
    rec = identify_image(store, "r1", image, app=object())
    assert rec["decision"] == "UNKNOWN"
    assert rec["faces"] == 0
    conn = sqlite3.connect(str(store))
    try:
        assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    finally:
        conn.close()


def test_cluster_keeps_ingest_timings(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    conn.execute(
        "UPDATE runs SET timings_json=? WHERE run_id='r1'",
        (json.dumps({"ingest_s": 1.25, "files": 2}),),
    )
    conn.commit()
    conn.close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = sqlite3.connect(str(store))
    timings = json.loads(conn.execute("SELECT timings_json FROM runs WHERE run_id='r1'").fetchone()[0])
    conn.close()
    assert timings["ingest_s"] == 1.25
    assert timings["files"] == 2
    assert "cluster_s" in timings
    assert timings["stage"] == "cluster"


def test_skipped_pairs_do_not_dilute_far(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_eval(store)
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    for i in range(5):
        _face(conn, f"skip{i}", "o1", None, status="rejected")
    conn.commit()
    conn.close()
    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    for a, b in _pairs_same(5, "a")[:MIN_SAME]:
        add_pair(store, "c1", a, b, "same", "easy")
    easy = [(f"a{i}", f"b{j}") for i in range(5) for j in range(5)][: MIN_DIFFERENT - 1]
    for a, b in easy:
        add_pair(store, "c1", a, b, "different", "easy")
    add_pair(store, "c1", "h1", "h2", "different", "lookalike")
    skip_ids = [f"skip{i}" for i in range(5)]
    for i, a in enumerate(skip_ids):
        for b in skip_ids[i + 1 :]:
            add_pair(store, "c1", a, b, "different", "not_ok")
    freeze_set(store, "c1")
    rec = score_set(store, "c1")
    assert rec["status"] == "measurable"
    assert rec["counts"]["different"] > rec["counts"]["different_scored"]
    assert rec["counts"]["different_scored"] == MIN_DIFFERENT
    assert rec["counts"]["false_accept"] == 1
    assert rec["far"] == pytest.approx(1 / MIN_DIFFERENT)
    assert rec["far"] != pytest.approx(1 / rec["counts"]["different"])


def test_skipped_same_pairs_stay_underpowered(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_eval(store)
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    for i in range(5):
        _face(conn, f"bad{i}", "o1", None, status="rejected")
    conn.commit()
    conn.close()
    create_set(store, "c1", "confirmatory_hard", pack_id="pack-a")
    ids = [f"bad{i}" for i in range(5)]
    same = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            same.append((a, b))
    assert len(same) >= MIN_SAME
    for a, b in same[:MIN_SAME]:
        add_pair(store, "c1", a, b, "same", "not_ok")
    easy = [(f"a{i}", f"b{j}") for i in range(5) for j in range(5)][: MIN_DIFFERENT - 1]
    for a, b in easy:
        add_pair(store, "c1", a, b, "different", "easy")
    add_pair(store, "c1", "h1", "h2", "different", "lookalike")
    freeze_set(store, "c1")
    rec = score_set(store, "c1")
    assert rec["counts"]["same"] >= MIN_SAME
    assert rec["counts"]["same_scored"] == 0
    assert rec["status"] == "underpowered"
    assert rec["far"] is None
    assert rec["frr"] is None


def test_exif_offset_naive_and_malformed(tmp_path):
    dt = b"2020:01:02 03:04:05\x00"
    off = b"+05:30\x00"
    stamped = tmp_path / "offset.jpg"
    stamped.write_bytes(_jpeg(_le_tiff([(0x9003, 2, dt), (0x9011, 2, off)])))
    rec = read_still_exif(stamped)
    assert rec["datetime_original"].startswith("2020-01-01T21:34:05")
    assert rec["datetime_original_ns"] > 0
    placed = when_where(str(stamped), 1)
    assert placed["when_source"] == "exif"

    naive = tmp_path / "naive.jpg"
    naive.write_bytes(_jpeg(_le_tiff([(0x9003, 2, dt)])))
    rec = read_still_exif(naive)
    assert rec["datetime_original"].startswith("2020-01-02T03:04:05")
    assert "datetime_original_ns" not in rec
    wall = when_where(str(naive), 1_700_000_000_000_000_000)
    assert wall["when_source"] == "mtime"

    gps_off = 8 + 2 + 2 * 12 + 4 + len(dt)
    tiff = _le_tiff([(0x9003, 2, dt), (0x8825, 4, struct.pack("<I", gps_off))])
    gps = struct.pack("<H", 1) + struct.pack("<HHI", 2, 5, 3) + struct.pack("<I", 999999)
    broken = tmp_path / "gps.jpg"
    broken.write_bytes(_jpeg(tiff + gps))
    rec = read_still_exif(broken)
    assert rec["datetime_original"].startswith("2020-01-02T03:04:05")
    assert "lat" not in rec

    short = tmp_path / "short.jpg"
    short.write_bytes(b"\xff\xd8\xff\xe1\x00\x04EX")
    assert read_still_exif(short) == {}
    assert read_still_exif(tmp_path / "missing.jpg") == {}


def test_still_byte_and_pixel_caps_do_not_store_media(tmp_path, monkeypatch):
    face = [{"bbox": (0, 0, 8, 8), "det_score": 0.9, "face_w": 40, "face_h": 40, "dim": 4, "embedding": np.zeros(4, np.float32)}]
    folder, store = _folder(tmp_path, payload=b"\xff\xd8\xff" + b"x" * 32)
    monkeypatch.setattr("semblon.ingest.MAX_STILL_BYTES", 8)
    rec = _run_ingest(folder, store, lambda *_a: face)
    assert rec["failed"] == 1
    assert _counts(store)[1] == 0

    wide = 10000
    high = (MAX_IMAGE_PIXELS // wide) + 2
    ihdr = struct.pack(">IIBBBBB", wide, high, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
    folder2 = tmp_path / "pngs"
    folder2.mkdir()
    (folder2 / "huge.png").write_bytes(png)
    store2 = tmp_path / "pixels.sqlite"
    monkeypatch.setattr("semblon.ingest.MAX_STILL_BYTES", 256 * 1024 * 1024)
    rec = _run_ingest(folder2, store2, lambda *_a: face)
    assert rec["failed"] == 1
    assert rec["new_media"] == 0
    assert _counts(store2)[1] == 0


def test_ingest_restores_sigint_and_closes(tmp_path):
    folder, store = _folder(tmp_path)
    before = signal.getsignal(signal.SIGINT)
    vec = [{"bbox": (0, 0, 8, 8), "det_score": 0.9, "face_w": 40, "face_h": 40, "dim": 4, "embedding": np.zeros(4, np.float32)}]
    _run_ingest(folder, store, lambda *_a: vec)
    assert signal.getsignal(signal.SIGINT) == before
    store.unlink()
    with pytest.raises(ValueError, match="unknown run"):
        _run_ingest(folder, store, lambda *_a: vec, resume_run_id="missing-run")
    store.unlink()


def test_cancel_exception_stops_ingest(tmp_path):
    folder, store = _folder(tmp_path)

    def cancel():
        raise RuntimeError("cancel broke")

    with pytest.raises(CancelledError):
        _run_ingest(folder, store, lambda *_a: [], cancel=cancel)


def test_watch_reraises_cancel_errors(tmp_path, monkeypatch):
    folder = tmp_path / "photos"
    folder.mkdir()
    monkeypatch.setattr(
        "semblon.watch.ingest",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("ingest ran")),
    )
    from semblon.watch import watch_folder

    def cancel():
        raise RuntimeError("cancel broke")

    with pytest.raises(RuntimeError, match="cancel broke"):
        watch_folder(folder, tmp_path / "s.sqlite", cancel=cancel)


def test_live_setup_failure_releases_capture(tmp_path, monkeypatch):
    released = {"n": 0}

    class Cap:
        def release(self):
            released["n"] += 1

        def isOpened(self):
            return True

    cap = Cap()

    class Boom:
        def load(self, *_a, **_k):
            raise RuntimeError("model unavailable")

    monkeypatch.setitem(__import__("sys").modules, "insightface", ModuleType("insightface"))
    monkeypatch.setitem(__import__("sys").modules, "onnxruntime", ModuleType("onnxruntime"))
    monkeypatch.setattr("semblon.providers.FaceKitProvider", Boom)
    from semblon.live import live_capture

    store = tmp_path / "s.sqlite"
    with pytest.raises(RuntimeError, match="model unavailable"):
        live_capture(store, seconds=0.1, capture_factory=lambda _src: cap)
    assert released["n"] >= 1
    store.unlink()


def test_clip_runtime_error_is_not_a_concept(monkeypatch):
    import semblon.semantic_visual as sv

    monkeypatch.setitem(__import__("sys").modules, "open_clip", ModuleType("open_clip"))
    monkeypatch.setitem(__import__("sys").modules, "torch", ModuleType("torch"))
    monkeypatch.setattr("semblon.observers.probe_clip_status", lambda: (True, "ready"))
    monkeypatch.setattr(sv, "_load_clip_bundle", lambda: (_ for _ in ()).throw(RuntimeError("weights")))
    monkeypatch.setattr(sv, "_vlm_image_concepts", lambda *_a, **_k: [])
    sv._CLIP_LAST_ERROR = None
    provider = sv.LocalSemanticVisualProvider()
    concepts = provider.discover_concepts(np.zeros((8, 8, 3), dtype=np.uint8), regions=[])
    assert concepts == []
    assert provider.last_optional_errors
    assert provider.last_optional_errors[0].startswith("clip: RuntimeError")
    assert all(not str(item.get("label", "")).startswith("clip:") for item in concepts)


def test_face_crop_clips_and_cancel(qapp, tmp_path):
    from PySide6.QtGui import QImage

    from semblon.native_shell.images import FaceCropImageResponse, _CropFace

    path = tmp_path / "a.png"
    image = QImage(40, 20, QImage.Format.Format_RGB32)
    image.fill(0xFF112233)
    assert image.save(str(path))
    response = FaceCropImageResponse(str(path), (2, 2, 10, 8), 64)
    _CropFace(response, str(path), (2, 2, 10, 8), 64).run()
    assert not response._image.isNull()
    assert response._image.width() <= 10
    assert response._image.height() <= 8
    response.cancel()
    assert response.cancelled is True
    assert "setClipRect" in _CropFace.run.__code__.co_names


def test_ipc_oversize_line_closes_client(tmp_path):
    from semblon.ipc_probe import IpcProbeServer

    left, right = socket.socketpair()
    server = IpcProbeServer(tmp_path / "s.sqlite")
    worker = threading.Thread(target=server._serve_client, args=(left,), daemon=True)
    worker.start()
    right.settimeout(3)
    try:
        right.sendall(b"A" * ((1 << 20) + 32))
    except OSError:
        pass
    worker.join(3)
    right.close()
    assert worker.is_alive() is False


def test_lens_failure_clears_busy(tmp_path, monkeypatch):
    import semblon.home_ui as home_ui

    class ImmediateThread:
        def __init__(self, target=None, name=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    states = []

    class Btn:
        def configure(self, **kwargs):
            states.append(kwargs.get("state"))

    class Root:
        def after(self, _delay, fn):
            fn()

    monkeypatch.setattr(home_ui.threading, "Thread", ImmediateThread)
    monkeypatch.setattr("semblon.selection.media_file", lambda _store, _media: tmp_path / "p.jpg")
    host = home_ui.HomeApp.__new__(home_ui.HomeApp)
    host.store = tmp_path / "s.sqlite"
    host._insp_media_id = "m1"
    host.app = type("App", (), {"query_media": staticmethod(lambda _mid: (_ for _ in ()).throw(RuntimeError("look failed")))})()
    host.root = Root()
    host._lens_busy = False
    host.btn_lens_region = Btn()
    host.btn_lens_whole = Btn()
    host._set_inspector = lambda *_a, **_k: None
    host._set_lens_processing = lambda *_a, **_k: None
    host._refresh_lens_workspace = lambda: None
    host._lens_ask_whole()
    assert host._lens_busy is False
    assert "normal" in states


def test_atmosphere_tertiary_contrast():
    from semblon.atmosphere import ATMOSPHERES
    from tests.test_ui_tokens import _contrast

    for spec in ATMOSPHERES.values():
        for bg in (spec.surface, spec.surface_muted, spec.surface_raised):
            assert _contrast(spec.text_tertiary, bg) >= 4.5


def test_installer_native_failure_and_dotsource(tmp_path):
    script = Path(__file__).resolve().parents[1] / "tools" / "install-windows.ps1"
    exe = tmp_path / "python.exe"
    env = os.environ.copy()
    env["FAKE_PY"] = str(exe)
    compile_ps = r'''
Add-Type -OutputType ConsoleApplication -OutputAssembly $env:FAKE_PY -TypeDefinition @"
using System;
public class Program {
    public static int Main(string[] args) { return 3; }
}
"@
if (-not (Test-Path -LiteralPath $env:FAKE_PY)) { exit 2 }
'''
    compiled = subprocess.run(
        ["powershell", "-NoProfile", "-Command", compile_ps],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert compiled.returncode == 0, compiled.stderr
    root = tmp_path / "root"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\nversion = '0.0.0'\n", encoding="utf-8")
    (root / "requirements.txt").write_text("# none\n", encoding="utf-8")
    failed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(script),
            "-Root",
            str(root),
            "-PythonLauncher",
            str(exe),
            "-PythonVersion",
            "-3.12",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode != 0
    assert "exit code" in (failed.stderr + failed.stdout)
    assert not (root / ".venv").exists()

    sourced = tmp_path / "sourced"
    tools = sourced / "tools"
    tools.mkdir(parents=True)
    (sourced / "pyproject.toml").write_text("[project]\nname = 'y'\nversion = '0.0.0'\n", encoding="utf-8")
    dest = tools / "install-windows.ps1"
    dest.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    dot = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f". '{dest}'; if (Test-Path -LiteralPath '{sourced / '.venv'}') {{ exit 4 }}; exit 0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dot.returncode == 0, dot.stderr
    assert not (sourced / ".venv").exists()
