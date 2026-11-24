"""HTTP request/response models (SRS 8). Only the interfaces layer uses pydantic."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.application.dto import AskResult, HistoryResult
from app.application.ports.repositories import ChecklistRecord
from app.domain.entities import Answer, Checklist, Citation, Conflict, Message, Service, SituationProfile

QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ServiceOut(BaseModel):
    id: str
    name_bn: str
    name_en: str
    office_bn: str
    sms_name: str

    @classmethod
    def of(cls, s: Service) -> "ServiceOut":
        return cls(id=s.id, name_bn=s.name_bn, name_en=s.name_en, office_bn=s.office_bn, sms_name=s.sms_name)


class ServiceBrief(BaseModel):
    id: str
    name_bn: str
    name_en: str


class ChecklistOut(BaseModel):
    who: str
    papers: list[str]
    fee: str
    where: str
    decision: str

    @classmethod
    def of(cls, c: Checklist) -> "ChecklistOut":
        return cls(who=c.who, papers=list(c.papers), fee=c.fee, where=c.where, decision=c.decision)


class ServiceChecklistOut(ChecklistOut):
    service_id: str

    @classmethod
    def of(cls, c: Checklist) -> "ServiceChecklistOut":  # type: ignore[override]
        return cls(
            service_id=c.service_id, who=c.who, papers=list(c.papers), fee=c.fee, where=c.where,
            decision=c.decision,
        )  # fmt: skip


class SituationOut(BaseModel):
    summary_bn: str
    facts: dict[str, str]

    @classmethod
    def of(cls, s: SituationProfile) -> "SituationOut":
        return cls(summary_bn=s.summary_bn, facts=dict(s.facts))


class ConflictSideOut(BaseModel):
    service_id: str
    rule_bn: str
    source_title: str
    source_url: str


class ConflictOut(BaseModel):
    topic_bn: str
    sides: list[ConflictSideOut]

    @classmethod
    def of(cls, c: Conflict) -> "ConflictOut":
        return cls(
            topic_bn=c.topic_bn,
            sides=[
                ConflictSideOut(
                    service_id=s.service_id,
                    rule_bn=s.rule_bn,
                    source_title=s.source_title,
                    source_url=s.source_url,
                )  # fmt: skip
                for s in c.sides
            ],
        )


class CitationOut(BaseModel):
    title: str
    source_url: str
    snippet: str
    chunk_id: str

    @classmethod
    def of(cls, c: Citation) -> "CitationOut":
        return cls(title=c.title, source_url=c.source_url, snippet=c.snippet, chunk_id=c.chunk_id)


# ------------------------------------------------------------------ chat


class ChatRequest(BaseModel):
    phone: str
    message: QuestionText
    channel: Literal["app"] = "app"  # voice turns come through /voice/*

    model_config = {"json_schema_extra": {"examples": [{"phone": "01712345678", "message": "বয়স্ক ভাতা"}]}}


class ChatResponse(BaseModel):
    conversation_id: str
    status: str
    service: ServiceBrief | None
    confidence: float
    router: str | None
    speech_text: str
    display_text: str
    checklist: ChecklistOut | None
    citations: list[CitationOut]
    follow_up_question: str | None
    latency_ms: int
    # Sprint additions (FR-AGT-19 to 22, FR-APP-11). Additive: old clients ignore them.
    mode: str = "single"
    situation: SituationOut | None = None
    services: list[ServiceBrief] = []
    checklists: list[ServiceChecklistOut] = []
    conflicts: list[ConflictOut] = []

    @classmethod
    def of(cls, r: AskResult) -> "ChatResponse":
        a = r.answer
        return cls(
            conversation_id=r.conversation_id,
            status=a.status.value,
            service=ServiceBrief(id=r.service.id, name_bn=r.service.name_bn, name_en=r.service.name_en)
            if r.service
            else None,
            confidence=a.confidence,
            router=a.router_source.value if a.router_source else None,
            speech_text=a.speech_text,
            display_text=a.display_text,
            checklist=ChecklistOut.of(a.checklist) if a.checklist else None,
            citations=[CitationOut.of(c) for c in a.citations],
            follow_up_question=a.follow_up_question,
            latency_ms=r.latency_ms,
            mode=a.mode,
            situation=SituationOut.of(a.situation) if a.situation else None,
            services=[ServiceBrief(id=x.id, name_bn=x.name_bn, name_en=x.name_en) for x in _services_of(r)],
            checklists=[ServiceChecklistOut.of(c) for c in _checklists_of(a)],
            conflicts=[ConflictOut.of(c) for c in a.conflicts],
        )


def _checklists_of(a: Answer) -> tuple[Checklist, ...]:
    if a.checklists:
        return a.checklists
    return (a.checklist,) if a.checklist else ()


def _services_of(r: AskResult) -> tuple[Service, ...]:
    """Every service of the answer, primary first (old results: just the primary)."""
    if r.services:
        return r.services
    return (r.service,) if r.service else ()


# ------------------------------------------------------------------ history


class MessageOut(BaseModel):
    role: str
    channel: str
    text: str
    service_id: str | None
    status: str | None
    created_at: datetime

    @classmethod
    def of(cls, m: Message) -> "MessageOut":
        return cls(
            role=m.role.value, channel=m.channel.value, text=m.text, service_id=m.service_id,
            status=m.status.value if m.status else None, created_at=m.created_at,
        )  # fmt: skip


class ChecklistRecordOut(BaseModel):
    id: str | None = None  # for DELETE /api/v1/conversations/{phone}/checklists/{id}
    service_id: str
    checklist: ChecklistOut
    citations: list[CitationOut]
    sms_sent: bool
    created_at: datetime

    @classmethod
    def of(cls, r: ChecklistRecord) -> "ChecklistRecordOut":
        return cls(
            id=r.id, service_id=r.checklist.service_id, checklist=ChecklistOut.of(r.checklist),
            citations=[CitationOut.of(c) for c in r.citations], sms_sent=r.sms_sent, created_at=r.created_at,
        )  # fmt: skip


class HistoryResponse(BaseModel):
    phone: str
    messages: list[MessageOut]
    checklists: list[ChecklistRecordOut]

    @classmethod
    def of(cls, h: HistoryResult) -> "HistoryResponse":
        return cls(
            phone=h.phone,
            messages=[MessageOut.of(m) for m in h.messages],
            checklists=[ChecklistRecordOut.of(r) for r in h.checklists],
        )


class DeleteResponse(BaseModel):
    deleted: bool
