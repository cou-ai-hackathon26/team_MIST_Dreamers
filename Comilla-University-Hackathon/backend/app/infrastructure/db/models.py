"""SQLAlchemy tables (SRS 6.2). Enums are stored as plain strings; times as UTC."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator[datetime]):
    """Stores UTC, always returns timezone-aware UTC (SQLite itself forgets time zones)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: pass a timezone-aware value")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:  # type: ignore[no-untyped-def]
        return None if value is None else value.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    phone: Mapped[str] = mapped_column(String(16), index=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, onupdate=_now)


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(10))
    channel: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    service_id: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str | None] = mapped_column(String(20))
    call_sid: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, index=True)


class ChecklistRow(Base):
    __tablename__ = "checklists"
    # Never reuse a deleted id (SQLite would otherwise give the next row max(id) + 1), so a delete
    # from a History page that was open for a while can never hit a newer checklist.
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(16), index=True)
    service_id: Mapped[str] = mapped_column(String(40))
    content_json: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[str] = mapped_column(Text)
    sms_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    call_sid: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class QuestionLogRow(Base):
    __tablename__ = "question_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_hash: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    service_id: Mapped[str | None] = mapped_column(String(40), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    router_source: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    llm_backend: Mapped[str | None] = mapped_column(String(40))
    cluster_id: Mapped[int | None] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, index=True)


class CallRow(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_sid: Mapped[str] = mapped_column(String(64), unique=True)
    phone: Mapped[str] = mapped_column(String(16), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    turns: Mapped[int] = mapped_column(Integer, default=0)


class ClusterRow(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer)
    examples_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class AnswerCacheRow(Base):
    __tablename__ = "answer_cache"

    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    answer_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, index=True)
