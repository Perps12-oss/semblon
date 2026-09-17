"""S8 toolkit spike: PySide6 + Qt Quick. Not product GUI.

Does not import ingest/cluster/identify. Does not mutate the store.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SPIKE = Path(__file__).resolve().parent
if str(SPIKE) not in sys.path:
    sys.path.insert(0, str(SPIKE))
ROOT = SPIKE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QColor, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow

    from bridge import ShellBridge, load_spike_snapshot
    from theme import Theme
    from windows.backdrop import WindowsBackdropAdapter

    p = argparse.ArgumentParser(prog="s8-toolkit-spike")
    p.add_argument("--store", type=Path, default=None)
    p.add_argument("--run", default=None)
    p.add_argument("--prefer", choices=("mica", "acrylic"), default="mica")
    args = p.parse_args(argv)

    QQuickWindow.setDefaultAlphaBuffer(True)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Semblon")

    theme = Theme()
    bridge = ShellBridge(load_spike_snapshot(args.store, args.run))
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(SPIKE / "qml"))
    engine.rootContext().setContextProperty("theme", theme)
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(SPIKE / "qml" / "main.qml")))
    if not engine.rootObjects():
        print("s8-toolkit-spike: failed to load QML", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    window.setColor(QColor(0, 0, 0, 0))
    hwnd = int(window.winId())
    material = WindowsBackdropAdapter().apply(hwnd, prefer=args.prefer)
    theme.set_material(material)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
