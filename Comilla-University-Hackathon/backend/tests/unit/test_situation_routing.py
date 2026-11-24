"""Sprint T3: the `understand` step and situation routing (FR-AGT-19, 23). Fakes only, no network."""

import dataclasses
from typing import Any

import pytest

from app.application.agent import prompts, routing, steps
from app.application.agent.steps import AgentDeps
from app.domain.entities import Message, Service
from app.domain.messages_bn import FALLBACK
from app.domain.value_objects import AnswerStatus, Channel, Role, RouterSource
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from tests.fakes import FakeClassifier, FakeRetriever
from tests.unit.test_agent import ALL_RELEVANT, ALL_SUPPORTED, GOOD_DRAFT, PASSAGES, StepLLM

SERVICES = {
    sid: Service(
        id=sid, name_bn=name, name_en=sid, office_bn="উপজেলা অফিস", sms_name=name, search_terms_bn=terms
    )
    for sid, name, terms in [
        ("old_age_allowance", "বয়স্ক ভাতা", "বয়স্কভাতা বয়স"),
        ("widow_allowance", "বিধবা ভাতা", "বিধবা স্বামী"),
        ("other", "অন্যান্য", ""),
    ]
}
SITUATION = routing.SituationRouting(enabled=True, multi_min_prob=0.25)
WIDOW_UNDERSTOOD: dict[str, Any] = {
    "services": ["widow_allowance"], "out_of_scope": False,
    "facts": {"marital_status": "বিধবা", "age": "66"}, "summary_bn": "স্বামী মারা গেছেন, বয়স 66",
    "search_queries": {"widow_allowance": "বিধবা ভাতা যোগ্যতা ও কাগজ"},
    "needs_follow_up": False, "follow_up_question": "",
}  # fmt: skip
OUT_OF_SCOPE = {
    "services": [],
    "out_of_scope": True,
    "summary_bn": "",
    "search_queries": {},
    "needs_follow_up": False,
}


class SituationLLM(StepLLM):
    """StepLLM that also knows the `understand` schema."""

    @staticmethod
    def step_of(schema: Any) -> str:
        if "out_of_scope" in schema.get("properties", {}):
            return "understand"
        return StepLLM.step_of(schema)


def deps(scores: dict[str, float], llm: StepLLM, situation_mode: bool = True) -> AgentDeps:
    return AgentDeps(
        classifier=FakeClassifier(scores, source=RouterSource.BANGLABERT),
        retriever=FakeRetriever(PASSAGES),
        llm=llm,
        services=SERVICES,
        confidence_threshold=0.7,
        max_retries=2,
        llm_backend="gemini",
        situation_mode=situation_mode,
        query_expansion=True,
    )


def run(question: str, d: AgentDeps, history: list[Message] | None = None) -> Any:
    return LangGraphAnswerEngine(d).answer(question, history or [], Channel.APP)


def answer_llm(understood: dict[str, Any] | None = None) -> SituationLLM:
    queues: dict[str, list[dict[str, Any]]] = {
        "grade": [ALL_RELEVANT], "generate": [GOOD_DRAFT], "verify": [ALL_SUPPORTED],
    }  # fmt: skip
    if understood is not None:
        queues["understand"] = [understood]
    return SituationLLM(**queues)


# ---------------------------------------------------------------- routing rules


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"service_id": "old_age_allowance", "confidence": 0.95,
          "candidates": [("old_age_allowance", 0.95), ("other", 0.05)]}, routing.RETRIEVE),
        ({"service_id": "old_age_allowance", "confidence": 0.5}, routing.UNDERSTAND),
        ({"service_id": "other", "confidence": 0.9}, routing.UNDERSTAND),
        ({"service_id": "old_age_allowance", "confidence": 0.7,
          "candidates": [("old_age_allowance", 0.7), ("widow_allowance", 0.25)]}, routing.UNDERSTAND),
        ({"service_id": "old_age_allowance", "confidence": 0.7,
          "candidates": [("old_age_allowance", 0.7), ("other", 0.3)]}, routing.RETRIEVE),  # 2nd is `other`
        ({"service_id": "old_age_allowance", "confidence": 0.3, "router_source": RouterSource.LLM},
         routing.RETRIEVE),  # the LLM router is never asked twice
        ({"pending_service_id": "widow_allowance", "service_id": "widow_allowance"}, routing.RETRIEVE),
    ],
)  # fmt: skip
def test_after_classify_in_situation_mode(state: dict[str, Any], expected: str) -> None:
    assert routing.after_classify(state, 0.7, SITUATION) == expected  # type: ignore[arg-type]


