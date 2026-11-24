"""Use case: the list of services (GET /api/v1/services)."""

from collections.abc import Sequence

from app.domain.entities import Service


class ListServices:
    def __init__(self, services: Sequence[Service]) -> None:
        self._services = list(services)

    def execute(self) -> list[Service]:
        return list(self._services)
