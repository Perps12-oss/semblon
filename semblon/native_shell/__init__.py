"""R3 native production shell (Qt/PySide).

Authorized path: SEM-ARCH-V1.4 §D.2 / §I.5 / r3-artifacts/07-shell-decision.md.
Talks only through semblon.application.Application (JobEngine door).
Does not import FaceKit, process_folder, or ingest. Tk Home remains the
compatibility frontend; tools/s8_toolkit_spike remains reference-only.
"""

from __future__ import annotations

from semblon.native_shell.run import run_native_shell

__all__ = ["run_native_shell"]
