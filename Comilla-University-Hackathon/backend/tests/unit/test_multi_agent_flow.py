"""A whole two-service run through the LangGraph engine with fakes (sprint T5, FR-AGT-21, 22)."""

from typing import Any

from app.application.agent.steps import AgentDeps
from app.application.ports.retrieval import Passage
from app.domain.messages_bn import COMBINE_UNKNOWN, CONFLICT_NOTE
from app.domain.value_objects import AnswerStatus, Channel, RouterSource
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from tests.fakes import FakeClassifier, FakeRetriever
from tests.unit.test_situation_routing import SERVICES, SituationLLM

OLD, WIDOW = "old_age_allowance", "widow_allowance"
PASSAGES = [
    Passage("old-1", OLD, "বয়স্কভাতা নীতিমালা", "https://dss.gov.bd/old", "বয়স কমপক্ষে ৬৫ বছর।", 0.9),
    Passage("old-2", OLD, "বয়স্কভাতা নীতিমালা", "https://dss.gov.bd/old", "জাতীয় পরিচয়পত্র লাগবে।", 0.85),
    Passage("wid-1", WIDOW, "বিধবা ভাতা নীতিমালা", "https://dss.gov.bd/widow", "বয়স ১৮ বছরের বেশি।", 0.88),
    Passage("wid-2", WIDOW, "বিধবা ভাতা নীতিমালা", "https://dss.gov.bd/widow", "স্বামীর মৃত্যু সনদ লাগবে।", 0.8),
]
# retrieve groups passages per service (top 3 each): P1 old-1, P2 old-2, P3 wid-1, P4 wid-2
UNDERSTOOD = {
    "services": [OLD, WIDOW], "out_of_scope": False, "facts": {"age": "৬৬", "marital_status": "বিধবা"},
    "summary_bn": "বিধবা, বয়স ৬৬", "search_queries": {OLD: "বয়স্ক ভাতার যোগ্যতা", WIDOW: "বিধবা ভাতার যোগ্যতা"},
    "needs_follow_up": False,
}  # fmt: skip
MIXED_DRAFT: dict[str, Any] = {
    "no_answer": False,
    "sections": [
        {"service_id": OLD, "speech_text": "বয়স্ক ভাতায় বয়স ৬৫ বছর লাগে।", "display_text": "- বয়স ৬৫",
         "checklist": {"who": "৬৫ বছর", "papers": ["এনআইডি"], "fee": "", "where": "", "decision": ""},
         "claims": [{"text": "বয়স ৬৫", "service_id": OLD, "passage_ids": ["P1"], "core": True},
                    {"text": "এনআইডি", "service_id": OLD, "passage_ids": ["P2"], "core": False},
                    {"text": "মৃত্যু সনদ", "service_id": OLD, "passage_ids": ["P4"], "core": False}]},  # blended
        {"service_id": WIDOW, "speech_text": "বিধবা ভাতায় স্বামীর মৃত্যু সনদ লাগে।",
         "checklist": {"who": "১৮+", "papers": ["মৃত্যু সনদ"], "fee": "", "where": "", "decision": ""},
         "claims": [{"text": "মৃত্যু সনদ", "service_id": WIDOW, "passage_ids": ["P4"], "core": True}]},
    ],
    "conflicts": [{"topic_bn": "বয়সের শর্ত", "sides": [
        {"service_id": OLD, "rule_bn": "৬৫ বছর", "passage_ids": ["P1"]},
        {"service_id": WIDOW, "rule_bn": "১৮ বছরের বেশি", "passage_ids": ["P3"]}]}],
    "asks_combine": True,
    "combine_rule": {"stated": False},
    "follow_up_question": "",
}  # fmt: skip


def all_supported(prompt: str) -> dict[str, Any]:
    count = sum(
        1 for line in prompt.split("Claims:\n", 1)[1].split("\n\nSpoken answer")[0].splitlines() if line
    )
    return {"claims": [{"index": i, "supported": True} for i in range(count)], "speech_supported": True,
            "display_supported": True, "answers_question": True, "unsupported_checklist": []}  # fmt: skip


class MixedLLM(SituationLLM):
    def __init__(self) -> None:
        super().__init__(understand=[UNDERSTOOD], grade=[{"relevant_ids": ["P1", "P2", "P3", "P4"]}],
                         generate=[MIXED_DRAFT])  # fmt: skip
        self.verify_prompts: list[str] = []

    def _answer(self, prompt: str, schema: Any, role: Any) -> dict[str, Any]:
        if self.step_of(schema) == "verify":
            self.steps.append("verify")
            self.verify_prompts.append(prompt)
            return all_supported(prompt)
        return super()._answer(prompt, schema, role)


