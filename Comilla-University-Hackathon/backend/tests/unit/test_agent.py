"""The agent (D1-T4, D1-T5): routing branches, steps and the whole LangGraph flow with fakes. No network.

FR-AGT-01 to 14, 17.
"""

import dataclasses
from collections.abc import Mapping
from typing import Any

import pytest

from app.application.agent import prompts, routing, steps
from app.application.agent.state import AgentState, merge_timings
from app.application.agent.steps import AgentDeps
from app.application.ports.llm import ModelRole
from app.application.ports.retrieval import Passage
from app.domain.entities import Message, Service
from app.domain.errors import ClassifierUnavailable, LLMUnavailable
from app.domain.messages_bn import DECISION_NOTE, FALLBACK
from app.domain.value_objects import AnswerStatus, Channel, Role, RouterSource
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from app.infrastructure.ml.llm_classifier import LLMClassifier
from tests.fakes import FakeClassifier, FakeLLM, FakeRetriever

SERVICES = {
    sid: Service(id=sid, name_bn=name, name_en=sid, office_bn="উপজেলা অফিস", sms_name=name)
    for sid, name in [("old_age_allowance", "বয়স্ক ভাতা"), ("widow_allowance", "বিধবা ভাতা"), ("other", "অন্যান্য")]
}
PASSAGES = [
    Passage("old_age_allowance-001", "old_age_allowance", "বয়স্ক ভাতা", "https://dss.gov.bd/a",
            "পুরুষের ক্ষেত্রে সর্বনিম্ন 65 বছর বয়স হতে হবে।", 0.9),
    Passage("old_age_allowance-002", "old_age_allowance", "বয়স্ক ভাতা", "https://dss.gov.bd/a",
            "জাতীয় পরিচয়পত্র লাগবে।", 0.88),
    Passage("old_age_allowance-003", "old_age_allowance", "নীতিমালা", "https://dss.gov.bd/b",
            "বাছাই কমিটি চূড়ান্ত করবে।", 0.85),
]  # fmt: skip

GOOD_DRAFT: dict[str, Any] = {
    "no_answer": False,
    "speech_text": "পুরুষের 65 বছর হলে আবেদন করা যায়।",
    "display_text": "**বয়স্ক ভাতা**\n- বয়স 65+",
    "checklist": {"who": "পুরুষ 65+", "papers": ["জাতীয় পরিচয়পত্র", " "], "fee": "", "where": "", "decision": ""},
    "claims": [
        {"text": "বয়স 65", "passage_ids": ["P1"], "core": True},
        {"text": "এনআইডি", "passage_ids": ["[P2]", "P9"], "core": True},
        {"text": "কমিটি", "passage_ids": ["P3"], "core": False},
    ],
    "follow_up_question": "",
}
NO_ANSWER: dict[str, Any] = {"no_answer": True, "speech_text": "", "display_text": "", "claims": []}
ALL_RELEVANT = {"relevant_ids": ["P1", "P2", "P3"]}
ALL_SUPPORTED = {"claims": [{"index": i, "supported": True} for i in range(3)], "speech_supported": True}


class StepLLM(FakeLLM):
    """Answers each agent step from its own queue, chosen by the JSON schema of the call."""

    def __init__(self, **queues: list[dict[str, Any]]) -> None:
        super().__init__(handler=self._answer)
        self.queues = {step: list(replies) for step, replies in queues.items()}
        self.steps: list[str] = []

    @staticmethod
    def step_of(schema: Mapping[str, Any]) -> str:
        keys = set(schema.get("properties", {}))
        for step, key in [("grade", "relevant_ids"), ("rewrite", "query"), ("verify", "speech_supported"),
                          ("generate", "no_answer"), ("classify", "service_id")]:  # fmt: skip
            if key in keys:
                return step
        raise AssertionError(f"unknown schema {keys}")

    def _answer(self, prompt: str, schema: Mapping[str, Any], role: ModelRole) -> dict[str, Any]:
        step = self.step_of(schema)
        self.steps.append(step)
        queue = self.queues.get(step) or []
        if not queue:
            raise AssertionError(f"no scripted reply left for {step}")
        return queue.pop(0) if len(queue) > 1 else queue[0]  # the last reply repeats


