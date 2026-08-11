"""Stable API facade. Re-exports the Engine so callers can depend on
``epistemos.api`` regardless of internal module movement (mission §19)."""

from __future__ import annotations

from ..core import Engine, EngineLimits
from ..identity import Principal

__all__ = ["Engine", "EngineLimits", "Principal"]
