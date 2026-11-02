"""Load the Qt Quick archive shell. Widgets stay out of the composition."""

from __future__ import annotations

import os
from pathlib import Path

# Env style must be set before any Qt Quick Controls registration (Linux CI).
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from semblon.application import Application
from semblon.native_shell.bridge import ShellBridge
from semblon.native_shell.images import (
    ArchiveImageProvider,
    FaceCropImageProvider,
    thumb_cache_dir,
)
from semblon.native_shell.model import ArchiveModel
from semblon.process import default_store_path

QML = Path(__file__).resolve().parent / "qml" / "Table.qml"
FONT_DIR = Path(__file__).resolve().parent / "fonts"


def load_bundled_fonts() -> list[str]:
    """Register Fraunces and Inter from the package so Windows never substitutes them."""
    from PySide6.QtGui import QFontDatabase

    families: list[str] = []
    for font in sorted(FONT_DIR.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


def _ensure_quick_style() -> None:
    """Basic style before Controls QML loads. Safe to call more than once."""
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    try:
        QQuickStyle.setStyle("Basic")
    except RuntimeError:
        # Already registered after a prior load in this process; env covers new engines.
        pass


def build_shell(store: Path | None = None, app: QApplication | None = None):
    """Return (qapp, engine). Root object is the archive window."""
    from semblon.engine import assert_single_opencv

    assert_single_opencv()
    _ensure_quick_style()
    qapp = app or QApplication.instance() or QApplication([])
    qapp.setApplicationName("Semblon")
    qapp.setOrganizationName("Semblon")
    load_bundled_fonts()
    _ensure_quick_style()
    path = Path(store) if store is not None else default_store_path()
    jobs = Application(path)
    model = ArchiveModel(jobs)
    bridge = ShellBridge(model, jobs)
    bridge.setParent(qapp)
    engine = QQmlApplicationEngine()
    # Explicit import path so Windows file:// loads still resolve qmldir singles.
    engine.addImportPath(str(QML.parent))
    engine.addImageProvider("archive", ArchiveImageProvider(bridge.path_for, thumb_cache_dir(path)))
    engine.addImageProvider("face", FaceCropImageProvider(bridge.face_crop_spec))
    engine.rootContext().setContextProperty("shell", bridge)
    engine.rootContext().setContextProperty("archiveModel", model)
    engine.rootContext().setContextProperty("similarModel", bridge.similar_model)
    engine.rootContext().setContextProperty("peopleModel", bridge.people_model)
    qml_errors: list[str] = []

    def _on_warnings(errors) -> None:
        for err in errors:
            try:
                qml_errors.append(str(err.toString()))
            except Exception:
                qml_errors.append(str(err))

    engine.warnings.connect(_on_warnings)
    engine.load(QUrl.fromLocalFile(str(QML)))
    if not engine.rootObjects():
        detail = "; ".join(qml_errors) if qml_errors else "no QML errors reported"
        message = f"archive shell failed to load {QML}: {detail}"
        print(message, flush=True)
        raise RuntimeError(message)
    # Keep Python owners alive for the engine's lifetime.
    engine._semblon_bridge = bridge  # type: ignore[attr-defined]
    engine._semblon_model = model  # type: ignore[attr-defined]
    engine._semblon_similar = bridge.similar_model  # type: ignore[attr-defined]
    engine._semblon_people = bridge.people_model  # type: ignore[attr-defined]
    engine._semblon_session = jobs.archive  # type: ignore[attr-defined]
    return qapp, engine


def shutdown_shell(engine: QQmlApplicationEngine) -> None:
    """Tear the shell down on the GUI thread: stop the timer, then flush deferred deletes."""
    bridge = getattr(engine, "_semblon_bridge", None)
    if bridge is not None:
        bridge.shutdown()
    ctx = engine.rootContext()
    for name in ("shell", "archiveModel", "similarModel", "peopleModel"):
        ctx.setContextProperty(name, None)
    for root in list(engine.rootObjects()):
        root.deleteLater()
    engine._semblon_bridge = None  # type: ignore[attr-defined]
    engine._semblon_model = None  # type: ignore[attr-defined]
    engine._semblon_similar = None  # type: ignore[attr-defined]
    engine._semblon_people = None  # type: ignore[attr-defined]
    engine._semblon_session = None  # type: ignore[attr-defined]
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
