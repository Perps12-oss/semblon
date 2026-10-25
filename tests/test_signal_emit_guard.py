"""Interpreter shutdown stays clean after a lot of Python signal emits.

PySide 6.12's SignalInstance.emit drops one reference to True per call.
The failure mode is not a failed assertion: the process aborts in
bool_dealloc while the interpreter is finalising. This runs in a child
so a regression fails the test instead of taking the suite down with it.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap


_SCRIPT = textwrap.dedent(
    """
    import os
    import sys

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.signal_guard import install_signal_emit_guard

    app = QApplication([])
    wrapped = install_signal_emit_guard()

    class E(QObject):
        flag = Signal(bool)
        bare = Signal()

    box = E()
    # More emits than True's refcount. Unguarded, this aborts before the print.
    bursts = sys.getrefcount(True) + 400
    before = sys.getrefcount(True)
    for i in range(bursts):
        box.flag.emit(i % 2 == 0)
        box.bare.emit()
    after = sys.getrefcount(True)
    if after < before - 5:
        raise SystemExit(f"True refcount {before} -> {after} over {bursts} emits")
    print(f"stable {before} {after} wrapped={wrapped}")
    """
)


def test_signal_emits_shut_down_cleanly_three_times():
    for _ in range(3):
        done = subprocess.run(
            [sys.executable, "-c", _SCRIPT],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-1500:] + done.stdout[-500:]
        assert "stable" in done.stdout


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]
