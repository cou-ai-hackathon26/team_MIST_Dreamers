"""Temporary AnswerEngine: always returns the same Old Age Allowance answer (D1-A2).

It lets the API and the frontend be built before the real agent exists (replaced in D1-T4).
"""

from collections.abc import Sequence

from app.domain.entities import Answer, Checklist, Citation, Message
from app.domain.messages_bn import DECISION_NOTE
from app.domain.value_objects import AnswerStatus, Channel

_CHECKLIST = Checklist(
    service_id="old_age_allowance",
    who="পুরুষ ৬৫+, নারী ৬২+, স্থায়ী বাসিন্দা",
    papers=("জাতীয় পরিচয়পত্র বা জন্ম নিবন্ধন",),
    fee="বিনামূল্যে",
    where="অনলাইনে বা উপজেলা সমাজসেবা অফিসে",
    decision="স্থানীয় বাছাই কমিটি",
)
_CITATION = Citation(
    title="বয়স্ক ভাতা কার্যক্রম (নমুনা উত্তর)",
    source_url="https://dss.gov.bd/",
    snippet="এটি পরীক্ষার জন্য একটি নির্দিষ্ট নমুনা উত্তর।",
    chunk_id="old_age_allowance-000",
)


class StubAnswerEngine:
    def answer(self, question: str, history: Sequence[Message], channel: Channel) -> Answer:
        speech = "পুরুষদের ৬৫ বছর হলে আবেদন করা যায়, আর আবেদন সম্পূর্ণ বিনামূল্যে। জাতীয় পরিচয়পত্র লাগবে।"
        display = (
            "**বয়স্ক ভাতা** (নমুনা উত্তর, পরীক্ষার জন্য: AGENT_ENGINE=stub)\n"
            "- কারা: পুরুষ ৬৫+, নারী ৬২+, স্থায়ী বাসিন্দা\n"
            "- লাগবে: জাতীয় পরিচয়পত্র বা জন্ম নিবন্ধন\n"
            "- ফি: বিনামূল্যে\n"
            f"\n_{DECISION_NOTE}_"
        )
        return Answer(
            status=AnswerStatus.ANSWERED,
            speech_text=speech,
            display_text=display,
            service_id="old_age_allowance",
            confidence=1.0,
            checklist=_CHECKLIST,
            citations=(_CITATION,),
            llm_calls=0,
            llm_backend="stub",
        )
