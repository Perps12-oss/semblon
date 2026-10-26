"""Keep PySide6 signal emits from dropping a reference to True.

On PySide6 6.12.0 and Python 3.11, ``SignalInstance.emit`` releases one
reference to the ``True`` singleton on every call. The argument does not
matter, and ``False`` is not affected. QML-originated signals do not do
this. After enough Python emits, interpreter shutdown reaches
``bool_dealloc`` and aborts.

The guard puts that reference back. A one-shot probe leaves the binding
alone when the drop is gone, so a fixed PySide does not leak.
"""

from __future__ import annotations

import ctypes
import sys

_wrapped: bool | None = None


def install_signal_emit_guard() -> bool:
    """Install the emit guard if this PySide still drops ``True``.

    Returns True when the guard wrapped ``emit``. Safe to call more than once.
    """
    global _wrapped
    if _wrapped is not None:
        return _wrapped

    from PySide6.QtCore import QObject, Signal, SignalInstance

    inc = ctypes.pythonapi.Py_IncRef
    dec = ctypes.pythonapi.Py_DecRef
    inc.argtypes = [ctypes.py_object]
    inc.restype = None
    dec.argtypes = [ctypes.py_object]
    dec.restype = None

    class _Probe(QObject):
        ping = Signal(int)

    probe = _Probe()
    original = SignalInstance.emit
    inc(True)
    before = sys.getrefcount(True)
    original(probe.ping, 0)
    steals = sys.getrefcount(True) < before
    if not steals:
        dec(True)
        _wrapped = False
        return False

    def emit(self, *args, **kwargs):
        inc(True)
        return original(self, *args, **kwargs)

    SignalInstance.emit = emit
    _wrapped = True
    return True