def deps(
    scores: dict[str, float] | None = None,
    llm: FakeLLM | None = None,
    passages: list[Passage] | None = None,
    classifier: Any = None,
    fast: bool = True,
) -> AgentDeps:
    return AgentDeps(
        classifier=classifier or FakeClassifier(scores or {"old_age_allowance": 0.95, "other": 0.05}),
        retriever=FakeRetriever(PASSAGES if passages is None else passages),
        llm=llm or StepLLM(grade=[ALL_RELEVANT], generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED]),
        services=SERVICES,
        confidence_threshold=0.7,
        max_retries=2,
        voice_fast_mode=fast,
        llm_backend="gemini",
    )


def user(text: str) -> Message:
    return Message(role=Role.USER, channel=Channel.APP, text=text)


def bot(text: str, status: AnswerStatus, service_id: str | None = "widow_allowance") -> Message:
    return Message(role=Role.ASSISTANT, channel=Channel.APP, text=text, service_id=service_id, status=status)


# ---------------------------------------------------------------- routing (SRS 7.4)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"pending_service_id": "widow_allowance", "service_id": "widow_allowance"}, routing.RETRIEVE),
        ({"service_id": "old_age_allowance", "confidence": 0.9}, routing.RETRIEVE),
        ({"service_id": "other", "confidence": 0.9}, routing.FALLBACK),  # FR-AGT-04
        ({"service_id": "old_age_allowance", "confidence": 0.5}, routing.LLM_CLASSIFY),  # FR-AGT-03
        ({"service_id": "other", "confidence": 0.5}, routing.LLM_CLASSIFY),
        ({"service_id": "old_age_allowance", "confidence": 0.3, "router_source": RouterSource.LLM},
         routing.RETRIEVE),  # the LLM router is never asked twice
    ],
)  # fmt: skip
def test_after_classify(state: AgentState, expected: str) -> None:
    assert routing.after_classify(state, threshold=0.7) == expected


def test_after_llm_classify() -> None:
    assert routing.after_llm_classify({"service_id": "other"}) == routing.FALLBACK
    assert routing.after_llm_classify({"service_id": "widow_allowance"}) == routing.RETRIEVE


def test_after_retrieve_skips_grading_only_in_fast_mode() -> None:
    assert routing.after_retrieve({}, fast_mode=True) == routing.GENERATE
    assert routing.after_retrieve({}, fast_mode=False) == routing.GRADE


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"relevant_ids": ["P1"]}, routing.GENERATE),
        ({"relevant_ids": [], "retries": 0}, routing.REWRITE_QUERY),  # FR-AGT-07
        ({"relevant_ids": [], "retries": 2}, routing.FALLBACK),
    ],
)
def test_after_grade(state: AgentState, expected: str) -> None:
    assert routing.after_grade(state, max_retries=2) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"draft": NO_ANSWER, "retries": 1}, routing.REWRITE_QUERY),
        ({"draft": NO_ANSWER, "retries": 2}, routing.FALLBACK),
        ({"draft": {"no_answer": False, "speech_text": "  "}, "retries": 2}, routing.FALLBACK),
        ({"draft": GOOD_DRAFT}, routing.VERIFY),
        ({"draft": {**GOOD_DRAFT, "follow_up_question": "আপনি কি স্থায়ী বাসিন্দা?"}}, routing.FINALIZE_FOLLOW_UP),
        ({"draft": {**GOOD_DRAFT, "follow_up_question": "আবার?"}, "pending_service_id": "widow_allowance"},
         routing.VERIFY),  # FR-AGT-09: only one follow-up
    ],
)  # fmt: skip
def test_after_generate(state: AgentState, expected: str) -> None:
    assert routing.after_generate(state, max_retries=2) == expected


