"""Port: the agent that turns a question into a checked answer (SRS 7.4)."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.domain.entities import Answer, Message
from app.domain.value_objects import Channel


@runtime_checkable
class AnswerEngine(Protocol):
    def answer(self, question: str, history: Sequence[Message], channel: Channel) -> Answer:
        """`history` is oldest first and includes status/service_id (for follow-ups, FR-AGT-17)."""
        ...
