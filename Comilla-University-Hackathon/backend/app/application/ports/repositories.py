"""Ports: storage the use cases need (SRS 6.2). Implemented with SQLAlchemy later."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.application.ports.clustering import Cluster
from app.domain.entities import Answer, Checklist, Citation, Message, QuestionLog
from app.domain.value_objects import AnswerStatus, PhoneNumber


@dataclass(frozen=True)
class ChecklistRecord:
    """A saved checklist, as shown on the History page."""

    checklist: Checklist
    citations: tuple[Citation, ...]
    sms_sent: bool
    call_sid: str | None
    created_at: datetime
    id: str | None = None  # set by the repository; the app uses it to delete one checklist


OTHER_SERVICE = "other"  # the router label for questions outside the 8 services


@dataclass(frozen=True)
class QuestionStats:
    """Counts over all logged questions, for the admin dashboard (FR-ADM-01, SRS 3.4)."""

    total: int
    by_status: Mapping[str, int]  # AnswerStatus value -> count
    by_service: Mapping[str, int]  # service id -> count; questions without a service count as "other"
    by_channel: Mapping[str, int]  # Channel value -> count
    avg_latency_ms: float  # over questions that got a reply (every status except "error"); 0 if none


@runtime_checkable
class ConversationRepo(Protocol):
    def get_or_create(self, phone: PhoneNumber) -> str:
        """Returns the conversation id for this phone."""
        ...

    def add_message(self, conversation_id: str, message: Message, call_sid: str | None = None) -> None: ...

    def recent_messages(self, phone: PhoneNumber, limit: int) -> list[Message]:
        """Oldest first."""
        ...

    def delete_for_phone(self, phone: PhoneNumber) -> bool: ...


@runtime_checkable
class ChecklistRepo(Protocol):
    def save(
        self,
        phone: PhoneNumber,
        checklist: Checklist,
        citations: Sequence[Citation],
        sms_sent: bool,
        call_sid: str | None = None,
    ) -> None: ...

    def sms_already_sent(self, call_sid: str, service_id: str) -> bool:
        """FR-SMS-02: at most one SMS per service per call."""
        ...

    def list_for_phone(self, phone: PhoneNumber, limit: int) -> list[ChecklistRecord]:
        """Newest first."""
        ...

    def delete_for_phone(self, phone: PhoneNumber) -> int:
        """NFR-PRIV-03: removes this phone's checklists; returns how many."""
        ...

    def delete_one(self, phone: PhoneNumber, checklist_id: str) -> bool:
        """NFR-PRIV-03: removes one checklist of this phone. False if there is none with that id
        for this phone (another number's checklist is never touched)."""
        ...


@runtime_checkable
class QuestionLogRepo(Protocol):
    def add(self, log: QuestionLog) -> None: ...

    def list_recent(self, status: AnswerStatus | None, limit: int) -> list[QuestionLog]:
        """Newest first; `status=None` means all."""
        ...

    def texts_for_clustering(self) -> list[tuple[int, str]]:
        """(log id, question text) for every logged question."""
        ...

    def set_cluster_ids(self, assignments: Mapping[int, int]) -> None:
        """log id -> cluster id."""
        ...

    def stats(self) -> QuestionStats:
        """Totals for the admin dashboard, computed in the database (FR-ADM-01)."""
        ...

    def delete_demo(self) -> int:
        """Removes the sample rows written by scripts/seed_demo_data.py (is_demo=True); returns how many."""
        ...


@runtime_checkable
class CallRepo(Protocol):
    def record_start(self, call_sid: str, phone: PhoneNumber, direction: str) -> None:
        """Idempotent: Twilio may send the same webhook twice; a known call is left unchanged."""
        ...

    def record_turn(self, call_sid: str) -> int:
        """Adds one turn and returns the new total (FR-CALL-06). Raises NotFound for an unknown call."""
        ...

    def record_end(self, call_sid: str) -> None:
        """Sets the end time. An unknown call is ignored (status callbacks can arrive late)."""
        ...

    def last_outbound_at(self, phone: PhoneNumber) -> datetime | None:
        """For the call-back rate limit (FR-CALL-07)."""
        ...

    def count_since(self, since: datetime) -> int:
        """For the "calls today" KPI."""
        ...


@runtime_checkable
class ClusterRepo(Protocol):
    def replace_all(self, clusters: Sequence[Cluster]) -> list[int]:
        """Deletes old clusters, stores these, returns their new ids (same order)."""
        ...

    def list_all(self) -> list[Cluster]: ...


@runtime_checkable
class AnswerCache(Protocol):
    def get(self, key: str) -> Answer | None: ...

    def set(self, key: str, answer: Answer) -> None: ...