def claim(core: bool, supported: bool) -> dict[str, Any]:
    return {"text": "x", "core": core, "supported": supported}


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"verified_claims": [claim(True, True), claim(False, False)], "speech_supported": True},
         routing.FINALIZE),
        ({"verified_claims": [claim(True, False)], "retries": 0}, routing.REWRITE_QUERY),  # FR-AGT-10
        ({"verified_claims": [claim(True, False)], "retries": 2}, routing.FALLBACK),
        ({"verified_claims": [claim(True, True)], "speech_supported": False, "retries": 2}, routing.FALLBACK),
        ({"verified_claims": [], "retries": 2}, routing.FALLBACK),  # nothing reliable left
    ],
)  # fmt: skip
def test_after_verify(state: AgentState, expected: str) -> None:
    assert routing.after_verify(state, max_retries=2) == expected


def test_timings_add_up_when_a_step_runs_twice() -> None:
    merged = merge_timings({"retrieve": 10.0}, {"retrieve": 5.5, "grade": 1.0})
    assert merged == {"retrieve": 15.5, "grade": 1.0}


# ---------------------------------------------------------------- steps


def test_classify_uses_the_router_and_keeps_the_top_3() -> None:
    d = deps(scores={"old_age_allowance": 0.6, "widow_allowance": 0.3, "other": 0.08, "x": 0.02})
    out = steps.classify({"question": "ভাতা", "history": []}, d)
    assert out["service_id"] == "old_age_allowance" and out["confidence"] == 0.6
    assert out["router_source"] is RouterSource.TFIDF
    assert [label for label, _ in out["candidates"]] == ["old_age_allowance", "widow_allowance", "other"]


def test_classify_keeps_the_service_of_a_pending_follow_up() -> None:  # FR-AGT-17
    history = [user("বিধবা ভাতার জন্য কী লাগে?"), bot("আপনি কি স্থায়ী বাসিন্দা?", AnswerStatus.FOLLOW_UP)]
    d = deps()
    out = steps.classify({"question": "হ্যাঁ", "history": history}, d)
    assert out["service_id"] == "widow_allowance" and out["router_source"] is RouterSource.CONTEXT
    assert out["query"] == "বিধবা ভাতার জন্য কী লাগে? হ্যাঁ"  # the short reply alone finds nothing
    assert d.classifier.texts == []  # type: ignore[attr-defined]


def test_an_answered_last_turn_is_not_a_pending_follow_up() -> None:
    history = [user("বিধবা ভাতা?"), bot("উত্তর", AnswerStatus.ANSWERED)]
    out = steps.classify({"question": "হ্যাঁ", "history": history}, deps())
    assert out["router_source"] is RouterSource.TFIDF


def test_classify_survives_a_missing_router_model() -> None:
    class Broken(FakeClassifier):
        def classify(self, text: str) -> list[tuple[str, float]]:
            raise ClassifierUnavailable("no model")

    out = steps.classify({"question": "ভাতা", "history": []}, deps(classifier=Broken({})))
    assert out["confidence"] == 0.0  # -> llm_classify decides
    assert routing.after_classify(out, 0.7) == routing.LLM_CLASSIFY  # type: ignore[arg-type]


def test_llm_classify_gets_hints_and_history_and_rejects_unknown_labels() -> None:
    llm = FakeLLM(
        [
            {"service_id": "widow_allowance", "confidence": 0.9},
            {"service_id": "nope", "confidence": 2},
        ]
    )
    d = deps(llm=llm)
    state: AgentState = {
        "question": "আর কী লাগে?", "history": [user("বিধবা ভাতা কী?")],
        "candidates": [("old_age_allowance", 0.4), ("widow_allowance", 0.35)],
    }  # fmt: skip
    out = steps.llm_classify(state, d)
    assert out == {"service_id": "widow_allowance", "confidence": 0.9,
                   "router_source": RouterSource.LLM, "llm_calls": 1}  # fmt: skip
    assert "old_age_allowance 0.40" in llm.prompts[0] and "বিধবা ভাতা কী?" in llm.prompts[0]
    assert steps.llm_classify(state, d)["service_id"] == "other"


def test_llm_classify_turns_a_context_question_into_a_standalone_query() -> None:
    llm = FakeLLM([{"service_id": "widow_allowance", "confidence": 0.85,
                    "search_query": "বিধবা ভাতার আবেদন কোথায় জমা দিতে হয়?"}])  # fmt: skip
    out = steps.llm_classify({"question": "আর কোথায় জমা দেবো?", "history": []}, deps(llm=llm))
    assert out["query"] == "বিধবা ভাতার আবেদন কোথায় জমা দিতে হয়?"