def engine(llm: MixedLLM) -> tuple[LangGraphAnswerEngine, FakeRetriever]:
    retriever = FakeRetriever(PASSAGES)
    d = AgentDeps(
        classifier=FakeClassifier({OLD: 0.7, WIDOW: 0.28, "other": 0.02}, source=RouterSource.BANGLABERT),
        retriever=retriever, llm=llm, services=SERVICES, confidence_threshold=0.7, situation_mode=True,
        query_expansion=True, multi_top_k=3, max_speech_words_multi=60, llm_backend="gemini",
    )  # fmt: skip
    return LangGraphAnswerEngine(d), retriever


def test_mixed_question_ends_in_a_grounded_multi_answer() -> None:
    llm = MixedLLM()
    eng, _ = engine(llm)
    answer = eng.answer("আমি বিধবা, বয়স ৬৬। বয়স্ক ভাতা আর বিধবা ভাতা দুটোই কি একসাথে পাবো?", [], Channel.APP)
    assert answer.status is AnswerStatus.ANSWERED and answer.mode == "multi"
    assert answer.router_source is RouterSource.SITUATION
    assert answer.service_ids == (OLD, WIDOW) and answer.service_id == OLD
    assert [c.service_id for c in answer.checklists] == [
        OLD,
        WIDOW,
    ] and answer.checklist == answer.checklists[0]
    assert len(answer.conflicts) == 1
    sides = answer.conflicts[0].sides
    assert [(s.service_id, s.source_url) for s in sides] == [
        (OLD, "https://dss.gov.bd/old"), (WIDOW, "https://dss.gov.bd/widow"),
    ]  # fmt: skip
    retrieved = {p.source_url for p in PASSAGES}
    assert answer.citations and {c.source_url for c in answer.citations} <= retrieved
    assert CONFLICT_NOTE in answer.speech_text and COMBINE_UNKNOWN in answer.speech_text
    assert len(answer.speech_text.split()) <= 60
    assert "নিয়ম আলাদা" in answer.display_text
    assert answer.situation is not None and answer.situation.summary_bn == "বিধবা, বয়স ৬৬"
    assert llm.steps == ["understand", "grade", "generate", "verify"]


def test_the_blended_claim_never_reaches_the_verifier() -> None:
    llm = MixedLLM()
    engine(llm)[0].answer("বিধবা, বয়স ৬৬, দুটো ভাতা?", [], Channel.APP)
    old_claims = [
        line for line in llm.verify_prompts[0].splitlines() if line[:2].strip().rstrip(".").isdigit()
    ]
    assert not any("বয়স্ক ভাতা] মৃত্যু সনদ" in line for line in old_claims)


def test_each_service_is_searched_with_its_own_filter() -> None:
    eng, retriever = engine(MixedLLM())
    eng.answer("বিধবা, বয়স ৬৬, দুটো ভাতা?", [], Channel.APP)
    assert {sid for _, sid, _ in retriever.searches} == {OLD, WIDOW}
    assert ("বিধবা ভাতার যোগ্যতা", WIDOW, 3) in retriever.searches


def test_verify_sees_the_fixed_notes_so_an_honest_unknown_counts_as_an_answer() -> None:
    llm = MixedLLM()
    engine(llm)[0].answer("বিধবা, বয়স ৬৬, দুটো ভাতা একসাথে?", [], Channel.APP)
    prompt = llm.verify_prompts[0]
    assert COMBINE_UNKNOWN in prompt and CONFLICT_NOTE in prompt
    assert "covers TWO services" in prompt


def test_a_checked_direct_answer_leads_the_speech_and_cites_its_source() -> None:
    first = "আগে বয়স্ক ভাতার নিয়ম দেখুন, কারণ বয়স ৬৫ বছর লাগে।"
    draft = {**MIXED_DRAFT, "direct_answer": {"stated": True, "text_bn": first, "passage_ids": ["P1"]}}
    llm = MixedLLM()
    llm.queues["generate"] = [draft]
    answer = engine(llm)[0].answer("কোনটা আগে করবো?", [], Channel.APP)
    assert answer.status is AnswerStatus.ANSWERED and answer.mode == "multi"
    assert answer.speech_text.split("। ", 1)[1].startswith(first)  # right after the intro
    assert first in answer.display_text and len(answer.speech_text.split()) <= 60
    assert first in llm.verify_prompts[0]  # checked like every other claim
    assert "https://dss.gov.bd/old" in {c.source_url for c in answer.citations}
