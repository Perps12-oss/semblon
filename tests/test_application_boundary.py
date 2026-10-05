"""Application is UI-independent. Visual commands use media identity."""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semblon.application import Application
from semblon.home_ui import HomeApp
from semblon.product_features import build_product_registry


def test_importing_application_does_not_import_tk(tmp_path):
    script = """
import sys
from pathlib import Path
import semblon.application
from semblon.application import Application
forbidden = ("tkinter", "semblon.home_ui", "semblon.lens_home", "semblon.review_ui", "semblon.canvas")
leaked = [name for name in forbidden if name in sys.modules]
assert not leaked, leaked
app = Application(Path(sys.argv[1]) / "s.sqlite")
assert app.engine is not None
assert app.archive_count() == 0
try:
    app.board()
except Exception:
    pass
missing = app.query_media("missing")
assert missing["status"] == "UNAVAILABLE"
app.pause_job()
forbidden = ("tkinter", "semblon.home_ui", "semblon.lens_home", "semblon.review_ui", "semblon.canvas", "PySide6")
leaked = [name for name in forbidden if name in sys.modules]
assert not leaked, leaked
"""
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(root),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_application_constructs_without_a_ui(tmp_path):
    app = Application(tmp_path / "s.sqlite")
    assert app.busy is False
    assert app.state == "idle"
    assert app.job_current() is None
    states = app.control_states(resume_ready=False)
    assert states["pause"] == "disabled"
    assert states["folder"] == "normal"


def test_query_media_uses_media_id_not_a_ui_image(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    from semblon.store import connect, init_db

    photo = tmp_path / "a.png"
    cv2.imwrite(str(photo), np.zeros((12, 16, 3), dtype=np.uint8))
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h", 16, 12, 1, 1),
    )
    conn.commit()
    conn.close()

    app = Application(store)
    whole = app.query_media("m1", capabilities=("barcode",))
    assert whole["media_id"] == "m1"
    assert whole["region"]["w"] == 16
    assert whole["region"]["h"] == 12
    assert "lines" in whole
    region = app.query_media("m1", {"x": 1, "y": 2, "w": 4, "h": 5}, capabilities=("barcode",))
    assert region["region"]["x"] == 1
    assert region["region"]["w"] == 4
    assert region["region"]["h"] == 5
    missing = app.query_media("missing")
    assert missing["status"] == "UNAVAILABLE"
    assert "Nothing was searched" in " ".join(missing["lines"])


def test_submit_visual_command_is_media_id(tmp_path):
    app = Application(tmp_path / "s.sqlite")
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return "handle"

    app.engine.submit_visual = fake
    handle = app.submit_visual("m1", run_id="r1", view_w=32)
    assert handle == "handle"
    assert seen["media_id"] == "m1"
    assert "image" not in seen
    assert seen["run_id"] == "r1"
    assert seen["view_w"] == 32


def test_inspector_ask_runs_whole_frame_query():
    class Host:
        def __init__(self, media_id):
            self.calls = []
            self._insp_media_id = media_id

        def _set_inspector(self, *_args):
            self.calls.append("empty")

        def _open_lens(self):
            self.calls.append("open")

        def _lens_ask_whole(self):
            self.calls.append("whole")

    host = Host("m9")
    host._ask_with_lens = HomeApp._ask_with_lens.__get__(host, Host)
    HomeApp._ask_with_lens(host)
    assert host.calls == ["open", "whole"]

    host.calls.clear()
    cmd = build_product_registry().get_command("lens.ask")
    assert cmd is not None
    assert cmd.label == "Ask about this photo"
    cmd.run(host)
    assert host.calls == ["open", "whole"]

    empty = Host(None)
    HomeApp._ask_with_lens(empty)
    assert "whole" not in empty.calls
    assert empty.calls == ["empty"]

    whole = inspect.getsource(HomeApp._lens_ask_whole)
    assert "query_media" in whole
    assert "run_lens_query" not in whole
    assert "query_image(" not in whole


def test_home_does_not_construct_a_job_engine():
    root = Path(__file__).resolve().parents[1]
    home = (root / "semblon" / "home_ui.py").read_text(encoding="utf-8")
    app = (root / "semblon" / "application.py").read_text(encoding="utf-8")
    assert "JobEngine(" not in home
    assert "self.engine = JobEngine(self.store)" in app
    assert "_install_lens_home" not in app
    init = inspect.getsource(HomeApp.__init__)
    assert "self.app = Application(self.store)" in init
    assert "self.engine = self.app.engine" in init