def test_situation_mode_off_keeps_the_old_routes() -> None:
    assert routing.after_classify({"service_id": "other", "confidence": 0.9}, 0.7) == routing.FALLBACK
    assert routing.after_classify({"service_id": "x", "confidence": 0.5}, 0.7) == routing.LLM_CLASSIFY


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"service_id": "widow_allowance"}, routing.RETRIEVE),
        ({"service_id": "other"}, routing.FALLBACK),
        ({"service_id": None}, routing.FALLBACK),
        ({"service_id": "other", "follow_up": "আপনার বয়স কত?"}, routing.FINALIZE_FOLLOW_UP),
    ],
)
def test_after_understand(state: dict[str, Any], expected: str) -> None:
    assert routing.after_understand(state) == expected  # type: ignore[arg-type]


# ---------------------------------------------------------------- whole flow


def test_confident_single_label_does_not_call_understand() -> None:
    llm = answer_llm()
    answer = run("বয়স্ক ভাতা কী?", deps({"old_age_allowance": 0.95, "other": 0.05}, llm))
    assert "understand" not in llm.steps
    assert answer.status is AnswerStatus.ANSWERED and answer.router_source is RouterSource.BANGLABERT


def test_low_confidence_calls_understand_once_and_uses_its_service() -> None:
    llm = answer_llm(WIDOW_UNDERSTOOD)
    d = deps({"old_age_allowance": 0.4, "widow_allowance": 0.35, "other": 0.25}, llm)
    d.retriever.passages = [p.__class__(**{**p.__dict__, "service_id": "widow_allowance"}) for p in PASSAGES]
    answer = run("স্বামী মারা গেছেন, বয়স ৬৬, সংসার চলে না", d)
    assert llm.steps.count("understand") == 1
    assert answer.status is AnswerStatus.ANSWERED
    assert answer.service_id == "widow_allowance" and answer.router_source is RouterSource.SITUATION
    assert answer.situation is not None and answer.situation.summary_bn == "স্বামী মারা গেছেন, বয়স ৬৬"
    assert dict(answer.situation.facts)["marital_status"] == "বিধবা"
    assert "বিধবা ভাতা যোগ্যতা ও কাগজ" in [q for q, _, _ in d.retriever.searches]  # understand's query


def test_other_label_plus_understand_service_is_answered_not_fallback() -> None:
    llm = answer_llm({**WIDOW_UNDERSTOOD, "services": ["old_age_allowance"], "search_queries": {}})
    answer = run("বয়স হয়ে গেছে, রিকশা চালাতে পারি না", deps({"other": 0.8, "old_age_allowance": 0.2}, llm))
    assert answer.status is AnswerStatus.ANSWERED and answer.service_id == "old_age_allowance"


def test_other_label_plus_out_of_scope_gives_the_exact_fallback() -> None:
    llm = answer_llm(OUT_OF_SCOPE)
    answer = run("গরুর পা ফুলে গেছে, কী করবো?", deps({"other": 0.9, "old_age_allowance": 0.1}, llm))
    assert answer.status is AnswerStatus.FALLBACK and answer.speech_text == FALLBACK
    assert llm.steps == ["understand"]


def test_out_of_scope_beats_a_follow_up_question() -> None:
    llm = answer_llm({**OUT_OF_SCOPE, "needs_follow_up": True, "follow_up_question": "কোন জেলা?"})
    answer = run("ধানে পোকা লেগেছে", deps({"other": 0.9}, llm))
    assert answer.status is AnswerStatus.FALLBACK


