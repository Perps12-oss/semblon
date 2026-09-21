"""R3 toolkit bake-off harness scaffold (code-ahead; gate default OFF).

Measure against docs/R3-BRIEF.md §6 before choosing WinUI / Qt / other.
Does not wire into product defaults or semblon.cli.
"""

from __future__ import annotations

from .criteria import CRITERIA, REJECTED_TOOLKITS, criterion_ids
from .harness import run_bakeoff

__all__ = [
    "CRITERIA",
    "REJECTED_TOOLKITS",
    "criterion_ids",
    "run_bakeoff",
]
