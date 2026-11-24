"""Results that use cases return to the interfaces layer."""

from dataclasses import dataclass

from app.application.ports.repositories import ChecklistRecord
from app.domain.entities import Answer, Message, Service


@dataclass(frozen=True)
class AskResult:
    conversation_id: str
    answer: Answer
    service: Service | None
    latency_ms: int
    # True when this answer queued the SMS checklist (voice, first answer about the service in the call).
    # The call then says SMS_SENT itself (FR-SMS-01); False for the app and for every later turn.
    sms_scheduled: bool = False
    # The services whose SMS was queued on this turn (two for a mixed answer, FR-AGT-21).
    sms_services: tuple[str, ...] = ()
    services: tuple[Service, ...] = ()  # every service of the answer, primary first

    @property
    def sms_count(self) -> int:
        return len(self.sms_services) if self.sms_services else int(self.sms_scheduled)


@dataclass(frozen=True)
class HistoryResult:
    phone: str
    messages: tuple[Message, ...]
    checklists: tuple[ChecklistRecord, ...]
