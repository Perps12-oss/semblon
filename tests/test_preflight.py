"""Preflight uses injected pins and probes. It does not read this machine's models."""

from __future__ import annotations

from pathlib import Path

RUNTIME = """
# comment
pillow==13.0.0
numpy==2.4.6; python_version < "3.12"
numpy==2.5.3; python_version >= "3.12"
opencv-python-headless==5.0.0.93
"""

DEV = """
-r requirements.txt
pytest==9.1.1
"""


def _probes(**overrides):
    base = {
        "region": lambda: (False, "region model missing"),
        "object": lambda: (False, "object model missing"),
        "vlm": lambda: "MISSING",
        "ocr": lambda: (False, "tesseract missing"),
        "clip": lambda: (False, "clip weights missing"),
        "face": lambda: (False, "face weights missing"),
        "opencv_load": lambda: (True, "5.0.0.93", None),
        "arch": lambda: ("native", "x64"),
    }
    base.update(overrides)
    return base


def _kw(**overrides):
    base = {
        "runtime_text": RUNTIME,
        "dev_text": DEV,
        "python_version": (3, 12),
        "installed": {
            "pillow": "13.0.0",
            "numpy": "2.5.3",
            "opencv-python-headless": "5.0.0.93",
            "pytest": "9.1.1",
        },
        "venv": True,
        "probes": _probes(),
    }
    base.update(overrides)
    return base


def test_satisfied_pin_is_skipped_and_not_reinstalled():
    from semblon.preflight import install_item

    def boom(_spec):
        raise AssertionError("pip was called for a satisfied pin")

    rec = install_item("pkg:pillow", pip_install=boom, **_kw())
    assert rec["ready"] is True
    assert rec["skipped"] is True


def test_missing_pin_installs_then_verifies():
    from semblon.preflight import collect_rows, install_item

    installed = {
        "numpy": "2.5.3",
        "opencv-python-headless": "5.0.0.93",
        "pytest": "9.1.1",
    }
    calls = []

    def pip(spec):
        calls.append(spec)
        name, version = spec.split("==", 1)
        installed[name] = version

    before = {row["id"]: row for row in collect_rows(**_kw(installed=installed))}
    assert before["pkg:pillow"]["status"] == "missing"
    assert before["pkg:pillow"]["installable"] is True
    rec = install_item("pkg:pillow", pip_install=pip, **_kw(installed=installed))
    assert calls == ["pillow==13.0.0"]
    assert rec["ready"] is True
    assert rec["skipped"] is False
    assert installed["pillow"] == "13.0.0"


def test_pip_that_does_not_install_the_pin_stays_failed():
    from semblon.preflight import install_item

    installed = {
        "numpy": "2.5.3",
        "opencv-python-headless": "5.0.0.93",
        "pytest": "9.1.1",
    }

    def pip(spec):
        assert spec == "pillow==13.0.0"

    rec = install_item("pkg:pillow", pip_install=pip, **_kw(installed=installed))
    assert rec["ready"] is False
    assert rec["status"] == "failed"
    assert "pillow" not in installed


def test_incompatible_pin_is_not_treated_as_ready():
    from semblon.preflight import collect_rows

    installed = {
        "pillow": "12.0.0",
        "numpy": "2.5.3",
        "opencv-python-headless": "5.0.0.93",
        "pytest": "9.1.1",
    }
    row = {item["id"]: item for item in collect_rows(**_kw(installed=installed))}["pkg:pillow"]
    assert row["status"] == "incompatible"
    assert row["found"] == "12.0.0"
    assert row["installable"] is True


def test_system_python_is_not_an_install_target():
    from semblon.preflight import install_item

    installed = {"numpy": "2.5.3", "opencv-python-headless": "5.0.0.93", "pytest": "9.1.1"}

    def boom(_spec):
        raise AssertionError("system Python was changed")

    rec = install_item("pkg:pillow", pip_install=boom, **_kw(installed=installed, venv=False))
    assert rec["ready"] is False
    assert "system Python" in rec["error"]


def test_failed_install_stays_unresolved():
    from semblon.preflight import install_item

    installed = {"numpy": "2.5.3", "opencv-python-headless": "5.0.0.93", "pytest": "9.1.1"}

    def pip(_spec):
        raise RuntimeError("disk full")

    rec = install_item("pkg:pillow", pip_install=pip, **_kw(installed=installed))
    assert rec == {
        "id": "pkg:pillow",
        "status": "failed",
        "ready": False,
        "skipped": False,
        "error": "disk full",
    }
    assert "pillow" not in installed


