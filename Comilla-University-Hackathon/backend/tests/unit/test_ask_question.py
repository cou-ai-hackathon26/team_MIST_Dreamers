import pytest

from app.application.privacy import hash_phone
from app.application.use_cases.ask_question import AskQuestion
from app.domain.entities import Answer, Service
from app.domain.errors import InvalidPhone, LLMUnavailable
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role
from app.infrastructure.agent.stub_engine import StubAnswerEngine
from tests import fakes

SERVICES = [Service("old_age_allowance", "বয়স্ক ভাতা", "Old Age Allowance", "সমাজসেবা অফিস", "বয়স্ক ভাতা")]
PHONE = "01712345678"
SALT = "test-salt"


class Setup:
    def __init__(self, engine=None) -> None:
        self.engine = engine or StubAnswerEngine()
        self.conversations = fakes.InMemoryConversationRepo()
        self.checklists = fakes.InMemoryChecklistRepo()
        self.logs = fakes.InMemoryQuestionLogRepo()
        self.use_case = AskQuestion(
            self.engine, self.conversations, self.checklists, self.logs, SERVICES, phone_hash_salt=SALT
        )


def test_answer_is_returned_with_service_and_latency() -> None:
    s = Setup()
    result = s.use_case.execute(PHONE, "বয়স্ক ভাতা কী?", Channel.APP)
    assert result.answer.status is AnswerStatus.ANSWERED
    assert result.service is not None and result.service.name_bn == "বয়স্ক ভাতা"
    assert result.latency_ms >= 0


def test_both_messages_are_saved_in_order() -> None:
    s = Setup()
    s.use_case.execute(PHONE, "  বয়স্ক   ভাতা  ", Channel.APP)
    user, assistant = s.conversations.recent_messages(PhoneNumber.parse(PHONE), 6)
    assert (user.role, user.text) == (Role.USER, "বয়স্ক ভাতা")  # extra spaces cleaned
    assert assistant.role is Role.ASSISTANT and assistant.status is AnswerStatus.ANSWERED


def test_voice_saves_the_spoken_text_app_saves_the_written_text() -> None:
    s = Setup()
    s.use_case.execute(PHONE, "ভাতা", Channel.VOICE, call_sid="CA1")
    s.use_case.execute(PHONE, "ভাতা", Channel.APP)
    messages = s.conversations.recent_messages(PhoneNumber.parse(PHONE), 6)
    voice_reply, app_reply = messages[1], messages[3]
    assert "**" not in voice_reply.text  # no markdown read aloud
    assert app_reply.text.startswith("**বয়স্ক ভাতা**")


def test_history_is_passed_to_the_engine() -> None:
    engine = fakes.FakeEngine(StubAnswerEngine().answer("x", [], Channel.APP))
    s = Setup(engine)
    s.use_case.execute(PHONE, "প্রথম প্রশ্ন", Channel.APP)
    s.use_case.execute(PHONE, "দ্বিতীয় প্রশ্ন", Channel.APP)
    _, history, _ = engine.questions[1]
    assert [m.text for m in history][0] == "প্রথম প্রশ্ন"  # previous turn included
    assert all(m.text != "দ্বিতীয় প্রশ্ন" for m in history)  # current question not duplicated


def test_checklist_saved_only_for_answered() -> None:
    s = Setup()
    s.use_case.execute(PHONE, "ভাতা", Channel.APP)
    assert len(s.checklists.list_for_phone(PhoneNumber.parse(PHONE), 10)) == 1

    sorry = Answer(status=AnswerStatus.FALLBACK, speech_text="দুঃখিত", display_text="দুঃখিত")
    fallback = fakes.FakeEngine(sorry)
    s2 = Setup(fallback)
    s2.use_case.execute(PHONE, "জমির ঝামেলা", Channel.APP)
    assert s2.checklists.list_for_phone(PhoneNumber.parse(PHONE), 10) == []


def test_log_stores_a_salted_hash_never_the_phone() -> None:
    s = Setup()
    s.use_case.execute(PHONE, "ভাতা", Channel.APP)
    [entry] = s.logs.list_recent(None, 10)
    assert entry.phone_hash == hash_phone(PhoneNumber.parse(PHONE), SALT)
    assert "1712345678" not in repr(entry)
    assert entry.llm_backend == "stub" and entry.status is AnswerStatus.ANSWERED


def test_engine_failure_is_logged_as_error_and_raised() -> None:
    class Broken:
        def answer(self, *args):
            raise LLMUnavailable("down")

    s = Setup(Broken())
    with pytest.raises(LLMUnavailable):
        s.use_case.execute(PHONE, "ভাতা", Channel.APP)
    [entry] = s.logs.list_recent(None, 10)
    assert entry.status is AnswerStatus.ERROR
    assert [m.role for m in s.conversations.recent_messages(PhoneNumber.parse(PHONE), 6)] == [Role.USER]


def test_invalid_phone_is_rejected_before_anything_is_saved() -> None:
    s = Setup()
    with pytest.raises(InvalidPhone):
        s.use_case.execute("12345", "ভাতা", Channel.APP)
    assert s.logs.list_recent(None, 10) == []


def test_hash_is_stable_and_salt_dependent() -> None:
    p = PhoneNumber.parse(PHONE)
    assert hash_phone(p, "a") == hash_phone(p, "a")
    assert hash_phone(p, "a") != hash_phone(p, "b")
    assert len(hash_phone(p, "a")) == 64
