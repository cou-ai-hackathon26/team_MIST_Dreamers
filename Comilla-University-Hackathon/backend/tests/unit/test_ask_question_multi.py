"""AskQuestion with two-service answers (sprint W1, FR-AGT-21, FR-SMS-01, 02)."""

import dataclasses

from app.application.use_cases.ask_question import AskQuestion
from app.domain.entities import Answer, Checklist, Citation
from app.domain.messages_bn import FALLBACK
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role
from tests import fakes
from tests.unit.test_ask_question_sms import PHONE, SERVICES, ScriptedEngine

OLD, WIDOW = "old_age_allowance", "widow_allowance"
CITATION = Citation("নীতিমালা", "https://dss.gov.bd", "…", "c1")


def checklist(sid: str) -> Checklist:
    return Checklist(sid, "শর্ত", ("এনআইডি",), "বিনামূল্যে", "উপজেলা সমাজসেবা অফিস", "কমিটি")


def multi_answer() -> Answer:
    return Answer(
        status=AnswerStatus.ANSWERED, speech_text="দুটি সেবা।", display_text="দুটি সেবা।", service_id=OLD,
        confidence=0.7, checklist=checklist(OLD), citations=(CITATION,),
        service_ids=(OLD, WIDOW), checklists=(checklist(OLD), checklist(WIDOW)), mode="multi",
    )  # fmt: skip


class Setup:
    def __init__(self, *answers: Answer) -> None:
        self.sms = fakes.FakeSms()
        self.checklists = fakes.InMemoryChecklistRepo()
        self.conversations = fakes.InMemoryConversationRepo()
        self.logs = fakes.InMemoryQuestionLogRepo()
        self.use_case = AskQuestion(
            ScriptedEngine(*(answers or (multi_answer(),))), self.conversations, self.checklists, self.logs,
            SERVICES, phone_hash_salt="salt", sms=self.sms, runner=fakes.FakeRunner(),
        )  # fmt: skip

    def ask(self, channel: Channel = Channel.VOICE, call_sid: str | None = "CA1"):  # type: ignore[no-untyped-def]
        return self.use_case.execute(PHONE, "আমি বিধবা, বয়স ৬৬", channel, call_sid=call_sid)


def test_multi_voice_answer_sends_exactly_two_sms() -> None:
    s = Setup()
    result = s.ask()
    assert len(s.sms.sent) == 2
    assert result.sms_services == (OLD, WIDOW) and result.sms_count == 2 and result.sms_scheduled
    assert "বয়স্ক ভাতা" in s.sms.sent[0][1] and "বিধবা ভাতা" in s.sms.sent[1][1]


def test_same_mixed_question_again_in_the_call_sends_no_more_sms() -> None:
    s = Setup()
    s.ask()
    again = s.ask()
    assert len(s.sms.sent) == 2 and again.sms_count == 0


def test_app_channel_sends_none_but_saves_both_checklists() -> None:
    s = Setup()
    result = s.ask(Channel.APP, call_sid=None)
    assert s.sms.sent == [] and result.sms_count == 0
    saved = [r.checklist.service_id for _, r in s.checklists.rows]
    assert saved == [OLD, WIDOW]
    assert [x.id for x in result.services] == [OLD, WIDOW]


def test_fallback_sends_none() -> None:
    s = Setup(Answer(status=AnswerStatus.FALLBACK, speech_text=FALLBACK, display_text=FALLBACK))
    s.ask()
    assert s.sms.sent == [] and s.checklists.rows == []


def test_both_services_are_stored_on_the_message_and_the_log_keeps_the_primary() -> None:
    s = Setup()
    s.ask(Channel.APP, call_sid=None)
    bot = [
        m for m in s.conversations.recent_messages(PhoneNumber.parse(PHONE), 10) if m.role is Role.ASSISTANT
    ]
    assert bot[-1].service_id == "old_age_allowance,widow_allowance"
    assert list(s.logs.logs.values())[-1].service_id == OLD  # admin charts keep working


def test_single_answer_still_stores_one_service() -> None:
    single = dataclasses.replace(multi_answer(), service_ids=(OLD,), checklists=(), mode="single")
    s = Setup(single)
    result = s.ask()
    assert len(s.sms.sent) == 1 and result.sms_services == (OLD,)
    bot = [
        m for m in s.conversations.recent_messages(PhoneNumber.parse(PHONE), 10) if m.role is Role.ASSISTANT
    ]
    assert bot[-1].service_id == OLD
