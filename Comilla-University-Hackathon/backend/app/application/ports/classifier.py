"""Port: decides which service a question is about (FR-AGT-01, 02)."""

from typing import Protocol, runtime_checkable

from app.domain.value_objects import RouterSource


@runtime_checkable
class ServiceClassifier(Protocol):
    @property
    def source(self) -> RouterSource:
        """Which router this is (recorded in logs and the API response)."""
        ...

    def classify(self, text: str) -> list[tuple[str, float]]:
        """Returns (label, score) for all labels, highest score first. Scores are 0 to 1."""
        ...