def test_install_that_does_not_verify_is_not_success():
    from semblon.preflight import install_item

    def install():
        return {"changed": True}

    rec = install_item(
        "region_pack",
        installers={"region_pack": install},
        **_kw(),
    )
    assert rec["ready"] is False
    assert rec["status"] == "failed"
    assert rec["skipped"] is False


def test_verified_model_install_is_ready():
    from semblon.preflight import install_item

    state = {"ready": False}

    def region():
        return state["ready"], "region model missing"

    def install():
        state["ready"] = True

    rec = install_item(
        "region_pack",
        installers={"region_pack": install},
        **_kw(probes=_probes(region=region)),
    )
    assert rec["ready"] is True
    assert rec["skipped"] is False


def test_present_model_is_not_installed_again():
    from semblon.preflight import install_item

    def boom():
        raise AssertionError("region installer ran")

    rec = install_item(
        "region_pack",
        installers={"region_pack": boom},
        **_kw(probes=_probes(region=lambda: (True, None))),
    )
    assert rec["ready"] is True
    assert rec["skipped"] is True


def test_optional_absence_does_not_fail_required_pins():
    from semblon.preflight import required_gaps

    gaps = required_gaps(**_kw())
    assert gaps == []


def test_face_pack_and_clip_are_not_download_buttons():
    from semblon.preflight import collect_rows, install_item

    rows = {row["id"]: row for row in collect_rows(**_kw())}
    assert rows["face_pack"]["installable"] is False
    assert rows["clip"]["installable"] is False
    assert rows["ocr"]["installable"] is False
    assert rows["authenticode"]["installable"] is False
    assert rows["model_licence"]["status"] == "blocked"

    def boom():
        raise AssertionError("weight download")

    rec = install_item("face_pack", installers={"face_pack": boom}, **_kw())
    assert rec["ready"] is False
    assert "does not download" in rec["error"]


def test_opencv_package_can_be_present_while_the_library_fails_to_load():
    from semblon.preflight import collect_rows

    rows = {
        row["id"]: row
        for row in collect_rows(**_kw(probes=_probes(opencv_load=lambda: (False, "", "ImportError"))))
    }
    assert rows["pkg:opencv-python-headless"]["status"] == "ready"
    assert rows["opencv_load"]["status"] == "incompatible"
    assert rows["opencv_load"]["installable"] is False


def test_emulated_architecture_is_not_called_native():
    from semblon.preflight import collect_rows

    row = {
        item["id"]: item
        for item in collect_rows(**_kw(probes=_probes(arch=lambda: ("emulated", "x64"))))
    }["architecture"]
    assert row["status"] == "unverifiable"
    assert row["installable"] is False
    assert "not claimed" in row["detail"]


def test_cancel_before_and_after_does_not_report_ready():
    from semblon.preflight import install_item

    rec = install_item("region_pack", cancel=lambda: True, **_kw())
    assert rec["status"] == "cancelled"
    assert rec["ready"] is False

    state = {"ready": False, "checks": 0}

    def region():
        return state["ready"], "missing"

    def install():
        state["ready"] = True

    def cancel():
        state["checks"] += 1
        return state["checks"] > 1

    rec = install_item(
        "region_pack",
        installers={"region_pack": install},
        cancel=cancel,
        **_kw(probes=_probes(region=region)),
    )
    assert rec["status"] == "cancelled"
    assert rec["ready"] is False


def test_runtime_pins_come_from_requirements_txt():
    from semblon.preflight import parse_pins

    text = Path("requirements.txt").read_text(encoding="utf-8")
    pins = {
        row["name"]: row["version"]
        for row in parse_pins(text, python_version=(3, 12))
        if row["status"] != "unverifiable"
    }
    assert pins["pillow"] == "13.0.0"
    assert pins["numpy"] == "2.5.3"
    assert pins["opencv-python-headless"] == "5.0.0.93"
    older = {
        row["name"]: row["version"]
        for row in parse_pins(text, python_version=(3, 11))
        if row["status"] != "unverifiable"
    }
    assert older["numpy"] == "2.4.6"


