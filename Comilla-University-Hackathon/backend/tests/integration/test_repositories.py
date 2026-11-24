"""Contract tests: every test runs on BOTH the in-memory fake and the real SQLite repository.

If they ever behave differently, unit tests (which use the fakes) would lie. This file stops that.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.application.ports.clustering import Cluster
from app.domain.entities import Answer, Checklist, Citation, Message, QuestionLog
from app.domain.errors import NotFound
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role, RouterSource
from app.infrastructure.cache.answer_cache import SqlAnswerCache
from app.infrastructure.db import repositories as sql
from app.infrastructure.db.session import init_db, make_engine, make_session_factory
from tests import fakes

A = PhoneNumber.parse("01712345678")
B = PhoneNumber.parse("01812345678")
NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)

CHECKLIST = Checklist("old_age_allowance", "পুরুষ ৬৫+", ("এনআইডি",), "বিনামূল্যে", "সমাজসেবা অফিস", "কমিটি")
CITATION = Citation("বয়স্ক ভাতা", "https://example.gov.bd", "স্নিপেট", "old_age_allowance-001")


@dataclass
class Repos:
    conversations: Any
    checklists: Any
    logs: Any
    calls: Any
    clusters: Any
    cache: Any


@pytest.fixture(params=["fake", "sql"])
def repos(request: pytest.FixtureRequest) -> Repos:
    if request.param == "fake":
        return Repos(
            fakes.InMemoryConversationRepo(),
            fakes.InMemoryChecklistRepo(),
            fakes.InMemoryQuestionLogRepo(),
            fakes.InMemoryCallRepo(),
            fakes.InMemoryClusterRepo(),
            fakes.InMemoryAnswerCache(),
        )
    engine = make_engine("sqlite://")
    init_db(engine)
    sf = make_session_factory(engine)
    return Repos(
        sql.SqlConversationRepo(sf),
        sql.SqlChecklistRepo(sf),
        sql.SqlQuestionLogRepo(sf),
        sql.SqlCallRepo(sf),
        sql.SqlClusterRepo(sf),
        SqlAnswerCache(sf),
    )


def msg(text: str, role: Role = Role.USER, status: AnswerStatus | None = None) -> Message:
    return Message(role=role, channel=Channel.APP, text=text, service_id="old_age_allowance", status=status)


def log(text: str, status: AnswerStatus, minutes_ago: int) -> QuestionLog:
    return QuestionLog(
        phone_hash="h", channel=Channel.VOICE, text=text, status=status,
        router_source=RouterSource.TFIDF, llm_backend="ollama",
        created_at=NOW - timedelta(minutes=minutes_ago),
    )  # fmt: skip


# ---------------------------------------------------------------- conversations


def test_same_phone_gets_the_same_conversation(repos: Repos) -> None:
    assert repos.conversations.get_or_create(A) == repos.conversations.get_or_create(A)
    assert repos.conversations.get_or_create(A) != repos.conversations.get_or_create(B)


def test_recent_messages_are_oldest_first_and_limited(repos: Repos) -> None:
    conv = repos.conversations.get_or_create(A)
    for i in range(8):
        repos.conversations.add_message(conv, msg(f"বার্তা {i}"))
    recent = repos.conversations.recent_messages(A, 6)
    assert [m.text for m in recent] == [f"বার্তা {i}" for i in range(2, 8)]


def test_message_fields_round_trip(repos: Repos) -> None:
    conv = repos.conversations.get_or_create(A)
    repos.conversations.add_message(conv, msg("আপনি কি স্থায়ী বাসিন্দা?", Role.ASSISTANT, AnswerStatus.FOLLOW_UP))
    [m] = repos.conversations.recent_messages(A, 6)
    assert (m.role, m.status, m.service_id) == (Role.ASSISTANT, AnswerStatus.FOLLOW_UP, "old_age_allowance")


def test_history_is_separate_per_phone_and_deletable(repos: Repos) -> None:
    repos.conversations.add_message(repos.conversations.get_or_create(A), msg("ক"))
    repos.conversations.add_message(repos.conversations.get_or_create(B), msg("খ"))
    assert repos.conversations.delete_for_phone(A) is True
    assert repos.conversations.recent_messages(A, 6) == []
    assert [m.text for m in repos.conversations.recent_messages(B, 6)] == ["খ"]
    assert repos.conversations.delete_for_phone(A) is False


# ---------------------------------------------------------------- checklists


def test_checklists_newest_first_with_citations(repos: Repos) -> None:
    other = Checklist("widow_allowance", "বিধবা", (), "বিনামূল্যে", "অফিস", "কমিটি")
    repos.checklists.save(A, CHECKLIST, [CITATION], sms_sent=False)
    repos.checklists.save(A, other, [], sms_sent=False)
    records = repos.checklists.list_for_phone(A, 10)
    assert [r.checklist.service_id for r in records] == ["widow_allowance", "old_age_allowance"]
    assert records[1].checklist == CHECKLIST and records[1].citations == (CITATION,)


def test_sms_sent_is_tracked_per_call_and_service(repos: Repos) -> None:
    repos.checklists.save(A, CHECKLIST, [CITATION], sms_sent=True, call_sid="CA1")
    assert repos.checklists.sms_already_sent("CA1", "old_age_allowance") is True
    assert repos.checklists.sms_already_sent("CA1", "widow_allowance") is False
    assert repos.checklists.sms_already_sent("CA2", "old_age_allowance") is False


def test_checklists_can_be_deleted_per_phone(repos: Repos) -> None:
    repos.checklists.save(A, CHECKLIST, [], sms_sent=False)
    repos.checklists.save(B, CHECKLIST, [], sms_sent=False)
    assert repos.checklists.delete_for_phone(A) == 1
    assert repos.checklists.list_for_phone(A, 10) == []
    assert len(repos.checklists.list_for_phone(B, 10)) == 1


# ---------------------------------------------------------------- question logs


def test_logs_newest_first_and_filtered_by_status(repos: Repos) -> None:
    repos.logs.add(log("পুরনো", AnswerStatus.ANSWERED, minutes_ago=30))
    repos.logs.add(log("নতুন", AnswerStatus.FALLBACK, minutes_ago=1))
    repos.logs.add(log("মাঝের", AnswerStatus.FALLBACK, minutes_ago=10))
    assert [x.text for x in repos.logs.list_recent(None, 10)] == ["নতুন", "মাঝের", "পুরনো"]
    assert [x.text for x in repos.logs.list_recent(AnswerStatus.FALLBACK, 10)] == ["নতুন", "মাঝের"]
    assert repos.logs.list_recent(None, 10)[0].llm_backend == "ollama"


def test_equal_times_list_the_later_added_first(repos: Repos) -> None:
    repos.logs.add(log("প্রথম", AnswerStatus.ANSWERED, minutes_ago=5))
    repos.logs.add(log("দ্বিতীয়", AnswerStatus.ANSWERED, minutes_ago=5))
    assert [x.text for x in repos.logs.list_recent(None, 10)] == ["দ্বিতীয়", "প্রথম"]


def test_cluster_ids_can_be_assigned(repos: Repos) -> None:
    repos.logs.add(log("ক", AnswerStatus.ANSWERED, 1))
    repos.logs.add(log("খ", AnswerStatus.ANSWERED, 2))
    pairs = repos.logs.texts_for_clustering()
    assert [text for _, text in pairs] == ["ক", "খ"]
    repos.logs.set_cluster_ids({pairs[0][0]: 7})
    assert {x.text: x.cluster_id for x in repos.logs.list_recent(None, 10)} == {"ক": 7, "খ": None}


# ---------------------------------------------------------------- calls


def test_call_turns_and_idempotent_start(repos: Repos) -> None:
    repos.calls.record_start("CA1", A, "inbound")
    assert repos.calls.record_turn("CA1") == 1
    repos.calls.record_start("CA1", A, "inbound")  # Twilio retry: must not reset turns
    assert repos.calls.record_turn("CA1") == 2


def test_unknown_call_turn_raises_but_end_is_ignored(repos: Repos) -> None:
    with pytest.raises(NotFound):
        repos.calls.record_turn("nope")
    repos.calls.record_end("nope")  # no error


def test_last_outbound_and_count(repos: Repos) -> None:
    before = datetime.now(UTC) - timedelta(seconds=5)
    assert repos.calls.last_outbound_at(A) is None
    repos.calls.record_start("CA1", A, "inbound")
    assert repos.calls.last_outbound_at(A) is None  # inbound does not count
    repos.calls.record_start("CA2", A, "outbound-api")
    assert repos.calls.last_outbound_at(A) is not None
    assert repos.calls.count_since(before) == 2


# ---------------------------------------------------------------- clusters + cache


def test_clusters_are_replaced_not_appended(repos: Repos) -> None:
    repos.clusters.replace_all([Cluster("এনআইডি বানান", 5, ("ক", "খ", "গ"))])
    ids = repos.clusters.replace_all([Cluster("ভাতা পাইনি", 3, ("ঘ",)), Cluster("পাসপোর্ট", 2, ())])
    assert len(ids) == 2
    assert [(c.label, c.examples) for c in repos.clusters.list_all()] == [("ভাতা পাইনি", ("ঘ",)), ("পাসপোর্ট", ())]


def test_cache_round_trips_a_full_answer(repos: Repos) -> None:
    answer = Answer(
        status=AnswerStatus.ANSWERED, speech_text="কথা", display_text="**লেখা**",
        service_id="old_age_allowance", confidence=0.9, router_source=RouterSource.BANGLABERT,
        checklist=CHECKLIST, citations=(CITATION,),
        timings={"generate": 1.2}, llm_calls=2,
    )  # fmt: skip
    assert repos.cache.get("k") is None
    repos.cache.set("k", answer)
    assert repos.cache.get("k") == answer
    repos.cache.set("k", Answer(status=AnswerStatus.FALLBACK, speech_text="x", display_text="x"))
    assert repos.cache.get("k").status is AnswerStatus.FALLBACK  # overwrite works


# ---------------------------------------------------------------- SQL-only: cache expiry


def test_sql_cache_entries_expire_after_ttl() -> None:
    engine = make_engine("sqlite://")
    init_db(engine)
    now = [NOW]
    cache = SqlAnswerCache(make_session_factory(engine), ttl_hours=24, clock=lambda: now[0])
    cache.set("k", Answer(status=AnswerStatus.FALLBACK, speech_text="x", display_text="x"))
    now[0] = NOW + timedelta(hours=23)
    assert cache.get("k") is not None
    now[0] = NOW + timedelta(hours=25)
    assert cache.get("k") is None
