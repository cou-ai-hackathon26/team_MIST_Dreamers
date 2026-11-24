"""AskQuestion: the SMS checklist after a voice answer (D1-A4: FR-SMS-01, 02, 04, 05, NFR-PRIV-01)."""

import logging

import pytest

from app.application.dto import AskResult
from app.application.use_cases.ask_question import AskQuestion
from app.domain.entities import Answer, Checklist, Citation, Message, Service
from app.domain.policies import MAX_SMS_CHARS
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber
from tests import fakes

SERVICES = [
    Service("old_age_allowance", "বয়স্ক ভাতা", "Old Age Allowance", "উপজেলা সমাজসেবা অফিস", "বয়স্ক ভাতা"),
    Service("widow_allowance", "বিধবা ভাতা", "Widow Allowance", "উপজেলা সমাজসেবা অফিস", "বিধবা ভাতা"),
]
PHONE = "01712345678"
E164 = "+8801712345678"


def answered(service_id: str = "old_age_allowance", papers: tuple[str, ...] = ("জাতীয় পরিচয়পত্র",)) -> Answer:
    return Answer(
        status=AnswerStatus.ANSWERED,
        speech_text="উত্তর। বিস্তারিত এসএমএসে পাঠানো হবে।",
        display_text="**উত্তর**",
        service_id=service_id,
        confidence=0.9,
        checklist=Checklist(service_id, "পুরুষ ৬৫+, নারী ৬২+", papers, "বিনামূল্যে", "উপজেলা সমাজসেবা অফিস", "কমিটি"),
        citations=(Citation("বয়স্ক ভাতা", "https://dss.gov.bd/", "...", f"{service_id}-001"),),
    )


class ScriptedEngine:
    """Returns the given answers one after another (the last one repeats)."""

    def __init__(self, *answers: Answer) -> None:
        self._answers = list(answers)

    def answer(self, question: str, history: list[Message], channel: Channel) -> Answer:
        return self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]


class Setup:
    def __init__(self, *answers: Answer, sms: object | None = None, wired: bool = True) -> None:
        self.sms = sms if sms is not None else fakes.FakeSms()
        self.runner = fakes.FakeRunner()
        self.checklists = fakes.InMemoryChecklistRepo()
        self.use_case = AskQuestion(
            ScriptedEngine(*(answers or (answered(),))),
            fakes.InMemoryConversationRepo(),
            self.checklists,
            fakes.InMemoryQuestionLogRepo(),
            SERVICES,
            phone_hash_salt="salt",
            sms=self.sms if wired else None,  # type: ignore[arg-type]
            runner=self.runner if wired else None,
        )

    def ask(self, channel: Channel = Channel.VOICE, call_sid: str | None = "CA1") -> AskResult:
        return self.use_case.execute(PHONE, "বয়স্ক ভাতা পাবো?", channel, call_sid=call_sid)


# ---------------------------------------------------------------- when an SMS is sent


def test_first_voice_answer_sends_one_sms_in_the_background() -> None:
    s = Setup()
    s.ask()
    assert len(s.sms.sent) == 1
    phone, text = s.sms.sent[0]
    assert phone == PhoneNumber.parse(PHONE)
    assert text.startswith("এক কল: বয়স্ক ভাতা")
    assert len(text) <= MAX_SMS_CHARS
    assert [name for name, _ in s.runner.submitted] == ["_send_sms"]  # through the runner, not inline


def test_the_checklist_is_marked_sent_for_that_call() -> None:
    s = Setup()
    s.ask()
    ((_, record),) = s.checklists.rows
    assert record.sms_sent is True and record.call_sid == "CA1"


def test_same_service_twice_in_one_call_sends_only_one_sms() -> None:
    s = Setup()
    s.ask()
    s.ask()
    s.ask()
    assert len(s.sms.sent) == 1
    assert [r.sms_sent for _, r in s.checklists.rows] == [True, False, False]  # checklists still saved


def test_a_second_service_in_the_same_call_gets_its_own_sms() -> None:
    s = Setup(answered("old_age_allowance"), answered("widow_allowance"), answered("old_age_allowance"))
    s.ask()
    s.ask()
    s.ask()
    titles = [text.splitlines()[0] for _, text in s.sms.sent]
    assert titles == ["এক কল: বয়স্ক ভাতা", "এক কল: বিধবা ভাতা"]


