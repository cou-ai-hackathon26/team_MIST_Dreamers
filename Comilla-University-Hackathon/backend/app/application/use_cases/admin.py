"""Use cases for the admin dashboard (D2-R1: FR-ADM-01, FR-ADM-02, SRS 3.4).

GetAdminStats: KPI numbers, questions per service and per channel, calls today.
ListQuestions: the newest logged questions, optionally only one status (e.g. the unanswered ones).
Neither returns a phone number or a phone hash (NFR-PRIV-01).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.application.ports.repositories import CallRepo, QuestionLogRepo
from app.domain.entities import QuestionLog, Service
from app.domain.value_objects import AnswerStatus, Channel, RouterSource

# "Today" for the KPI means the Bangladesh calendar day (UTC+6, no daylight saving).
BANGLADESH_TIME = timezone(timedelta(hours=6), "Asia/Dhaka")
MAX_QUESTIONS = 200


@dataclass(frozen=True)
class ServiceCount:
    service_id: str
    name_bn: str
    count: int


@dataclass(frozen=True)
class AdminStats:
    total_questions: int
    answered_pct: float
    fallback_pct: float
    avg_latency_ms: int
    calls_today: int
    by_service: tuple[ServiceCount, ...]  # every known service (zeros included), most asked first
    by_channel: Mapping[str, int]  # voice / app (both always present)
    by_status: Mapping[str, int]  # answered / follow_up / fallback / error (all always present)


@dataclass(frozen=True)
class AdminQuestion:
    text: str
    status: AnswerStatus
    channel: Channel
    service_id: str | None
    service_name_bn: str | None
    router_source: RouterSource | None
    latency_ms: int
    is_demo: bool
    created_at: datetime


def _percent(part: int, total: int) -> float:
    return round(100 * part / total, 1) if total else 0.0


def start_of_today(now: datetime) -> datetime:
    """Midnight of the current Bangladesh day, in UTC."""
    local = now.astimezone(BANGLADESH_TIME)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


class GetAdminStats:
    def __init__(
        self,
        question_logs: QuestionLogRepo,
        calls: CallRepo,
        services: Sequence[Service],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._logs = question_logs
        self._calls = calls
        self._services = list(services)
        self._now = now

    def execute(self) -> AdminStats:
        stats = self._logs.stats()
        names = {s.id: s.name_bn for s in self._services}
        order = {s.id: i for i, s in enumerate(self._services)}

        counts = {s.id: 0 for s in self._services} | dict(stats.by_service)
        by_service = sorted(
            (ServiceCount(sid, names.get(sid, sid), n) for sid, n in counts.items()),
            key=lambda c: (-c.count, order.get(c.service_id, len(order))),
        )
        by_status = {s.value: 0 for s in AnswerStatus} | dict(stats.by_status)
        by_channel = {Channel.VOICE.value: 0, Channel.APP.value: 0} | dict(stats.by_channel)

        return AdminStats(
            total_questions=stats.total,
            answered_pct=_percent(by_status[AnswerStatus.ANSWERED.value], stats.total),
            fallback_pct=_percent(by_status[AnswerStatus.FALLBACK.value], stats.total),
            avg_latency_ms=round(stats.avg_latency_ms),
            calls_today=self._calls.count_since(start_of_today(self._now())),
            by_service=tuple(by_service),
            by_channel=by_channel,
            by_status=by_status,
        )


class ListQuestions:
    def __init__(self, question_logs: QuestionLogRepo, services: Sequence[Service]) -> None:
        self._logs = question_logs
        self._names = {s.id: s.name_bn for s in services}

    def execute(self, status: AnswerStatus | None = None, limit: int = 50) -> list[AdminQuestion]:
        limit = max(1, min(limit, MAX_QUESTIONS))
        return [self._row(log) for log in self._logs.list_recent(status, limit)]

    def _row(self, log: QuestionLog) -> AdminQuestion:
        return AdminQuestion(
            text=log.text,
            status=log.status,
            channel=log.channel,
            service_id=log.service_id,
            service_name_bn=self._names.get(log.service_id) if log.service_id else None,
            router_source=log.router_source,
            latency_ms=log.latency_ms,
            is_demo=log.is_demo,
            created_at=log.created_at,
        )
