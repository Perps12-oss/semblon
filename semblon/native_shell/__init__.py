"""Qt Quick archive shell (`semblon shell`).

Forward product UI. One archive, viewed through a lens (Time by default).
Client of Application. Does not import FaceKit, Tk, or call process_folder.
"""

from __future__ import annotations

from semblon.native_shell.run import run_native_shell

__all__ = ["run_native_shell"]
