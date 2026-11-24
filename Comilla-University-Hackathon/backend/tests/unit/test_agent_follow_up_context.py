"""A short question after an answer ("আর কোথায় জমা দেবো?") must not be routed by the local router alone."""

import dataclasses

from app.application.agent import routing, steps
from app.application.agent.state import AgentState
from app.domain.value_objects import AnswerStatus, Channel, RouterSource
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from tests.fakes import InMemoryAnswerCache
from tests.unit.test_agent import ALL_RELEVANT, ALL_SUPPORTED, GOOD_DRAFT, PASSAGES, StepLLM, bot, deps, user

WIDOW_TALK = [user("বিধবা ভাতার জন্য কী লাগে?"), bot("উত্তর", AnswerStatus.ANSWERED, "widow_allowance")]
SHORT = "আর কোথায় জমা দেবো?"
CONFIDENT_WRONG = {"old_age_allowance": 0.95, "other": 0.05}  # the local router guesses another service


def state_for(question: str, history: list) -> AgentState:
    return {"question": question, "history": history, "channel": Channel.APP}


def test_short_question_after_another_service_needs_the_llm_and_is_never_cached() -> None:
    d = dataclasses.replace(deps(scores=CONFIDENT_WRONG), cache=InMemoryAnswerCache())
    out = steps.classify(state_for(SHORT, WIDOW_TALK), d)
    assert out["needs_context"] is True and "cache_key" not in out
    assert routing.after_classify({**state_for(SHORT, WIDOW_TALK), **out}, 0.7) == routing.LLM_CLASSIFY


def test_the_llm_decision_is_final_for_a_short_question() -> None:
    state: AgentState = {"needs_context": True, "service_id": "widow_allowance", "confidence": 0.9,
                         "router_source": RouterSource.LLM}  # fmt: skip
    assert routing.after_classify(state, 0.7) == routing.RETRIEVE


def test_no_context_rule_when_the_router_agrees_or_the_question_is_long_or_there_is_no_history() -> None:
    d = deps(scores={"widow_allowance": 0.95, "other": 0.05})
    assert "needs_context" not in steps.classify(state_for(SHORT, WIDOW_TALK), d)  # same service
    long_question = "বয়স্ক ভাতা পেতে হলে আবেদন কোথায় জমা দিতে হবে এবং কী কী লাগবে"
    assert "needs_context" not in steps.classify(
        state_for(long_question, WIDOW_TALK), deps(scores=CONFIDENT_WRONG)
    )
    assert "needs_context" not in steps.classify(state_for(SHORT, []), deps(scores=CONFIDENT_WRONG))


def test_a_fallback_turn_is_not_a_context_for_the_next_question() -> None:
    history = [user("আজ বৃষ্টি হবে?"), bot("দুঃখিত", AnswerStatus.FALLBACK, None)]
    assert steps.previous_service(history) is None
    assert "needs_context" not in steps.classify(state_for(SHORT, history), deps(scores=CONFIDENT_WRONG))


def test_end_to_end_the_follow_up_stays_on_widow_allowance() -> None:
    standalone = "বিধবা ভাতার আবেদন কোথায় জমা দিতে হয়?"
    llm = StepLLM(
        classify=[{"service_id": "widow_allowance", "confidence": 0.9, "search_query": standalone}],
        grade=[ALL_RELEVANT],
        generate=[GOOD_DRAFT],
        verify=[ALL_SUPPORTED],
    )
    d = deps(
        scores=CONFIDENT_WRONG,
        llm=llm,
        passages=[dataclasses.replace(p, service_id="widow_allowance") for p in PASSAGES],
    )
    answer = LangGraphAnswerEngine(d).answer(SHORT, WIDOW_TALK, Channel.APP)
    assert answer.service_id == "widow_allowance" and answer.router_source is RouterSource.LLM
    assert llm.steps[0] == "classify" and answer.status is AnswerStatus.ANSWERED
    assert d.retriever.searches[0][0] == standalone  # type: ignore[attr-defined]


def test_an_answer_to_another_question_is_not_given_even_when_its_facts_are_supported() -> None:
    claims = [{"supported": True, "core": True}]
    state: AgentState = {"answers_question": False, "verified_claims": claims, "speech_supported": True}
    assert routing.after_verify(state, 2) == routing.FALLBACK
    assert routing.after_verify({**state, "answers_question": True}, 2) == routing.FINALIZE
