"""Ports: turn text into vectors and find official passages (FR-AGT-05, FR-DATA-03)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Passage:
    """One chunk of an official document, as returned by a search."""

    chunk_id: str
    service_id: str
    title: str
    source_url: str
    text: str
    score: float


@runtime_checkable
class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...


@runtime_checkable
class Retriever(Protocol):
    def search(self, query: str, service_id: str | None, k: int) -> list[Passage]:
        """Top-k passages, best first. `service_id=None` searches all services."""
        ...
