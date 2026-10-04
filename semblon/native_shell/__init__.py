"""Qt Quick archive shell (`semblon shell`).

One archive, viewed through a lens, drawn as a field, entered as focus.
Optional client of Application. Not the product Home (`semblon home`).
Does not import FaceKit or call process_folder directly.
"""

from __future__ import annotations

from semblon.native_shell.run import run_native_shell

__all__ = ["run_native_shell"]
