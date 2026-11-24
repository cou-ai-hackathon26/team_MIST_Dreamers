"""SQLite answer cache with a time limit (FR-AGT-15). Survives restarts, so pre-warming is kept."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities import Answer
from app.domain.policies import CACHE_TTL_HOURS
from app.infrastructure.db.models import AnswerCacheRow
from app.infrastructure.db.serialization import answer_from_json, answer_to_json


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SqlAnswerCache:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        ttl_hours: float = CACHE_TTL_HOURS,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._sessions = session_factory
        self._ttl = timedelta(hours=ttl_hours)
        self._clock = clock

    def get(self, key: str) -> Answer | None:
        with self._sessions() as s:
            row = s.get(AnswerCacheRow, key)
            if row is None:
                return None
            if row.created_at < self._clock() - self._ttl:
                s.delete(row)  # expired: remove it
                s.commit()
                return None
            return answer_from_json(row.answer_json)

    def set(self, key: str, answer: Answer) -> None:
        with self._sessions() as s:
            s.merge(AnswerCacheRow(key=key, answer_json=answer_to_json(answer), created_at=self._clock()))
            s.commit()
