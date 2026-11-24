"""SQLAlchemy implementations of the storage ports (application/ports/repositories.py).

Each method opens its own short session and commits, so callers never deal with sessions.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.ports.clustering import Cluster
from app.application.ports.repositories import OTHER_SERVICE, ChecklistRecord, QuestionStats
from app.domain.entities import Checklist, Citation, Message, QuestionLog
from app.domain.errors import NotFound
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role, RouterSource
from app.infrastructure.db.models import (
    CallRow,
    ChecklistRow,
    ClusterRow,
    ConversationRow,
    MessageRow,
    QuestionLogRow,
)
from app.infrastructure.db.serialization import (
    checklist_from_json,
    checklist_to_json,
    citations_from_json,
    citations_to_json,
)

SessionFactory = sessionmaker[Session]


class SqlConversationRepo:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    def get_or_create(self, phone: PhoneNumber) -> str:
        with self._sessions() as s:
            row = s.scalars(select(ConversationRow).where(ConversationRow.phone == phone.e164)).first()
            if row is None:
                row = ConversationRow(phone=phone.e164)
                s.add(row)
                s.commit()
            return row.id

    def add_message(self, conversation_id: str, message: Message, call_sid: str | None = None) -> None:
        with self._sessions() as s:
            s.add(
                MessageRow(
                    conversation_id=conversation_id,
                    role=message.role.value,
                    channel=message.channel.value,
                    text=message.text,
                    service_id=message.service_id,
                    status=message.status.value if message.status else None,
                    call_sid=call_sid,
                    created_at=message.created_at,
                )
            )
            conversation = s.get(ConversationRow, conversation_id)
            if conversation is not None:
                conversation.updated_at = datetime.now(UTC)
            s.commit()

    def recent_messages(self, phone: PhoneNumber, limit: int) -> list[Message]:
        if limit <= 0:
            return []
        with self._sessions() as s:
            rows = s.scalars(
                select(MessageRow)
                .join(ConversationRow, MessageRow.conversation_id == ConversationRow.id)
                .where(ConversationRow.phone == phone.e164)
                .order_by(MessageRow.id.desc())
                .limit(limit)
            ).all()
            return [_message(row) for row in reversed(rows)]  # oldest first

    def delete_for_phone(self, phone: PhoneNumber) -> bool:
        with self._sessions() as s:
            row = s.scalars(select(ConversationRow).where(ConversationRow.phone == phone.e164)).first()
            if row is None:
                return False
            s.delete(row)  # messages go too (ON DELETE CASCADE)
            s.commit()
            return True


class SqlChecklistRepo:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    def save(
        self,
        phone: PhoneNumber,
        checklist: Checklist,
        citations: Sequence[Citation],
        sms_sent: bool,
        call_sid: str | None = None,
    ) -> None:
        with self._sessions() as s:
            s.add(
                ChecklistRow(
                    phone=phone.e164,
                    service_id=checklist.service_id,
                    content_json=checklist_to_json(checklist),
                    citations_json=citations_to_json(citations),
                    sms_sent=sms_sent,
                    call_sid=call_sid,
                )
            )
            s.commit()

    def sms_already_sent(self, call_sid: str, service_id: str) -> bool:
        with self._sessions() as s:
            found = s.scalars(
                select(ChecklistRow.id).where(
                    ChecklistRow.call_sid == call_sid,
                    ChecklistRow.service_id == service_id,
                    ChecklistRow.sms_sent.is_(True),
                )
            ).first()
            return found is not None

    def list_for_phone(self, phone: PhoneNumber, limit: int) -> list[ChecklistRecord]:
        with self._sessions() as s:
            rows = s.scalars(
                select(ChecklistRow)
                .where(ChecklistRow.phone == phone.e164)
                .order_by(ChecklistRow.id.desc())
                .limit(limit)
            ).all()
            return [
                ChecklistRecord(
                    checklist=checklist_from_json(r.content_json),
                    citations=citations_from_json(r.citations_json),
                    sms_sent=r.sms_sent,
                    call_sid=r.call_sid,
                    created_at=r.created_at,
                    id=str(r.id),
                )
                for r in rows
            ]

    def delete_for_phone(self, phone: PhoneNumber) -> int:
        with self._sessions() as s:
            result = s.execute(delete(ChecklistRow).where(ChecklistRow.phone == phone.e164))
            s.commit()
            return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def delete_one(self, phone: PhoneNumber, checklist_id: str) -> bool:
        if not checklist_id.isdigit():
            return False
        with self._sessions() as s:
            result = s.execute(
                delete(ChecklistRow).where(
                    ChecklistRow.id == int(checklist_id), ChecklistRow.phone == phone.e164
                )
            )
            s.commit()
            return bool(result.rowcount)  # type: ignore[attr-defined]


class SqlQuestionLogRepo:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    def add(self, log: QuestionLog) -> None:
        with self._sessions() as s:
            s.add(
                QuestionLogRow(
                    phone_hash=log.phone_hash,
                    channel=log.channel.value,
                    text=log.text,
                    service_id=log.service_id,
                    confidence=log.confidence,
                    router_source=log.router_source.value if log.router_source else None,
                    status=log.status.value,
                    latency_ms=log.latency_ms,
                    llm_calls=log.llm_calls,
                    llm_backend=log.llm_backend,
                    cluster_id=log.cluster_id,
                    is_demo=log.is_demo,
                    created_at=log.created_at,
                )
            )
            s.commit()

    def list_recent(self, status: AnswerStatus | None, limit: int) -> list[QuestionLog]:
        with self._sessions() as s:
            query = select(QuestionLogRow)
            if status is not None:
                query = query.where(QuestionLogRow.status == status.value)
            query = query.order_by(QuestionLogRow.created_at.desc(), QuestionLogRow.id.desc()).limit(limit)
            return [_question_log(row) for row in s.scalars(query).all()]

    def texts_for_clustering(self) -> list[tuple[int, str]]:
        with self._sessions() as s:
            rows = s.execute(select(QuestionLogRow.id, QuestionLogRow.text).order_by(QuestionLogRow.id)).all()
            return [(row_id, text) for row_id, text in rows]

    def set_cluster_ids(self, assignments: Mapping[int, int]) -> None:
        with self._sessions() as s:
            for log_id, cluster_id in assignments.items():
                row = s.get(QuestionLogRow, log_id)
                if row is not None:
                    row.cluster_id = cluster_id
            s.commit()

    def stats(self) -> QuestionStats:
        with self._sessions() as s:

            def counts(column: Any) -> dict[str, int]:
                rows = s.execute(select(column, func.count(QuestionLogRow.id)).group_by(column)).all()
                result: dict[str, int] = {}
                for key, n in rows:  # NULL and "other" are two groups in SQL: add them up, never overwrite
                    name = key or OTHER_SERVICE
                    result[name] = result.get(name, 0) + int(n)
                return result

            avg = s.scalar(
                select(func.avg(QuestionLogRow.latency_ms)).where(
                    QuestionLogRow.status != AnswerStatus.ERROR.value
                )
            )
            by_status = counts(QuestionLogRow.status)
            return QuestionStats(
                total=sum(by_status.values()),
                by_status=by_status,
                by_service=counts(QuestionLogRow.service_id),
                by_channel=counts(QuestionLogRow.channel),
                avg_latency_ms=float(avg or 0.0),
            )

    def delete_demo(self) -> int:
        with self._sessions() as s:
            result = s.execute(delete(QuestionLogRow).where(QuestionLogRow.is_demo.is_(True)))
            s.commit()
            return int(result.rowcount or 0)  # type: ignore[attr-defined]


class SqlCallRepo:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    def _find(self, s: Session, call_sid: str) -> CallRow | None:
        return s.scalars(select(CallRow).where(CallRow.call_sid == call_sid)).first()

    def record_start(self, call_sid: str, phone: PhoneNumber, direction: str) -> None:
        with self._sessions() as s:
            if self._find(s, call_sid) is None:  # idempotent
                s.add(CallRow(call_sid=call_sid, phone=phone.e164, direction=direction))
                s.commit()

    def record_turn(self, call_sid: str) -> int:
        with self._sessions() as s:
            row = self._find(s, call_sid)
            if row is None:
                raise NotFound(f"unknown call {call_sid}")
            row.turns += 1
            s.commit()
            return row.turns

    def record_end(self, call_sid: str) -> None:
        with self._sessions() as s:
            row = self._find(s, call_sid)
            if row is not None:
                row.ended_at = datetime.now(UTC)
                s.commit()

    def last_outbound_at(self, phone: PhoneNumber) -> datetime | None:
        with self._sessions() as s:
            return s.scalar(
                select(func.max(CallRow.started_at)).where(
                    CallRow.phone == phone.e164, CallRow.direction.startswith("outbound")
                )
            )

    def count_since(self, since: datetime) -> int:
        with self._sessions() as s:
            return int(s.scalar(select(func.count(CallRow.id)).where(CallRow.started_at >= since)) or 0)


class SqlClusterRepo:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._sessions = session_factory

    def replace_all(self, clusters: Sequence[Cluster]) -> list[int]:
        with self._sessions() as s:
            s.execute(delete(ClusterRow))
            rows = [
                ClusterRow(
                    label=c.label, size=c.size, examples_json=json.dumps(list(c.examples), ensure_ascii=False)
                )
                for c in clusters
            ]
            s.add_all(rows)
            s.commit()
            return [row.id for row in rows]

    def list_all(self) -> list[Cluster]:
        with self._sessions() as s:
            rows = s.scalars(select(ClusterRow).order_by(ClusterRow.id)).all()
            return [
                Cluster(label=r.label, size=r.size, examples=tuple(json.loads(r.examples_json)), id=r.id)
                for r in rows
            ]


# ------------------------------------------------------------------ row -> entity


def _message(row: MessageRow) -> Message:
    return Message(
        role=Role(row.role),
        channel=Channel(row.channel),
        text=row.text,
        service_id=row.service_id,
        status=AnswerStatus(row.status) if row.status else None,
        created_at=row.created_at,
    )


def _question_log(row: QuestionLogRow) -> QuestionLog:
    return QuestionLog(
        phone_hash=row.phone_hash,
        channel=Channel(row.channel),
        text=row.text,
        status=AnswerStatus(row.status),
        service_id=row.service_id,
        confidence=row.confidence,
        router_source=RouterSource(row.router_source) if row.router_source else None,
        latency_ms=row.latency_ms,
        llm_calls=row.llm_calls,
        llm_backend=row.llm_backend,
        cluster_id=row.cluster_id,
        is_demo=row.is_demo,
        created_at=row.created_at,
    )
