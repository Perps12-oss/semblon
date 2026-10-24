"""Grab the production shell for the Safelight Desk review.

Run under xvfb so the window is a real framebuffer:

    xvfb-run -a -s "-screen 0 1600x1000x24" .venv/bin/python tools/capture_ux_screens.py OUT_DIR
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from semblon.native_shell.host import build_shell, shutdown_shell
from semblon.store import connect, init_db


def _pump(app: QApplication, ms: int = 400) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _save(window, path: Path) -> None:
    image = window.grabWindow()
    path.parent.mkdir(parents=True, exist_ok=True)
    if image.isNull() or not image.save(str(path)):
        raise RuntimeError(f"could not save {path}")
    print(f"wrote {path} {image.width()}x{image.height()}")


def _seed(store: Path, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    photo = folder / "harbour.png"
    image = QImage(640, 420, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkCyan)
    painter_ok = image.save(str(photo))
    if not painter_ok:
        raise RuntimeError("could not write sample photo")
    conn = connect(store)
    try:
        init_db(conn)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("harbour", "folder", str(photo), "hharbour", 640, 420, time.time_ns(), photo.stat().st_size),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/cursor/artifacts/screenshots")
    work = Path("/tmp/semblon-ux-capture")
    work.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])

    empty_store = work / "empty.sqlite"
    _app, engine = build_shell(empty_store, app=app)
    window = engine.rootObjects()[0]
    window.setWidth(1440)
    window.setHeight(900)
    window.show()
    _pump(app, 700)
    _save(window, out / "01-first-run.png")
    bridge = engine._semblon_bridge
    bridge._surface_state = "error"
    bridge._notice = "That folder could not be read. Choose another folder and try again."
    bridge.surfaceChanged.emit()
    _pump(app, 300)
    _save(window, out / "04-error.png")
    shutdown_shell(engine)
    del engine

    library = work / "library"
    store = library / "s.sqlite"
    _seed(store, library / "pictures")
    _app, engine = build_shell(store, app=app)
    window = engine.rootObjects()[0]
    window.setWidth(1440)
    window.setHeight(900)
    window.show()
    bridge = engine._semblon_bridge
    _pump(app, 500)
    _save(window, out / "02-home-with-pictures.png")
    bridge.showLibrary()
    _pump(app, 600)
    _save(window, out / "03-library.png")
    bridge.openPeople()
    _pump(app, 400)
    _save(window, out / "05-people-empty.png")
    shutdown_shell(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