def test_settings_offers_one_install_per_missing_capability():
    qml = Path("semblon/native_shell/qml/Shell.qml").read_text(encoding="utf-8")
    assert 'objectName: "preflightRepeater"' in qml
    assert "shellApi.installPreflight(model.itemId)" in qml
    assert "Install everything" not in qml


def test_cli_reports_without_installing_and_failed_install_exits_nonzero(monkeypatch, capsys):
    from semblon.cli import main

    monkeypatch.setattr(
        "semblon.preflight.collect_rows",
        lambda **_kwargs: [
            {
                "id": "pkg:pillow",
                "status": "ready",
                "detail": "pillow 13.0.0 is already installed.",
            }
        ],
    )
    called = []
    monkeypatch.setattr(
        "semblon.preflight.install_item",
        lambda item_id, **_kwargs: called.append(item_id) or {
            "id": item_id,
            "status": "failed",
            "ready": False,
            "skipped": False,
            "error": "disk full",
        },
    )
    assert main(["lab", "preflight"]) == 0
    assert called == []
    assert "pkg:pillow" in capsys.readouterr().out
    assert main(["lab", "preflight", "--install", "region_pack"]) == 1
    assert "disk full" in capsys.readouterr().out


def test_cli_exits_nonzero_when_required_or_failed(monkeypatch, capsys):
    from semblon.cli import main

    optional = [
        {
            "id": "vlm_local",
            "status": "missing",
            "required": False,
            "detail": "Description model is not installed.",
        }
    ]
    monkeypatch.setattr("semblon.preflight.collect_rows", lambda **_kwargs: list(optional))
    assert main(["lab", "preflight"]) == 0
    assert "vlm_local" in capsys.readouterr().out

    monkeypatch.setattr(
        "semblon.preflight.collect_rows",
        lambda **_kwargs: optional
        + [
            {
                "id": "pkg:pillow",
                "status": "incompatible",
                "required": True,
                "detail": "Found pillow 12.3.0. The pin requires 13.0.0.",
            }
        ],
    )
    assert main(["lab", "preflight"]) == 1
    assert "12.3.0" in capsys.readouterr().out

    monkeypatch.setattr(
        "semblon.preflight.collect_rows",
        lambda **_kwargs: [
            {
                "id": "region_pack",
                "status": "failed",
                "required": False,
                "detail": "Region model could not be checked. RuntimeError: boom",
            }
        ],
    )
    assert main(["lab", "preflight"]) == 1
    assert "boom" in capsys.readouterr().out


def test_settings_install_failure_does_not_mark_the_capability_ready(tmp_path, monkeypatch):
    import pytest

    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    missing = {
        "id": "region_pack",
        "itemId": "region_pack",
        "name": "Region model",
        "detail": "Region model is missing. Colour-only search is a separate fallback.",
        "confirm": "Download the pinned region model.",
        "installable": True,
        "status": "missing",
    }
    monkeypatch.setattr("semblon.preflight.capability_rows", lambda **_kwargs: [missing])
    monkeypatch.setattr(
        "semblon.preflight.install_item",
        lambda item_id, **_kwargs: {
            "id": item_id,
            "status": "failed",
            "ready": False,
            "skipped": False,
            "error": "disk full",
        },
    )
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )
        bridge.setMode("advanced")
        bridge.toggleSettings()
        assert bridge.preflightRows[0]["id"] == "region_pack"
        bridge.installPreflight("region_pack")
        deadline = __import__("time").time() + 3
        while __import__("time").time() < deadline:
            app.processEvents()
            thread = bridge._preflight_thread
            if thread is None or not thread.isRunning():
                break
            __import__("time").sleep(0.02)
        app.processEvents()
        assert "disk full" in bridge.noticeText
        assert bridge.noticeText.startswith("Setup:")
        assert "Installed and verified" not in bridge.noticeText
        assert bridge.preflightRows[0]["status"] == "missing"
        from semblon.native_shell.presentation import present_message

        shown = present_message("primary", "Setup: disk full.")
        assert shown == "Setup: disk full."
        assert "couldn't complete that step" not in shown
    finally:
        shutdown_shell(engine)