def test_retrieve_searches_the_chosen_service() -> None:
    d = deps()
    out = steps.retrieve({"question": "q", "query": "rewritten", "service_id": "old_age_allowance"}, d)
    assert len(out["passages"]) == 3
    assert d.retriever.searches == [  # type: ignore[attr-defined]
        ("rewritten", "old_age_allowance", 5),
        ("বয়স্ক ভাতা ফি কত টাকা", "old_age_allowance", 2),  # the fee passages, see the next test
    ]


class FeeRetriever:
    """The topic search finds no fee table; the fee search does."""

    def __init__(self, topic: list[Passage], fees: list[Passage]) -> None:
        self.topic, self.fees = topic, fees

    def search(self, query: str, service_id: str | None, k: int) -> list[Passage]:
        return list(self.fees if query.endswith("ফি কত টাকা") else self.topic)[:k]


def test_retrieve_adds_the_fee_passage_that_states_an_amount_without_duplicates() -> None:
    topic = [dataclasses.replace(PASSAGES[0], chunk_id="t-1", text="নাম সংশোধন করতে ফরম লাগে")]
    fee = dataclasses.replace(PASSAGES[1], chunk_id="t-fee", text="১ম বার: ফি ২০০ টাকা")
    no_amount = dataclasses.replace(PASSAGES[2], chunk_id="t-other", text="অফিসে যোগাযোগ করুন")
    d = dataclasses.replace(deps(), retriever=FeeRetriever(topic, [topic[0], fee, no_amount]))
    out = steps.retrieve({"question": "q", "service_id": "old_age_allowance"}, d)
    assert [p.chunk_id for p in out["passages"]] == ["t-1", "t-fee"] and out["fee_ids"] == ["t-fee"]


def test_grade_keeps_the_fee_passages_while_something_else_is_relevant() -> None:
    passages = [
        dataclasses.replace(PASSAGES[0], chunk_id="t-1"),
        dataclasses.replace(PASSAGES[1], chunk_id="t-fee"),
    ]
    state: AgentState = {"question": "q", "passages": passages, "fee_ids": ["t-fee"]}
    out = steps.grade(state, deps(llm=FakeLLM([{"relevant_ids": ["P1"]}])))
    assert [p.chunk_id for p in out["passages"]] == ["t-1", "t-fee"]
    nothing = steps.grade(state, deps(llm=FakeLLM([{"relevant_ids": []}])))
    assert nothing["relevant_ids"] == []  # a fee passage alone is not an answer: the query is rewritten


def test_grade_keeps_only_relevant_passages_and_renumbers_them() -> None:  # FR-AGT-06
    llm = FakeLLM([{"relevant_ids": ["[p3]", "P1", "P7"]}])
    out = steps.grade({"question": "q", "passages": PASSAGES}, deps(llm=llm))
    assert [p.chunk_id for p in out["passages"]] == ["old_age_allowance-001", "old_age_allowance-003"]
    assert out["relevant_ids"] == ["P1", "P2"] and out["llm_calls"] == 1
    assert llm.roles == [ModelRole.FAST]


def test_grade_without_passages_skips_the_llm() -> None:
    out = steps.grade({"question": "q", "passages": []}, deps(llm=FakeLLM(fail=True)))
    assert out == {"relevant_ids": []}


def test_rewrite_query_counts_a_retry_and_falls_back_to_the_question() -> None:  # FR-AGT-07
    llm = FakeLLM([{"query": "বয়স্ক ভাতার আবেদনের যোগ্যতা"}, {"query": "  "}])
    state: AgentState = {
        "question": "ভাতা কবে?", "service_id": "old_age_allowance", "retries": 1, "history": [],
    }  # fmt: skip
    assert steps.rewrite_query(state, deps(llm=llm)) == {
        "query": "বয়স্ক ভাতার আবেদনের যোগ্যতা", "retries": 2, "llm_calls": 1,
    }  # fmt: skip
    assert steps.rewrite_query(state, deps(llm=llm))["query"] == "ভাতা কবে?"