def test_second_likely_service_gives_multi_mode() -> None:
    llm = answer_llm({**WIDOW_UNDERSTOOD, "services": ["old_age_allowance", "widow_allowance"]})
    d = deps({"old_age_allowance": 0.7, "widow_allowance": 0.28, "other": 0.02}, llm)
    start: dict[str, Any] = {"question": "বিধবা, বয়স ৬৬", "channel": Channel.APP}
    classified = {**start, **steps.classify(start, d)}  # type: ignore[arg-type]
    out = steps.understand(classified, d)  # type: ignore[arg-type]
    assert out["mode"] == "multi" and out["service_ids"] == ["old_age_allowance", "widow_allowance"]
    assert out["cache_key"] == ""  # situation and multi answers are never cached
    assert routing.after_classify(classified, 0.7, SITUATION) == routing.UNDERSTAND  # type: ignore[arg-type]


def test_unknown_labels_from_the_llm_are_ignored() -> None:
    llm = answer_llm(
        {**WIDOW_UNDERSTOOD, "services": ["pension_scheme", "other", "widow_allowance", "widow_allowance"]}
    )
    d = deps({"other": 0.9}, llm)
    start: dict[str, Any] = {"question": "q", "channel": Channel.APP}
    out = steps.understand({**start, **steps.classify(start, d)}, d)  # type: ignore[arg-type]
    assert out["service_ids"] == ["widow_allowance"] and out["mode"] == "single"


def test_only_unknown_labels_means_fallback() -> None:
    llm = answer_llm({**WIDOW_UNDERSTOOD, "services": ["pension_scheme"]})
    answer = run("পেনশন", deps({"other": 0.9}, llm))
    assert answer.status is AnswerStatus.FALLBACK


def test_vague_question_gets_one_follow_up_without_a_guess() -> None:
    vague = {**OUT_OF_SCOPE, "out_of_scope": False, "needs_follow_up": True,
             "follow_up_question": "আপনার বয়স কত, আর পরিবারে কেউ বিধবা বা প্রতিবন্ধী আছেন?"}  # fmt: skip
    llm = answer_llm(vague)
    answer = run("আমি খুব গরিব, সরকার থেকে কি কিছু পাওয়া যায়?", deps({"other": 0.6, "old_age_allowance": 0.3}, llm))
    assert answer.status is AnswerStatus.FOLLOW_UP and answer.service_id is None
    assert answer.follow_up_question and "বয়স" in answer.follow_up_question


def test_no_second_follow_up_after_one_was_asked() -> None:
    history = [
        Message(role=Role.USER, channel=Channel.APP, text="আমি খুব গরিব"),
        Message(role=Role.ASSISTANT, channel=Channel.APP, text="বয়স কত?", status=AnswerStatus.FOLLOW_UP),
    ]
    llm = answer_llm({**WIDOW_UNDERSTOOD, "needs_follow_up": True, "follow_up_question": "আবার?"})
    d = deps({"old_age_allowance": 0.5, "other": 0.5}, llm)
    d.retriever.passages = [p.__class__(**{**p.__dict__, "service_id": "widow_allowance"}) for p in PASSAGES]
    answer = run("আমি বিধবা", d, history)
    assert answer.status is AnswerStatus.ANSWERED
    assert "ALREADY asked" in llm.prompts[0]


def test_two_service_follow_up_keeps_both_for_the_next_turn() -> None:
    both = {**WIDOW_UNDERSTOOD, "services": ["old_age_allowance", "widow_allowance"], "needs_follow_up": True,
            "follow_up_question": "আপনি কি বয়স্ক ভাতা আগে থেকে পান?"}  # fmt: skip
    answer = run("বিধবা, বয়স ৬৬", deps({"old_age_allowance": 0.5, "widow_allowance": 0.45}, answer_llm(both)))
    assert answer.status is AnswerStatus.FOLLOW_UP
    assert answer.service_id == "old_age_allowance,widow_allowance"
    reply_history = [
        Message(role=Role.USER, channel=Channel.APP, text="বিধবা, বয়স ৬৬"),
        Message(role=Role.ASSISTANT, channel=Channel.APP, text="?", service_id=answer.service_id,
                status=AnswerStatus.FOLLOW_UP),
    ]  # fmt: skip
    d = deps({"other": 1.0}, answer_llm())
    state = steps.classify({"question": "না", "history": reply_history, "channel": Channel.APP}, d)
    assert state["service_ids"] == ["old_age_allowance", "widow_allowance"] and state["mode"] == "multi"
    assert routing.after_classify(state, 0.7, SITUATION) == routing.RETRIEVE