def test_a_new_call_about_the_same_service_sends_again() -> None:
    s = Setup()
    s.ask(call_sid="CA1")
    s.ask(call_sid="CA2")
    assert len(s.sms.sent) == 2


def test_a_long_checklist_is_shortened_to_the_sms_limit() -> None:
    papers = tuple(f"অনেক লম্বা একটি কাগজের নাম নম্বর {i}" for i in range(30))
    s = Setup(answered(papers=papers))
    s.ask()
    ((_, text),) = s.sms.sent
    assert len(text) <= MAX_SMS_CHARS
    assert "ফি: বিনামূল্যে" in text  # the fee line is never cut


# ---------------------------------------------------------------- when no SMS is sent


def test_app_answers_never_send_sms() -> None:
    s = Setup()
    s.ask(channel=Channel.APP, call_sid=None)
    assert s.sms.sent == [] and s.runner.submitted == []
    ((_, record),) = s.checklists.rows
    assert record.sms_sent is False


@pytest.mark.parametrize("status", [AnswerStatus.FALLBACK, AnswerStatus.FOLLOW_UP, AnswerStatus.ERROR])
def test_answers_that_are_not_answered_never_send_sms(status: AnswerStatus) -> None:
    follow_up = "আপনি কি স্থায়ী বাসিন্দা?" if status is AnswerStatus.FOLLOW_UP else None
    s = Setup(
        Answer(status=status, speech_text="দুঃখিত।", display_text="দুঃখিত।", follow_up_question=follow_up)
    )
    s.ask()
    assert s.sms.sent == []
    assert s.checklists.rows == []


def test_a_voice_turn_without_a_call_sid_sends_nothing() -> None:
    s = Setup()
    s.ask(call_sid=None)
    assert s.sms.sent == []


def test_without_sms_and_runner_nothing_is_sent() -> None:
    s = Setup(wired=False)
    s.ask()
    assert s.sms.sent == []
    ((_, record),) = s.checklists.rows
    assert record.sms_sent is False  # not marked, because nothing was sent


# ---------------------------------------------------------------- sms_scheduled (TEAM_UPDATES 14)


def test_result_says_when_this_answer_queued_the_sms() -> None:
    s = Setup()
    assert s.ask().sms_scheduled is True  # first answer about the service: the call says SMS_SENT
    assert s.ask().sms_scheduled is False  # same service again: no SMS, so the call must not claim one


def test_result_says_no_sms_for_the_app_and_for_answers_without_a_checklist() -> None:
    assert Setup().ask(channel=Channel.APP, call_sid=None).sms_scheduled is False
    fallback = Answer(status=AnswerStatus.FALLBACK, speech_text="দুঃখিত।", display_text="দুঃখিত।")
    assert Setup(fallback).ask().sms_scheduled is False
    assert Setup(wired=False).ask().sms_scheduled is False


def test_result_still_says_scheduled_when_the_send_later_fails() -> None:
    # Queued is what the caller is told; a failed send is only logged (FR-SMS-05).
    assert Setup(sms=fakes.FakeSms(succeed=False)).ask().sms_scheduled is True


# ---------------------------------------------------------------- failures (FR-SMS-05)


def test_a_failed_send_does_not_break_the_answer_and_is_not_retried() -> None:
    s = Setup(sms=fakes.FakeSms(succeed=False))
    s.ask()  # no exception
    s.ask()
    assert len(s.sms.sent) == 1  # marked before sending, so the second turn does not try again


class RaisingSms:
    def send(self, phone: PhoneNumber, text: str) -> bool:
        raise RuntimeError("adapter bug")


def test_an_adapter_that_raises_does_not_break_the_answer(caplog: pytest.LogCaptureFixture) -> None:
    s = Setup(sms=RaisingSms())
    with caplog.at_level(logging.ERROR):
        s.ask()  # no exception
    assert any("SMS adapter raised" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------- privacy (NFR-PRIV-01)


def test_logs_never_contain_the_phone_number(caplog: pytest.LogCaptureFixture) -> None:
    s = Setup(sms=fakes.FakeSms(succeed=False))  # failure path logs too
    with caplog.at_level(logging.DEBUG):
        s.ask()
        s.ask()
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert logged  # something was logged
    assert E164 not in logged and PHONE not in logged and "1712345678" not in logged
