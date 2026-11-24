"""Answer cache inside the agent (D2-T4, FR-AGT-15). Fakes only, no network."""

import dataclasses
from typing import Any

import pytest

from app.application.agent import routing, steps
from app.application.agent.cache_key import cache_key, normalize_question
from app.application.agent.state import AgentState
from app.domain.value_objects import AnswerStatus, Channel, RouterSource
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from tests.fakes import FakeClassifier, FakeLLM, InMemoryAnswerCache
from tests.unit.test_agent import (
    ALL_RELEVANT,
    ALL_SUPPORTED,
    GOOD_DRAFT,
    NO_ANSWER,
    StepLLM,
    bot,
    deps,
    user,
)

QUESTION = "বয়স্ক ভাতা কত টাকা?"


def cached_deps(cache: InMemoryAnswerCache, llm: FakeLLM | None = None, **kwargs: Any) -> steps.AgentDeps:
    llm = llm or StepLLM(grade=[ALL_RELEVANT], generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])
    return dataclasses.replace(deps(llm=llm, **kwargs), cache=cache)


def state_for(question: str, history: list | None = None) -> AgentState:
    return {"question": question, "history": history or [], "channel": Channel.APP}


# ---------------------------------------------------------------- key


def test_key_ignores_case_punctuation_spaces_and_digit_script() -> None:
    a = cache_key("  আমার বয়স ৬৭ , বয়স্ক  ভাতা পাবো?", "old_age_allowance", Channel.APP)
    b = cache_key("আমার বয়স 67 বয়স্ক ভাতা পাবো", "old_age_allowance", Channel.APP)
    assert a == b == "আমার বয়স 67 বয়স্ক ভাতা পাবো|old_age_allowance|app"
    assert normalize_question("Boyosko VATA!!") == "boyosko vata"


def test_key_separates_service_and_channel() -> None:
    base = cache_key(QUESTION, "old_age_allowance", Channel.APP)
    assert base != cache_key(QUESTION, "widow_allowance", Channel.APP)
    assert base != cache_key(QUESTION, "old_age_allowance", Channel.VOICE)


# ---------------------------------------------------------------- routing


def test_confident_router_goes_through_the_cache_only_when_a_key_exists() -> None:
    state: AgentState = {"service_id": "old_age_allowance", "confidence": 0.9}
    assert routing.after_classify(state, 0.7) == routing.RETRIEVE
    assert routing.after_classify({**state, "cache_key": "k"}, 0.7) == routing.CACHE_LOOKUP
    other: AgentState = {"service_id": "other", "confidence": 0.9, "cache_key": "k"}
    assert routing.after_classify(other, 0.7) == routing.FALLBACK


def test_after_cache_lookup() -> None:
    assert routing.after_cache_lookup({}) == routing.RETRIEVE
    hit = steps.fallback({"service_id": "other"}, deps())["answer"]
    assert routing.after_cache_lookup({"answer": hit}) == routing.DONE


# ---------------------------------------------------------------- steps


def test_classify_sets_a_key_only_for_a_confident_local_router() -> None:
    cache = InMemoryAnswerCache()
    sure = steps.classify(state_for(QUESTION), cached_deps(cache))
    assert sure["cache_key"] == cache_key(QUESTION, "old_age_allowance", Channel.APP)

    unsure = cached_deps(cache, scores={"old_age_allowance": 0.5, "other": 0.5})
    assert "cache_key" not in steps.classify(state_for(QUESTION), unsure)

    other = cached_deps(cache, scores={"other": 0.95, "old_age_allowance": 0.05})
    assert "cache_key" not in steps.classify(state_for("আজ বৃষ্টি?"), other)

    llm_router = cached_deps(cache, classifier=FakeClassifier({"old_age_allowance": 0.95}, RouterSource.LLM))
    assert "cache_key" not in steps.classify(state_for(QUESTION), llm_router)

    assert "cache_key" not in steps.classify(state_for(QUESTION), deps())  # caching switched off


def test_a_pending_follow_up_reply_is_never_cached() -> None:
    history = [user("বিধবা ভাতা?"), bot("আপনি কি স্থায়ী বাসিন্দা?", AnswerStatus.FOLLOW_UP)]
    out = steps.classify(state_for("হ্যাঁ", history), cached_deps(InMemoryAnswerCache()))
    assert "cache_key" not in out


def test_a_broken_cache_never_breaks_answering() -> None:
    class Broken(InMemoryAnswerCache):
        def get(self, key: str) -> Any:
            raise RuntimeError("db down")

        def set(self, key: str, answer: Any) -> None:
            raise RuntimeError("db down")

    d = cached_deps(Broken())
    assert steps.cache_lookup({"cache_key": "k"}, d) == {}
    answer = LangGraphAnswerEngine(d).answer(QUESTION, [], Channel.APP)
    assert answer.status is AnswerStatus.ANSWERED


# ---------------------------------------------------------------- the whole graph


def test_second_identical_question_is_served_from_the_cache_without_llm() -> None:
    cache = InMemoryAnswerCache()
    llm = StepLLM(grade=[ALL_RELEVANT], generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])
    engine = LangGraphAnswerEngine(cached_deps(cache, llm))
    first = engine.answer(QUESTION, [], Channel.APP)
    assert first.llm_calls == 3 and len(cache.store) == 1
    calls_before = len(llm.steps)

    second = engine.answer("বয়স্ক ভাতা কত টাকা", [], Channel.APP)  # same question, no "?"
    assert len(llm.steps) == calls_before and second.llm_calls == 0
    assert second.speech_text == first.speech_text and second.status is AnswerStatus.ANSWERED
    assert set(second.timings) == {"classify", "cache_lookup", "total"}


def test_the_cache_does_not_mix_channels() -> None:
    cache = InMemoryAnswerCache()
    llm = StepLLM(grade=[ALL_RELEVANT], generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])
    engine = LangGraphAnswerEngine(cached_deps(cache, llm))
    engine.answer(QUESTION, [], Channel.APP)
    voice = engine.answer(QUESTION, [], Channel.VOICE)
    assert voice.llm_calls == 2 and len(cache.store) == 2  # fast mode: generate + verify


@pytest.mark.parametrize("draft", [NO_ANSWER, {**GOOD_DRAFT, "follow_up_question": "আপনার বয়স কত?"}])
def test_only_answered_results_are_stored(draft: dict[str, Any]) -> None:
    cache = InMemoryAnswerCache()
    llm = StepLLM(grade=[ALL_RELEVANT], generate=[draft], rewrite=[{"query": "q"}], verify=[ALL_SUPPORTED])
    answer = LangGraphAnswerEngine(cached_deps(cache, llm)).answer(QUESTION, [], Channel.APP)
    assert answer.status is not AnswerStatus.ANSWERED
    assert cache.store == {}


def test_other_never_touches_the_cache() -> None:
    cache = InMemoryAnswerCache()
    d = cached_deps(cache, llm=FakeLLM(fail=True), scores={"other": 0.95, "old_age_allowance": 0.05})
    assert LangGraphAnswerEngine(d).answer("আজ বৃষ্টি হবে?", [], Channel.APP).status is AnswerStatus.FALLBACK
    assert cache.store == {}
