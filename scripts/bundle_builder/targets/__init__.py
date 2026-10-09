"""Build targets registry."""

from .base import TargetBuilder
from .universal import UniversalTarget
from .workbuddy import WorkbuddyTarget

__all__ = ["TargetBuilder", "UniversalTarget", "WorkbuddyTarget"]
