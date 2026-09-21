"""R3 frames package — test-asset catalog only (no GUI required).

Gate: ``hierarchy_frames`` / ``SEMBLON_GATE_HIERARCHY_FRAMES``.
See ``docs/R3-FRAMES.md`` and ``docs/R3-BRIEF.md`` §7–§8.
"""

from __future__ import annotations

from .catalog import FRAME_SETS, generate_catalog

__all__ = [
    "FRAME_SETS",
    "generate_catalog",
]
