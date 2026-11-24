import dataclasses

import pytest

from app.domain.entities import Answer, Checklist, Citation, Message
from app.domain.value_objects import AnswerStatus, Channel, Role, RouterSource

CHECKLIST = Checklist(
    service_id="old_age_allowance",
    who="পুরুষ ৬৫+, নারী ৬২+",
    papers=("জাতীয় পরিচয়পত্র",),
    fee="বিনামূল্যে",
    where="উপজেলা সমাজসেবা অফিস",
    decision="স্থানীয় বাছাই কমিটি",
)
CITATION = Citation(
    title="বয়স্ক ভাতা কার্যক্রম",
    source_url="https://example.gov.bd",
    snippet="...",
    chunk_id="old_age_allowance-001",
)


def answered(**overrides) -> Answer:
    values = dict(
        status=AnswerStatus.ANSWERED,
        speech_text="কথা",
        display_text="লেখা",
        service_id="old_age_allowance",
        confidence=0.9,
        router_source=RouterSource.TFIDF,
        checklist=CHECKLIST,
        citations=(CITATION,),
    )
    values.update(overrides)
    return Answer(**values)


def test_valid_answered_answer() -> None:
    answer = answered()
    assert answer.checklist is not None
    assert answer.checklist.papers == ("জাতীয় পরিচয়পত্র",)


def test_entities_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        answered().speech_text = "changed"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        CHECKLIST.fee = "১০০ টাকা"  # type: ignore[misc]


@pytest.mark.parametrize("missing", ["service_id", "checklist", "citations"])
def test_answered_needs_service_checklist_and_citations(missing: str) -> None:
    empty = () if missing == "citations" else None
    with pytest.raises(ValueError):
        answered(**{missing: empty})


def test_fallback_answer_needs_no_checklist() -> None:
    answer = Answer(status=AnswerStatus.FALLBACK, speech_text="দুঃখিত", display_text="দুঃখিত")
    assert answer.checklist is None and answer.citations == ()


def test_follow_up_needs_a_question() -> None:
    with pytest.raises(ValueError):
        Answer(status=AnswerStatus.FOLLOW_UP, speech_text="x", display_text="x")
    ok = Answer(
        status=AnswerStatus.FOLLOW_UP,
        speech_text="আপনি কি স্থায়ী বাসিন্দা?",
        display_text="আপনি কি স্থায়ী বাসিন্দা?",
        follow_up_question="আপনি কি স্থায়ী বাসিন্দা?",
    )
    assert ok.follow_up_question


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_confidence_must_be_between_0_and_1(bad: float) -> None:
    with pytest.raises(ValueError):
        answered(confidence=bad)


def test_message_gets_a_timezone_aware_timestamp() -> None:
    msg = Message(role=Role.USER, channel=Channel.APP, text="বয়স্ক ভাতা")
    assert msg.created_at.tzinfo is not None