def test_understand_prompt_lists_services_with_official_words_and_no_other() -> None:
    text = prompts.build_understand_prompt("প্রশ্ন", SERVICES, [("other", 0.6)])
    assert "widow_allowance: বিধবা ভাতা (widow_allowance) - বিধবা স্বামী" in text
    assert "- other:" not in text and "other 0.60" in text


# ---------------------------------------------------------------- hint router (T6)

CONFIDENT_OLD: dict[str, Any] = {
    "service_id": "old_age_allowance", "confidence": 0.9,
    "candidates": [("old_age_allowance", 0.9), ("widow_allowance", 0.05)],
}  # fmt: skip


def test_hint_router_agreeing_keeps_the_fast_path() -> None:
    state = {**CONFIDENT_OLD, "hint_candidates": [("old_age_allowance", 0.8), ("widow_allowance", 0.1)]}
    assert routing.after_classify(state, 0.7, SITUATION) == routing.RETRIEVE  # type: ignore[arg-type]


def test_hint_router_disagreeing_or_seeing_a_second_service_runs_understand() -> None:
    other_top = {
        **CONFIDENT_OLD,
        "hint_candidates": [("disability_allowance", 0.5), ("old_age_allowance", 0.4)],
    }
    second = {
        **CONFIDENT_OLD,
        "hint_candidates": [("old_age_allowance", 0.5), ("disability_allowance", 0.35)],
    }
    for state in (other_top, second):
        assert routing.after_classify(state, 0.7, SITUATION) == routing.UNDERSTAND  # type: ignore[arg-type]


def test_hint_router_is_ignored_when_situation_mode_is_off() -> None:
    state = {**CONFIDENT_OLD, "hint_candidates": [("disability_allowance", 0.9)]}
    assert routing.after_classify(state, 0.7) == routing.RETRIEVE  # type: ignore[arg-type]


def test_classify_adds_hint_candidates_and_understand_sees_them() -> None:
    llm = answer_llm({**WIDOW_UNDERSTOOD, "services": ["old_age_allowance"]})
    d = dataclasses.replace(
        deps({"old_age_allowance": 0.9, "other": 0.1}, llm),
        hint_classifier=FakeClassifier({"widow_allowance": 0.6, "old_age_allowance": 0.4}),
    )
    start: dict[str, Any] = {"question": "বয়স ৭০, স্বামী নেই", "channel": Channel.APP}
    state = {**start, **steps.classify(start, d)}  # type: ignore[arg-type]
    assert state["hint_candidates"][0] == ("widow_allowance", 0.6)
    assert routing.after_classify(state, 0.7, SITUATION) == routing.UNDERSTAND  # type: ignore[arg-type]
    steps.understand(state, d)  # type: ignore[arg-type]
    assert "widow_allowance 0.60" in llm.prompts[0]


def test_unsure_hint_router_runs_understand_for_a_vague_question() -> None:
    vague = {
        "service_id": "disability_allowance", "confidence": 0.87,
        "candidates": [("disability_allowance", 0.87), ("old_age_allowance", 0.05)],
        "hint_candidates": [("disability_allowance", 0.34), ("other", 0.24), ("widow_allowance", 0.22)],
    }  # fmt: skip
    assert routing.after_classify(vague, 0.7, SITUATION) == routing.UNDERSTAND  # type: ignore[arg-type]
    sure = {**vague, "hint_candidates": [("disability_allowance", 0.6), ("other", 0.24)]}
    assert routing.after_classify(sure, 0.7, SITUATION) == routing.RETRIEVE  # type: ignore[arg-type]
    no_rule = routing.SituationRouting(enabled=True, multi_min_prob=0.25, hint_min_confidence=0.0)
    assert routing.after_classify(vague, 0.7, no_rule) == routing.RETRIEVE  # type: ignore[arg-type]
