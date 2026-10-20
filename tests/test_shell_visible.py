"""Visible Windows pass for the PySide6 archive shell.

Skipped unless SEMBLON_VISIBLE_SHELL=1. Offscreen Qt is not this test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SEMBLON_VISIBLE_SHELL") != "1",
    reason="set SEMBLON_VISIBLE_SHELL=1 to launch a real window",
)


def test_visible_windows_shell_exercises_exposed_controls(tmp_path, monkeypatch):
    if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
        monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    import ctypes
    import threading
    import time

    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog

    from semblon.native_shell.host import build_shell
    from semblon.store import connect, init_db
    from semblon.user_region import persist_user_region

    store = tmp_path / "store.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "emulated"),
    )
    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"not-a-real-jpeg")
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "aaa", 200, 100, 1, 1),
    )
    conn.commit()
    conn.close()
    region = persist_user_region(store, media_id="m1", x=10, y=10, w=40, h=20, run_id="r1")
    pack = tmp_path / "pack.json"
    pack.write_text('{"entries":[{"kind":"landmark","match":{"label":"pier"},"label":"Pier"}]}', encoding="utf-8")
    source = tmp_path / "model.bin"
    source.write_bytes(b"weights")
    dest = tmp_path / "installed.bin"
    folder = tmp_path / "photos"
    folder.mkdir()

    seen = {}
    started = threading.Event()

    def fake_process(path, **kwargs):
        seen["reprocess"] = kwargs.get("reprocess")
        started.set()
        return {"run_id": "r", "out": None}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(pack), "JSON (*.json)"),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(dest), "All files (*.*)"),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(folder),
    )

    app = QApplication.instance() or QApplication([])
    _qapp, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    bridge._last_folder = folder
    root.show()
    root.raise_()
    root.requestActivate()
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    platform = QGuiApplication.platformName()
    hwnd = int(root.winId())
    visible = bool(ctypes.windll.user32.IsWindowVisible(hwnd))
    log = [
        f"platform={platform}",
        f"title={root.title()}",
        f"hwnd_visible={visible}",
        f"width={root.width()}",
        f"height={root.height()}",
    ]
    grab = root.grabWindow()
    shot = tmp_path / "shell-visible.png"
    grab.save(str(shot))
    log.append(f"grab_null={grab.isNull()} grab={grab.width()}x{grab.height()} file={shot.is_file()}")
    assert platform == "windows", "visible pass requires the Windows platform plugin, got " + platform
    assert visible, "the shell window was not visible to Windows"
    assert not grab.isNull() and grab.width() > 0

    def find_visual(name: str):
        stack = [root.contentItem()]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            if item.objectName() == name:
                return item
            stack.extend(item.childItems())
        return None

    def click(name: str) -> None:
        app.processEvents()
        item = find_visual(name)
        assert item is not None, name
        assert item.isVisible(), name
        point = item.mapToScene(QPointF(max(1, item.width() / 2), max(1, item.height() / 2)))
        QTest.mouseClick(
            root,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(int(point.x()), int(point.y())),
        )
        app.processEvents()

    click("settingsButton")
    assert root.findChild(QQuickItem, "settingsSheet").isVisible()
    for name in (
        "setting_cycleDensity",
        "setting_libraryHealth",
        "setting_showActivity",
        "setting_modeText",
        "setting_rescan",
    ):
        click(name)
        log.append(f"click {name} notice={bridge.noticeText!r} state={bridge.surfaceState}")
    assert started.wait(3)
    assert seen.get("reprocess") is True
    bridge.setMode("advanced")
    for _ in range(8):
        app.processEvents()
        time.sleep(0.05)
    for name in (
        "setting_namedItems",
        "setting_scanDuplicates",
        "setting_showCapabilities",
        "setting_gpuOff",
        "setting_knowledgePack",
        "setting_installModel",
    ):
        click(name)
        log.append(
            f"click {name} notice={bridge.noticeText!r} named_open={bridge.namedItemsOpen} focus={bridge.focusId!r}"
        )
    field = root.findChild(QQuickItem, "namedItemField")
    if field is None or not field.isVisible():
        report = tmp_path / "visible-log.txt"
        report.write_text("\n".join(log), encoding="utf-8")
        print("\n".join(log))
    assert field is not None and field.isVisible()
    click("namedItemRow")
    field.setProperty("text", "old camera")
    click("nameNamedItem")
    log.append(f"named notice={bridge.noticeText!r}")
    assert "old camera" in bridge.noticeText
    bridge.closeNamedItems()
    app.processEvents()
    click("sidebarMoments")
    log.append(f"moments notice={bridge.noticeText!r} facet={bridge.facet}")
    assert bridge.facet == "moments"
    day_label = "1970-01-01"
    month = root.findChild(QQuickItem, f"timelineMonth_{day_label[:7]}")
    if month is not None and month.isVisible():
        click(f"timelineMonth_{day_label[:7]}")
        log.append(f"month notice={bridge.noticeText!r} scope={bridge.scopeKind}:{bridge.scopeLabel}")
        assert bridge.scopeKind == "month"
    else:
        bridge.selectDay(day_label)
        log.append(f"day notice={bridge.noticeText!r} scope={bridge.scopeKind}:{bridge.scopeLabel}")
        assert bridge.scopeKind == "day"
    click(f"sidebarFolder_{photo.parent.name}")
    log.append(f"folder notice={bridge.noticeText!r} scope={bridge.scopeKind}:{bridge.scopeLabel}")
    assert bridge.scopeKind == "folder"
    click("peopleButton")
    app.processEvents()
    assert root.findChild(QQuickItem, "peopleDesk").isVisible()
    log.append(f"people review={bridge.reviewCountText!r} unresolved={bridge.unresolvedText!r}")
    bridge.closePeople()
    bridge.setMode("primary")
    app.processEvents()
    bridge.openFocus("m1")
    app.processEvents()
    click("similarAction")
    log.append(f"similar state={bridge.similarState} note={bridge.similarNote!r}")
    click("focusMoreButton")
    click("askPhoto")
    log.append(f"ask notice={bridge.resultText!r}")
    before = store.read_bytes()
    bridge.escape()
    app.processEvents()
    if not bridge.settingsOpen:
        click("settingsButton")
    click("setting_resetDefaults")
    log.append(f"reset notice={bridge.noticeText!r} store_same={store.read_bytes()==before}")
    assert store.read_bytes() == before
    shot2 = tmp_path / "shell-after.png"
    root.grabWindow().save(str(shot2))
    log.append(f"after_shot={shot2.is_file()}")
    report = tmp_path / "visible-log.txt"
    report.write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))
    root.close()
