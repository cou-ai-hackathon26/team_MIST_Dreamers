"""GetAdminStats and ListQuestions (D2-R1: FR-ADM-01, 02, NFR-PRIV-01). Fakes only."""

from dataclasses import fields
from datetime import UTC, datetime, timedelta

from app.application.use_cases.admin import AdminQuestion, GetAdminStats, ListQuestions, start_of_today
from app.domain.entities import QuestionLog, Service
from app.domain.value_objects import AnswerStatus, Channel, RouterSource
from tests import fakes

SERVICES = [
    Service("old_age_allowance", "বয়স্ক ভাতা", "Old Age Allowance", "অফিস", "বয়স্ক ভাতা"),
    Service("nid_correction", "এনআইডি সংশোধন", "NID Correction", "অফিস", "এনআইডি"),
    Service("other", "অন্যান্য", "Other", "", "অন্যান্য"),
]
NOW = datetime(2026, 11, 22, 4, 0, tzinfo=UTC)  # 10:00 in Dhaka


def log(
    status: AnswerStatus = AnswerStatus.ANSWERED,
    service: str | None = "old_age_allowance",
    channel: Channel = Channel.APP,
    latency: int = 1000,
    minutes_ago: int = 0,
    text: str = "প্রশ্ন",
) -> QuestionLog:
    return QuestionLog(
        phone_hash="secret-hash", channel=channel, text=text, status=status, service_id=service,
        router_source=RouterSource.TFIDF, latency_ms=latency, created_at=NOW - timedelta(minutes=minutes_ago),
    )  # fmt: skip


class CountingCalls(fakes.InMemoryCallRepo):
    def __init__(self, result: int = 0) -> None:
        super().__init__()
        self.result = result
        self.asked_since: list[datetime] = []

    def count_since(self, since: datetime) -> int:
        self.asked_since.append(since)
        return self.result


def stats_for(*logs: QuestionLog, calls: CountingCalls | None = None):
    repo = fakes.InMemoryQuestionLogRepo()
    for item in logs:
        repo.add(item)
    return GetAdminStats(repo, calls or CountingCalls(), SERVICES, now=lambda: NOW).execute()


# ---------------------------------------------------------------- stats


def test_empty_database_gives_zeros_and_every_service() -> None:
    s = stats_for()
    assert (s.total_questions, s.answered_pct, s.fallback_pct, s.avg_latency_ms) == (0, 0.0, 0.0, 0)
    assert [c.service_id for c in s.by_service] == ["old_age_allowance", "nid_correction", "other"]
    assert all(c.count == 0 for c in s.by_service)
    assert s.by_channel == {"voice": 0, "app": 0}
    assert s.by_status == {"answered": 0, "follow_up": 0, "fallback": 0, "error": 0}


def test_percentages_and_counts() -> None:
    s = stats_for(
        log(),
        log(channel=Channel.VOICE),
        log(service="nid_correction", channel=Channel.VOICE),
        log(AnswerStatus.FALLBACK, service="other"),
    )
    assert s.total_questions == 4
    assert (s.answered_pct, s.fallback_pct) == (75.0, 25.0)
    assert s.by_channel == {"voice": 2, "app": 2}
    assert s.by_status["answered"] == 3 and s.by_status["fallback"] == 1


def test_services_are_sorted_most_asked_first_with_bangla_names() -> None:
    s = stats_for(log(service="nid_correction"), log(service="nid_correction"), log())
    assert [(c.service_id, c.name_bn, c.count) for c in s.by_service] == [
        ("nid_correction", "এনআইডি সংশোধন", 2),
        ("old_age_allowance", "বয়স্ক ভাতা", 1),
        ("other", "অন্যান্য", 0),
    ]


def test_a_question_without_a_service_counts_as_other() -> None:
    s = stats_for(log(AnswerStatus.ERROR, service=None))
    assert {c.service_id: c.count for c in s.by_service}["other"] == 1


def test_average_latency_ignores_errors() -> None:
    s = stats_for(log(latency=2000), log(latency=4000), log(AnswerStatus.ERROR, latency=30000))
    assert s.avg_latency_ms == 3000


def test_percentages_are_rounded_to_one_decimal() -> None:
    s = stats_for(log(), log(), log(AnswerStatus.FALLBACK))
    assert (s.answered_pct, s.fallback_pct) == (66.7, 33.3)


def test_calls_today_counts_from_midnight_in_bangladesh() -> None:
    calls = CountingCalls(result=5)
    s = stats_for(calls=calls)
    assert s.calls_today == 5
    assert calls.asked_since == [datetime(2026, 11, 21, 18, 0, tzinfo=UTC)]  # 00:00 Dhaka = 18:00 UTC


def test_start_of_today_just_after_midnight_in_dhaka() -> None:
    # 18:30 UTC on the 21st is already 00:30 on the 22nd in Dhaka.
    assert start_of_today(datetime(2026, 11, 21, 18, 30, tzinfo=UTC)) == datetime(
        2026, 11, 21, 18, 0, tzinfo=UTC
    )
    assert start_of_today(datetime(2026, 11, 21, 17, 59, tzinfo=UTC)) == datetime(
        2026, 11, 20, 18, 0, tzinfo=UTC
    )


# ---------------------------------------------------------------- questions


def questions(*logs: QuestionLog, status: AnswerStatus | None = None, limit: int = 50) -> list[AdminQuestion]:
    repo = fakes.InMemoryQuestionLogRepo()
    for item in logs:
        repo.add(item)
    return ListQuestions(repo, SERVICES).execute(status, limit)


def test_newest_first_with_service_names() -> None:
    rows = questions(
        log(text="পুরনো", minutes_ago=30), log(service="nid_correction", text="নতুন", minutes_ago=1)
    )
    assert [r.text for r in rows] == ["নতুন", "পুরনো"]
    assert rows[0].service_name_bn == "এনআইডি সংশোধন"


def test_filter_by_status_lists_the_unanswered() -> None:
    rows = questions(
        log(text="ক"), log(AnswerStatus.FALLBACK, service="other", text="খ"), status=AnswerStatus.FALLBACK
    )
    assert [(r.text, r.status, r.service_name_bn) for r in rows] == [("খ", AnswerStatus.FALLBACK, "অন্যান্য")]


def test_limit_is_kept_within_1_and_200() -> None:
    many = [log(minutes_ago=i) for i in range(5)]
    assert len(questions(*many, limit=2)) == 2
    assert len(questions(*many, limit=0)) == 1
    assert len(questions(*many, limit=10_000)) == 5


def test_rows_never_carry_the_phone_hash() -> None:
    names = {f.name for f in fields(AdminQuestion)}
    assert not any("phone" in name for name in names)
