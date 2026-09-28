"""Provider-neutral visual regions.

Discovery writes VisualRegion observations. Hover only reads a derived
primary-owner map. Identity stays on faces / decisions / persons.
"""

from semblon.visual.engine import analyse, capabilities
from semblon.visual.hover import HoverIndex
from semblon.visual.model import VisualConfig, VisualRegion

__all__ = ["HoverIndex", "VisualConfig", "VisualRegion", "analyse", "capabilities"]