def test_verify_marks_each_claim_and_defaults_missing_verdicts_to_unsupported() -> None:  # FR-AGT-10
    llm = FakeLLM([{"claims": [{"index": 0, "supported": True}, {"index": 2, "supported": True}],
                    "speech_supported": True}])  # fmt: skip
    out = steps.verify({"draft": GOOD_DRAFT, "passages": PASSAGES}, deps(llm=llm))
    assert [c["supported"] for c in out["verified_claims"]] == [True, False, True]
    assert out["speech_supported"] is True and out["llm_calls"] == 1
    assert llm.roles == [ModelRole.MAIN]
    assert "0. বয়স 65" in llm.prompts[0] and "[P1]" in llm.prompts[0]


def test_verify_without_claims_is_not_reliable() -> None:
    out = steps.verify({"draft": {**GOOD_DRAFT, "claims": []}}, deps(llm=FakeLLM(fail=True)))
    assert out == {"verified_claims": [], "speech_supported": False}


def test_generate_without_passages_skips_the_llm() -> None:
    d = deps(llm=FakeLLM(fail=True))
    assert steps.generate({"question": "q", "passages": []}, d) == {"draft": {"no_answer": True}}


def test_generate_prompt_numbers_passages_and_leaves_the_sms_sentence_to_the_call() -> None:
    llm = FakeLLM([GOOD_DRAFT])
    state: AgentState = {"question": "বয়স?", "service_id": "old_age_allowance", "passages": PASSAGES,
                         "history": [], "channel": Channel.VOICE}  # fmt: skip
    assert steps.generate(state, deps(llm=llm))["llm_calls"] == 1
    assert "[P1] বয়স্ক ভাতা:" in llm.prompts[0] and "[P3] নীতিমালা:" in llm.prompts[0]
    assert "Do not mention SMS" in llm.prompts[0]  # speech.py says SMS_SENT only when one is queued


def test_finalize_builds_a_valid_answer() -> None:  # FR-AGT-08, 11, 12
    state: AgentState = {"draft": GOOD_DRAFT, "service_id": "old_age_allowance", "confidence": 0.95,
                         "router_source": RouterSource.TFIDF, "passages": PASSAGES}  # fmt: skip
    answer = steps.finalize(state, deps())["answer"]
    assert answer.status is AnswerStatus.ANSWERED
    assert answer.speech_text == "পুরুষের ৬৫ বছর হলে আবেদন করা যায়।"  # Bangla digits for speech
    assert DECISION_NOTE in answer.display_text
    assert answer.checklist.papers == ("জাতীয় পরিচয়পত্র",)
    assert answer.checklist.fee == steps.UNKNOWN_BN and answer.checklist.where == "উপজেলা অফিস"
    assert answer.checklist.decision == DECISION_NOTE
    # P1 and P2 are the same document -> one citation; P3 is another document; P9 does not exist.
    assert [c.source_url for c in answer.citations] == ["https://dss.gov.bd/a", "https://dss.gov.bd/b"]
    assert answer.llm_backend == "gemini"


def test_finalize_cites_only_passages_behind_supported_claims() -> None:
    verified = [{**c, "supported": i != 2} for i, c in enumerate(GOOD_DRAFT["claims"])]  # P3 claim dropped
    state: AgentState = {"draft": GOOD_DRAFT, "service_id": "old_age_allowance", "passages": PASSAGES,
                         "verified_claims": verified}  # fmt: skip
    citations = steps.finalize(state, deps())["answer"].citations
    assert [c.source_url for c in citations] == ["https://dss.gov.bd/a"]


def test_finalize_cites_the_best_passage_when_claims_cite_nothing() -> None:
    draft = {**GOOD_DRAFT, "claims": []}
    state: AgentState = {"draft": draft, "service_id": "old_age_allowance", "passages": PASSAGES}
    citations = steps.finalize(state, deps())["answer"].citations
    assert [c.chunk_id for c in citations] == ["old_age_allowance-001"]


def test_fallback_uses_the_exact_text_and_hides_other() -> None:  # FR-AGT-13
    answer = steps.fallback({"service_id": "other", "confidence": 0.9}, deps())["answer"]
    assert answer.status is AnswerStatus.FALLBACK
    assert answer.speech_text == FALLBACK == answer.display_text
    assert answer.service_id is None


