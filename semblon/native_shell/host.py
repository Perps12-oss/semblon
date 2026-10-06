"""Load the Qt Quick archive shell. Widgets stay out of the composition."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from semblon.application import Application
from semblon.native_shell.bridge import ShellBridge
from semblon.native_shell.images import ArchiveImageProvider
from semblon.native_shell.model import ArchiveModel
from semblon.process import default_store_path

QML = Path(__file__).resolve().parent / "qml" / "Shell.qml"


def build_shell(store: Path | None = None, app: QApplication | None = None):
    """Return (qapp, engine). Root object is the archive window."""
    qapp = app or QApplication.instance() or QApplication([])
    qapp.setApplicationName("Semblon")
    qapp.setOrganizationName("Semblon")
    QQuickStyle.setStyle("Basic")
    path = Path(store) if store is not None else default_store_path()
    jobs = Application(path)
    model = ArchiveModel(jobs)
    bridge = ShellBridge(model, jobs)
    engine = QQmlApplicationEngine()
    engine.addImageProvider("archive", ArchiveImageProvider(bridge.path_for))
    engine.rootContext().setContextProperty("shell", bridge)
    engine.rootContext().setContextProperty("archiveModel", model)
    engine.rootContext().setContextProperty("similarModel", bridge.similar_model)
    engine.rootContext().setContextProperty("peopleModel", bridge.people_model)
    engine.load(QUrl.fromLocalFile(str(QML)))
    if not engine.rootObjects():
        raise RuntimeError(f"archive shell failed to load {QML}")
    # Keep Python owners alive for the engine's lifetime.
    engine._semblon_bridge = bridge  # type: ignore[attr-defined]
    engine._semblon_model = model  # type: ignore[attr-defined]
    engine._semblon_similar = bridge.similar_model  # type: ignore[attr-defined]
    engine._semblon_people = bridge.people_model  # type: ignore[attr-defined]
    engine._semblon_session = jobs.archive  # type: ignore[attr-defined]
    return qapp, engine
