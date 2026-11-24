"""Two-service answers on the phone (sprint V1, FR-AGT-21, FR-CALL-03, FR-SMS-01)."""

import re

from app.application.agent import multi
from app.application.dto import AskResult
from app.application.use_cases.speech import HandleVoiceTurn
from app.domain import messages_bn
from app.domain.entities import Answer, Checklist, Citation, Message
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role
from app.interfaces.voice import twiml
from tests.fakes import InMemoryCallRepo, InMemoryConversationRepo

PHONE = "+8801712345678"
CFG = twiml.VoiceConfig(stt_language="bn-BD", tts_voice="Google.bn-IN-Standard-A", tts_language="bn-IN")
OLD, DIS = "old_age_allowance", "disability_allowance"
LONG = "এই সেবার জন্য " + "অনেক নিয়ম আছে " * 30
SPEECH = multi.build_speech(["বয়স্ক ভাতা", "প্রতিবন্ধী ভাতা"], [LONG, LONG], False, None, False, 60)
MULTI = Answer(
    AnswerStatus.ANSWERED, SPEECH, "দুটি", service_id=OLD,
    checklist=Checklist(OLD, "৬৫+", (), "বিনামূল্যে", "অফিস", "কমিটি"),
    citations=(Citation("নীতিমালা", "https://dss.gov.bd", "…", "c1"),),
    service_ids=(OLD, DIS), mode="multi",
)  # fmt: skip
FOLLOW_UP = Answer(
    AnswerStatus.FOLLOW_UP, "আপনার বাবা কি আগে থেকে কোনো ভাতা পান?", "",
    service_id="old_age_allowance,disability_allowance",
    follow_up_question="আপনার বাবা কি আগে থেকে কোনো ভাতা পান?",
)  # fmt: skip


class FakeAsk:
    def __init__(self, answer: Answer, sms_services: tuple[str, ...] = ()) -> None:
        self.answer, self.sms_services = answer, sms_services
        self.asked: list[str] = []

    def __call__(self, phone: str, text: str, channel: Channel, call_sid: str | None) -> AskResult:
        self.asked.append(text)
        return AskResult("c", self.answer, None, 900, bool(self.sms_services), self.sms_services)


def turn(ask: FakeAsk) -> tuple[HandleVoiceTurn, InMemoryConversationRepo]:
    conversations = InMemoryConversationRepo()
    return HandleVoiceTurn(ask, InMemoryCallRepo(), conversations), conversations


def test_multi_twiml_has_speech_two_sms_and_continue_inside_one_gather() -> None:
    handler, _ = turn(FakeAsk(MULTI, (OLD, DIS)))
    reply = handler.execute("CA1", PHONE, "আমার বাবার বয়স সত্তর, আবার চোখেও দেখেন না")
    assert reply.say == (SPEECH, messages_bn.TWO_SMS, messages_bn.CONTINUE) and not reply.hang_up
    xml = twiml.reply(CFG, reply.say, reply.hang_up)
    gathers = re.findall(r"<Gather.*?</Gather>", xml, flags=re.S)
    assert len(gathers) == 1
    for text in (SPEECH, messages_bn.TWO_SMS, messages_bn.CONTINUE):
        assert text in gathers[0]
    assert messages_bn.SMS_SENT not in xml and "<Hangup" not in xml


def test_one_sms_still_says_sms_sent() -> None:
    handler, _ = turn(FakeAsk(MULTI, (OLD,)))
    assert handler.execute("CA1", PHONE, "প্রশ্ন").say[1] == messages_bn.SMS_SENT


def test_multi_speech_is_at_most_60_words() -> None:
    assert len(SPEECH.split()) <= 60
    assert "বয়স্ক ভাতা" in SPEECH and "প্রতিবন্ধী ভাতা" in SPEECH


def test_follow_up_from_understand_keeps_the_call_alive() -> None:
    ask = FakeAsk(FOLLOW_UP)
    handler, conversations = turn(ask)
    first = handler.execute("CA1", PHONE, "বাবার বয়স সত্তর, চোখে দেখেন না")
    assert first.say == (FOLLOW_UP.speech_text,) and not first.hang_up and first.status == "follow_up"
    number = PhoneNumber.parse(PHONE)
    cid = conversations.get_or_create(number)
    conversations.add_message(cid, Message(Role.USER, Channel.VOICE, "বাবার বয়স সত্তর"))
    conversations.add_message(
        cid,
        Message(
            Role.ASSISTANT, Channel.VOICE, FOLLOW_UP.speech_text, FOLLOW_UP.service_id, AnswerStatus.FOLLOW_UP
        ),
    )
    ask.answer = MULTI
    second = handler.execute("CA1", PHONE, "না")  # "না" answers the question; it is not a goodbye
    assert not second.hang_up and ask.asked[-1] == "না"


def test_situation_words_are_in_the_speech_hints() -> None:
    for word in ("বিধবা", "প্রতিবন্ধী", "নামজারি", "ট্রেড লাইসেন্স", "দোকান"):
        assert word in twiml.SPEECH_HINTS.split(",")
    assert 'hints="' in twiml.greet(CFG)