# ---------------------------------------------------------------- the whole graph


def test_app_question_runs_grade_generate_verify() -> None:
    llm = StepLLM(grade=[ALL_RELEVANT], generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])
    answer = LangGraphAnswerEngine(deps(llm=llm)).answer("আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?", [], Channel.APP)
    assert answer.status is AnswerStatus.ANSWERED and answer.service_id == "old_age_allowance"
    assert llm.steps == ["grade", "generate", "verify"] and answer.llm_calls == 3
    assert set(answer.timings) == {
        "classify", "retrieve", "grade", "generate", "grounding_guard", "verify", "finalize", "total"
    }  # fmt: skip


def test_voice_fast_mode_uses_two_llm_calls() -> None:  # D1-T5 target
    llm = StepLLM(generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])
    answer = LangGraphAnswerEngine(deps(llm=llm)).answer("বয়স্ক ভাতা?", [], Channel.VOICE)
    assert answer.status is AnswerStatus.ANSWERED
    assert llm.steps == ["generate", "verify"] and answer.llm_calls == 2


def test_voice_grades_when_fast_mode_is_off() -> None:
    llm = StepLLM(grade=[ALL_RELEVANT], generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])
    LangGraphAnswerEngine(deps(llm=llm, fast=False)).answer("বয়স্ক ভাতা?", [], Channel.VOICE)
    assert llm.steps[0] == "grade"


def test_empty_grade_rewrites_and_retries_then_answers() -> None:
    llm = StepLLM(grade=[{"relevant_ids": []}, ALL_RELEVANT], rewrite=[{"query": "বয়স্ক ভাতার যোগ্যতা"}],
                  generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])  # fmt: skip
    d = deps(llm=llm)
    answer = LangGraphAnswerEngine(d).answer("ভাতা কবে পাবো?", [], Channel.APP)
    assert answer.status is AnswerStatus.ANSWERED
    assert llm.steps == ["grade", "rewrite", "grade", "generate", "verify"]
    queries = [q for q, _, _ in d.retriever.searches if not q.endswith("ফি কত টাকা")]  # type: ignore[attr-defined]
    assert queries == ["ভাতা কবে পাবো?", "বয়স্ক ভাতার যোগ্যতা"]


def test_gives_up_after_two_retries_with_the_exact_fallback() -> None:  # S7
    llm = StepLLM(grade=[{"relevant_ids": []}], rewrite=[{"query": "আবার খোঁজো"}])
    answer = LangGraphAnswerEngine(deps(llm=llm)).answer("বয়স্ক ভাতার অফিস কখন খোলে?", [], Channel.APP)
    assert answer.status is AnswerStatus.FALLBACK and answer.speech_text == FALLBACK
    assert llm.steps == ["grade", "rewrite", "grade", "rewrite", "grade"]  # one shared counter, max 2


def test_voice_no_answer_rewrites_like_an_empty_grade() -> None:
    llm = StepLLM(generate=[NO_ANSWER, GOOD_DRAFT], rewrite=[{"query": "বয়স্ক ভাতা"}], verify=[ALL_SUPPORTED])
    answer = LangGraphAnswerEngine(deps(llm=llm)).answer("ভাতা?", [], Channel.VOICE)
    assert answer.status is AnswerStatus.ANSWERED
    assert llm.steps == ["generate", "rewrite", "generate", "verify"]


def test_unsupported_core_claim_retries_then_falls_back() -> None:  # FR-AGT-10
    bad = {"claims": [{"index": 0, "supported": False}], "speech_supported": True}
    llm = StepLLM(grade=[ALL_RELEVANT], generate=[GOOD_DRAFT], verify=[bad], rewrite=[{"query": "q2"}])
    answer = LangGraphAnswerEngine(deps(llm=llm)).answer("বয়স্ক ভাতা?", [], Channel.APP)
    assert answer.status is AnswerStatus.FALLBACK
    assert llm.steps.count("verify") == 3 and llm.steps.count("rewrite") == 2


