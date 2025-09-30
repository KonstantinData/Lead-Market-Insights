"""Resource metadata container used by the stub implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

__all__ = ["Resource"]


@dataclass
class Resource:
    attributes: Dict[str, object]

    @classmethod
    def create(cls, attributes: Dict[str, object]) -> "Resource":
        return cls(dict(attributes))
