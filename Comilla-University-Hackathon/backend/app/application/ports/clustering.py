"""Port: groups similar questions for the dashboard (FR-ADM-03, 04)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Cluster:
    label: str
    size: int
    examples: tuple[str, ...]
    id: int | None = None


@runtime_checkable
class Clusterer(Protocol):
    def cluster(self, vectors: Sequence[Sequence[float]]) -> list[int]:
        """Returns one cluster number per vector (same order)."""
        ...