def test_other_goes_to_fallback_without_rag() -> None:
    d = deps(scores={"other": 0.9, "old_age_allowance": 0.1}, llm=FakeLLM(fail=True))
    answer = LangGraphAnswerEngine(d).answer("আজ বৃষ্টি হবে?", [], Channel.APP)
    assert answer.status is AnswerStatus.FALLBACK and answer.llm_calls == 0
    assert d.retriever.searches == []  # type: ignore[attr-defined]


def test_unsure_router_asks_the_llm_first() -> None:
    llm = StepLLM(classify=[{"service_id": "old_age_allowance", "confidence": 0.8}],
                  generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])  # fmt: skip
    d = deps(scores={"old_age_allowance": 0.4, "other": 0.35}, llm=llm)
    answer = LangGraphAnswerEngine(d).answer("ভাতা নিয়ে জানতে চাই", [], Channel.VOICE)
    assert answer.router_source is RouterSource.LLM and answer.llm_calls == 3
    assert llm.steps == ["classify", "generate", "verify"]


def test_follow_up_then_answer_keeps_the_service() -> None:  # S2
    follow = {**GOOD_DRAFT, "follow_up_question": "আপনি কি এই এলাকার স্থায়ী বাসিন্দা?"}
    llm = StepLLM(generate=[follow, GOOD_DRAFT], verify=[ALL_SUPPORTED])
    # every passage GOOD_DRAFT cites must exist, or grounding_guard drops the claim (FR-AGT-22)
    widow_passages = [dataclasses.replace(p, service_id="widow_allowance") for p in PASSAGES]
    engine = LangGraphAnswerEngine(
        deps(scores={"widow_allowance": 0.9, "other": 0.1}, llm=llm, passages=widow_passages)
    )
    first = engine.answer("বিধবা ভাতার জন্য কী লাগে?", [], Channel.VOICE)
    assert first.status is AnswerStatus.FOLLOW_UP and first.follow_up_question
    history = [user("বিধবা ভাতার জন্য কী লাগে?"), bot(first.speech_text, first.status)]
    second = engine.answer("হ্যাঁ", history, Channel.VOICE)
    assert second.status is AnswerStatus.ANSWERED and second.service_id == "widow_allowance"
    assert second.router_source is RouterSource.CONTEXT


def test_llm_errors_reach_the_caller() -> None:  # S9: the API turns it into the ERROR text
    with pytest.raises(LLMUnavailable):
        LangGraphAnswerEngine(deps(llm=FakeLLM(fail=True))).answer("বয়স্ক ভাতা?", [], Channel.APP)


# ---------------------------------------------------------------- LLM router (ROUTER_BACKEND=llm)


def test_llm_classifier_returns_all_labels_sorted() -> None:
    clf = LLMClassifier(FakeLLM([{"service_id": "widow_allowance", "confidence": 0.8}]), SERVICES)
    scores = clf.classify("স্বামী মারা গেছে, ভাতা পাবো?")
    assert clf.source is RouterSource.LLM
    assert scores[0] == ("widow_allowance", 0.8)
    assert {label for label, _ in scores} == set(SERVICES)
    assert sum(score for _, score in scores) == pytest.approx(1.0)


def test_classify_prompt_lists_every_label() -> None:
    prompt = prompts.build_classify_prompt("প্রশ্ন", SERVICES)
    assert all(f"- {sid}:" in prompt for sid in SERVICES)


def test_finalize_cuts_a_phone_answer_to_three_sentences_but_not_an_app_answer() -> None:
    long_speech = "এক। দুই। তিন। চার। পাঁচ।"
    draft = {**GOOD_DRAFT, "speech_text": long_speech}
    base: AgentState = {"draft": draft, "service_id": "old_age_allowance", "confidence": 0.95,
                        "router_source": RouterSource.TFIDF, "passages": PASSAGES, "verified_claims": [],
                        "speech_supported": True}  # fmt: skip
    voice = steps.finalize({**base, "channel": Channel.VOICE}, deps())
    app = steps.finalize({**base, "channel": Channel.APP}, deps())
    assert voice["answer"].speech_text == "এক। দুই। তিন।"
    assert app["answer"].speech_text == long_speech
