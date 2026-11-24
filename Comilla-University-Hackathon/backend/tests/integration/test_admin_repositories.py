"""QuestionLogRepo.stats and delete_demo on BOTH the in-memory fake and SQLite (D2-R1, FR-ADM-01).

Same idea as test_repositories.py: if the fake and the SQL repository ever disagree, unit tests lie.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.ports.repositories import QuestionLogRepo
from app.domain.entities import QuestionLog
from app.domain.value_objects import AnswerStatus, Channel
from app.infrastructure.db.repositories import SqlQuestionLogRepo
from app.infrastructure.db.session import init_db, make_engine, make_session_factory
from tests import fakes

NOW = datetime(2026, 11, 22, 4, 0, tzinfo=UTC)


@pytest.fixture(params=["fake", "sql"])
def logs(request: pytest.FixtureRequest) -> QuestionLogRepo:
    if request.param == "fake":
        return fakes.InMemoryQuestionLogRepo()
    engine = make_engine("sqlite://")
    init_db(engine)
    return SqlQuestionLogRepo(make_session_factory(engine))


def log(
    status: AnswerStatus = AnswerStatus.ANSWERED,
    service: str | None = "old_age_allowance",
    channel: Channel = Channel.APP,
    latency: int = 1000,
    demo: bool = False,
    text: str = "প্রশ্ন",
) -> QuestionLog:
    return QuestionLog(
        phone_hash="h", channel=channel, text=text, status=status, service_id=service,
        latency_ms=latency, is_demo=demo, created_at=NOW - timedelta(minutes=len(text)),
    )  # fmt: skip


def test_stats_of_an_empty_table(logs: QuestionLogRepo) -> None:
    s = logs.stats()
    assert (s.total, dict(s.by_status), dict(s.by_service), dict(s.by_channel), s.avg_latency_ms) == (
        0, {}, {}, {}, 0.0,
    )  # fmt: skip


def test_stats_counts_by_status_service_and_channel(logs: QuestionLogRepo) -> None:
    for item in [
        log(),
        log(channel=Channel.VOICE),
        log(service="nid_correction", channel=Channel.VOICE),
        log(AnswerStatus.FALLBACK, service="other"),
        log(AnswerStatus.ERROR, service=None, latency=30000),
    ]:
        logs.add(item)
    s = logs.stats()
    assert s.total == 5
    assert dict(s.by_status) == {"answered": 3, "fallback": 1, "error": 1}
    assert dict(s.by_service) == {"old_age_allowance": 2, "nid_correction": 1, "other": 2}  # None -> other
    assert dict(s.by_channel) == {"app": 3, "voice": 2}
    assert s.avg_latency_ms == pytest.approx(1000.0)  # the error is left out


def test_delete_demo_removes_only_sample_rows(logs: QuestionLogRepo) -> None:
    logs.add(log(text="আসল"))
    logs.add(log(demo=True, text="নমুনা ১"))
    logs.add(log(demo=True, text="নমুনা ২"))
    assert logs.delete_demo() == 2
    assert [x.text for x in logs.list_recent(None, 10)] == ["আসল"]
    assert logs.delete_demo() == 0


def test_rows_added_after_a_delete_are_all_kept(logs: QuestionLogRepo) -> None:
    logs.add(log(text="ক"))
    logs.add(log(demo=True, text="খখ"))
    logs.delete_demo()
    logs.add(log(text="গগগ"))
    logs.add(log(text="ঘঘঘঘ"))
    assert sorted(x.text for x in logs.list_recent(None, 10)) == ["ক", "গগগ", "ঘঘঘঘ"]
