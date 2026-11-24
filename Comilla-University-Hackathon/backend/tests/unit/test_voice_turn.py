"""One spoken turn of a call (D1-A5: SRS 3.1; FR-CALL-02, 05, 06, 09, 11)."""

from dataclasses import dataclass

import pytest

from app.application.dto import AskResult
from app.application.use_cases.speech import HandleVoiceTurn, is_goodbye
from app.domain import messages_bn
from app.domain.entities import Answer, Checklist, Citation, Message
from app.domain.errors import LLMUnavailable
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role
from tests.fakes import InMemoryCallRepo, InMemoryConversationRepo

PHONE = "+8801712345678"
CHECKLIST = Checklist("old_age_allowance", "৬৫+", ("জাতীয় পরিচয়পত্র",), "বিনামূল্যে", "উপজেলা", "কমিটি")
CITATION = Citation("বয়স্ক ভাতা", "https://dss.gov.bd", "...", "old_age_allowance-001")
ANSWERED = Answer(
    AnswerStatus.ANSWERED, "আপনি ভাতা পাবেন।", "**বয়স্ক ভাতা**",
    service_id="old_age_allowance", checklist=CHECKLIST, citations=(CITATION,),
)  # fmt: skip
FOLLOW_UP = Answer(
    AnswerStatus.FOLLOW_UP, "আপনি কি স্থায়ী বাসিন্দা?", "", service_id="widow_allowance",
    follow_up_question="আপনি কি স্থায়ী বাসিন্দা?",
)  # fmt: skip
FALLBACK = Answer(AnswerStatus.FALLBACK, messages_bn.FALLBACK, messages_bn.FALLBACK)


@dataclass(frozen=True)
class AskResultWithSms(AskResult):
    """AskResult as it looks once AskQuestion reports a queued SMS."""

    sms_scheduled: bool = False


class FakeAsk:
    def __init__(self, answer: Answer = ANSWERED, error: Exception | None = None, sms: bool = False) -> None:
        self.answer, self.error, self.sms = answer, error, sms
        self.asked: list[tuple[str, str, Channel, str | None]] = []

    def __call__(self, phone: str, text: str, channel: Channel, call_sid: str | None) -> AskResult:
        self.asked.append((phone, text, channel, call_sid))
        if self.error:
            raise self.error
        return AskResultWithSms("conv-1", self.answer, None, 1200, sms_scheduled=self.sms)


class Setup:
    def __init__(self, ask: FakeAsk | None = None, max_turns: int = 6) -> None:
        self.ask = ask or FakeAsk()
        self.calls = InMemoryCallRepo()
        self.conversations = InMemoryConversationRepo()
        self.turn = HandleVoiceTurn(self.ask, self.calls, self.conversations, max_turns=max_turns)

    def say(self, text: str, call_sid: str = "CA1", phone: str = PHONE):
        return self.turn.execute(call_sid, phone, text, direction="inbound")

    def assistant_asked_follow_up(self) -> None:
        number = PhoneNumber.parse(PHONE)
        cid = self.conversations.get_or_create(number)
        msg = Message(Role.ASSISTANT, Channel.VOICE, FOLLOW_UP.speech_text, status=AnswerStatus.FOLLOW_UP)
        self.conversations.add_message(cid, msg, "CA1")


# ---------------------------------------------------------------- goodbye phrases


@pytest.mark.parametrize(
    "text", ["না", "আর কিছু না", "ধন্যবাদ", "না, ধন্যবাদ।", "আর কিছু লাগবে না", "জি না ধন্যবাদ", "আল্লাহ হাফেজ"]
)
def test_goodbye_phrases(text: str) -> None:
    assert is_goodbye(text)


@pytest.mark.parametrize(
    "text", ["", "ঠিক আছে", "আর কিছু জানতে চাই", "বয়স্ক ভাতা পাবো না?", "হ্যাঁ", "না আমার বয়স ৬৭ বছর ধন্যবাদ"]
)
def test_not_goodbye(text: str) -> None:
    assert not is_goodbye(text)


# ---------------------------------------------------------------- turns


def test_question_goes_to_ask_question_as_voice_with_call_sid() -> None:
    s = Setup()
    reply = s.say("  আমার বয়স ৬৭  ")
    assert s.ask.asked == [(PHONE, "আমার বয়স ৬৭", Channel.VOICE, "CA1")]
    assert reply.say == (ANSWERED.speech_text, messages_bn.CONTINUE)
    assert not reply.hang_up
    assert reply.status == "answered"


def test_sms_sentence_only_when_an_sms_was_queued() -> None:
    reply = Setup(FakeAsk(sms=True)).say("বয়স্ক ভাতা")
    assert reply.say == (ANSWERED.speech_text, messages_bn.SMS_SENT, messages_bn.CONTINUE)


def test_goodbye_ends_the_call_without_asking() -> None:
    s = Setup()
    reply = s.say("আর কিছু না")
    assert reply.say == (messages_bn.GOODBYE,)
    assert reply.hang_up
    assert s.ask.asked == []


def test_no_after_a_follow_up_question_is_an_answer_not_goodbye() -> None:
    s = Setup()
    s.assistant_asked_follow_up()
    reply = s.say("না")
    assert s.ask.asked[0][1] == "না"
    assert not reply.hang_up


def test_follow_up_answer_speaks_the_question_and_listens() -> None:
    reply = Setup(FakeAsk(FOLLOW_UP)).say("বিধবা ভাতার জন্য কী লাগে?")
    assert reply.say == (FOLLOW_UP.speech_text,)
    assert not reply.hang_up
    assert reply.status == "follow_up"


def test_fallback_is_spoken_then_continue() -> None:
    reply = Setup(FakeAsk(FALLBACK)).say("জমি নিয়ে ঝামেলা")
    assert reply.say == (messages_bn.FALLBACK, messages_bn.CONTINUE)
    assert reply.status == "fallback"


@pytest.mark.parametrize("error", [LLMUnavailable("down"), RuntimeError("bug")])
def test_any_failure_speaks_error_and_keeps_listening(error: Exception) -> None:
    reply = Setup(FakeAsk(error=error)).say("বয়স্ক ভাতা")
    assert reply.say == (messages_bn.ERROR,)
    assert not reply.hang_up
    assert reply.status == "error"


def test_non_bangladeshi_caller_gets_error_not_a_crash() -> None:
    s = Setup()
    reply = s.say("বয়স্ক ভাতা", phone="+15005550006")
    assert reply.say == (messages_bn.ERROR,)
    assert s.ask.asked == []


def test_last_turn_gets_its_answer_then_goodbye() -> None:
    s = Setup(max_turns=2)
    assert not s.say("প্রশ্ন ১").hang_up
    last = s.say("প্রশ্ন ২")
    assert last.say == (ANSWERED.speech_text, messages_bn.GOODBYE)
    assert last.hang_up


def test_turns_are_stored_on_the_call_row() -> None:
    s = Setup()
    s.say("প্রশ্ন ১")
    s.say("প্রশ্ন ২")
    s.say("ধন্যবাদ")  # a goodbye is not a question turn
    row = s.calls.calls["CA1"]
    assert row["turns"] == 2
    assert row["phone"] == PHONE
    assert row["direction"] == "inbound"
