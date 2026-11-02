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
    # #region agent log
    try:
        import json as _json, time as _time
        open("/opt/cursor/logs/debug.log", "a").write(
            _json.dumps(
                {
                    "hypothesisId": "B",
                    "location": "host.py:build_shell:pre_load",
                    "message": "loading Table.qml",
                    "data": {
                        "qml": str(QML),
                        "pinnedDotCount": int(bridge.pinnedDotCount),
                        "lowInfoRecovery": bool(bridge.lowInfoRecovery),
                        "canEscalateWhole": bool(bridge.canEscalateWhole),
                        "selectionOnFocus": bool(bridge.selectionOnFocus),
                    },
                    "timestamp": int(_time.time() * 1000),
                }
            )
            + "\n"
        )
    except Exception:
        pass
    # #endregion
    engine.load(QUrl.fromLocalFile(str(QML)))
    if not engine.rootObjects():
        detail = "; ".join(qml_errors) if qml_errors else "no QML errors reported"
        message = f"archive shell failed to load {QML}: {detail}"
        print(message, flush=True)
        # #region agent log
        try:
            import json as _json, time as _time
            open("/opt/cursor/logs/debug.log", "a").write(
                _json.dumps(
                    {
                        "hypothesisId": "A",
                        "location": "host.py:build_shell:load_fail",
                        "message": "QML rootObjects empty",
                        "data": {"detail": detail, "qml_errors": list(qml_errors)},
                        "timestamp": int(_time.time() * 1000),
                    }
                )
                + "\n"
            )
        except Exception:
            pass
        # #endregion
        raise RuntimeError(message)
    # Keep Python owners alive for the engine's lifetime.
    engine._semblon_bridge = bridge  # type: ignore[attr-defined]
    engine._semblon_model = model  # type: ignore[attr-defined]
    engine._semblon_similar = bridge.similar_model  # type: ignore[attr-defined]
    engine._semblon_people = bridge.people_model  # type: ignore[attr-defined]
    engine._semblon_session = jobs.archive  # type: ignore[attr-defined]
    # #region agent log
    try:
        import json as _json, time as _time
        from PySide6.QtCore import QObject as _QObject

        _root = engine.rootObjects()[0]
        _viewer = _root.findChild(_QObject, "viewer")
        _handles = [
            n
            for n in (
                "selectionHandle_tl",
                "selectionHandle_t",
                "selectionHandle_tr",
                "selectionHandle_l",
                "selectionHandle_r",
                "selectionHandle_bl",
                "selectionHandle_b",
                "selectionHandle_br",
            )
            if _root.findChild(_QObject, n) is not None
        ]
        open("/opt/cursor/logs/debug.log", "a").write(
            _json.dumps(
                {
                    "hypothesisId": "A",
                    "location": "host.py:build_shell:post_load",
                    "message": "shell loaded",
                    "data": {
                        "roots": len(engine.rootObjects()),
                        "viewer": _viewer is not None,
                        "handles_at_start": _handles,
                        "qml_errors": list(qml_errors),
                        "runId": "post-fix",
                    },
                    "timestamp": int(_time.time() * 1000),
                }
            )
            + "\n"
        )
    except Exception:
        pass
    # #endregion
    return qapp, engine


def shutdown_shell(engine: QQmlApplicationEngine) -> None:
    """Tear the shell down on the GUI thread: stop the timer, then flush deferred deletes."""
    bridge = getattr(engine, "_semblon_bridge", None)
    if bridge is not None:
        bridge.shutdown()
    # #region agent log
    try:
        import json as _json, time as _time

        open("/opt/cursor/logs/debug.log", "a").write(
            _json.dumps(
                {
                    "hypothesisId": "B",
                    "location": "host.py:shutdown_shell:pre_null",
                    "message": "about to null context properties",
                    "data": {"had_bridge": bridge is not None},
                    "timestamp": int(_time.time() * 1000),
                }
            )
            + "\n"
        )
    except Exception:
        pass
    # #endregion
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