def test_probe_error_is_visible_and_other_checks_continue():
    from semblon.preflight import collect_rows

    def boom():
        raise RuntimeError("region probe exploded")

    rows = {row["id"]: row for row in collect_rows(**_kw(probes=_probes(region=boom)))}
    assert rows["region_pack"]["status"] == "failed"
    assert rows["region_pack"]["installable"] is False
    assert "region probe exploded" in rows["region_pack"]["detail"]
    assert rows["object_pack"]["status"] == "missing"
    assert rows["face_pack"]["status"] == "missing"


def test_unreadable_requirements_and_metadata_are_failed_rows(monkeypatch):
    from semblon.preflight import collect_rows

    def boom(_path):
        raise OSError("permission denied")

    monkeypatch.setattr("semblon.preflight._read", boom)
    rows = collect_rows(python_version=(3, 12), installed={}, venv=True, probes={})
    by_id = {row["id"]: row for row in rows}
    assert by_id["pins:requirements.txt"]["status"] == "failed"
    assert by_id["pins:requirements.txt"]["required"] is True
    assert "permission denied" in by_id["pins:requirements.txt"]["detail"]
    assert "pkg:pillow" not in by_id

    def broken():
        raise RuntimeError("metadata corrupt")

    monkeypatch.setattr("semblon.preflight.installed_distributions", broken)
    rows = collect_rows(runtime_text=RUNTIME, dev_text=DEV, python_version=(3, 12), venv=True, probes={})
    assert rows[0]["id"] == "pkg:metadata"
    assert rows[0]["status"] == "failed"
    assert rows[0]["required"] is True
    assert "metadata corrupt" in rows[0]["detail"]
    assert all(row["id"] != "pkg:pillow" for row in rows)


def test_pip_failure_keeps_the_earlier_output(monkeypatch, tmp_path):
    from semblon.preflight import _default_pip_install

    monkeypatch.setattr("semblon.preflight.sys.prefix", str(tmp_path / "venv"))

    class Completed:
        returncode = 1
        stderr = "first cause\nsecond cause\n"
        stdout = ""

    monkeypatch.setattr("semblon.preflight.sys.prefix", "/managed")
    monkeypatch.setattr("semblon.preflight.sys.base_prefix", "/base")
    monkeypatch.setattr("semblon.preflight.subprocess.run", lambda *_args, **_kwargs: Completed())
    try:
        _default_pip_install("pillow==13.0.0")
    except RuntimeError as exc:
        text = str(exc)
    else:
        raise AssertionError("pip failure was not reported")
    assert "first cause" in text
    assert "second cause" in text


def test_pip_install_refuses_system_python(monkeypatch):
    from semblon.preflight import _default_pip_install

    def boom(*_args, **_kwargs):
        raise AssertionError("pip must not run against system Python")

    monkeypatch.setattr("semblon.preflight.sys.prefix", "/same")
    monkeypatch.setattr("semblon.preflight.sys.base_prefix", "/same")
    monkeypatch.setattr("semblon.preflight.subprocess.run", boom)
    try:
        _default_pip_install("pillow==13.0.0")
    except RuntimeError as exc:
        text = str(exc)
    else:
        raise AssertionError("system Python was not refused")
    assert text == "refusing to change system Python"


def test_opencv_load_failure_includes_the_exception_text(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("opencv_geometry500.dll missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from semblon.preflight import default_probes

    loaded, _version, error = default_probes()["opencv_load"]()
    assert loaded is False
    assert "opencv_geometry500.dll missing" in error


def test_pytest_hook_prints_the_reason(monkeypatch, capsys):
    monkeypatch.delenv("SEMBLON_PREFLIGHT", raising=False)

    def gaps():
        return [
            {
                "id": "pkg:pillow",
                "detail": "Found pillow 12.3.0. The pin requires 13.0.0.",
                "status": "incompatible",
            }
        ]

    monkeypatch.setattr("semblon.preflight.required_gaps", gaps)
    from tests.conftest import pytest_sessionstart

    pytest_sessionstart(None)
    err = capsys.readouterr().err
    assert "pkg:pillow" in err
    assert "12.3.0" in err

    def broken():
        raise OSError("requirements.txt missing")

    monkeypatch.setattr("semblon.preflight.required_gaps", broken)
    pytest_sessionstart(None)
    err = capsys.readouterr().err
    assert "requirements.txt missing" in err
