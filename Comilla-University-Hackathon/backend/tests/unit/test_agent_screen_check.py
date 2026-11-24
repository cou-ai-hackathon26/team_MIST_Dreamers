"""The verifier also checks the screen text and each checklist field (facts copied from history)."""

from typing import Any

from app.application.agent import prompts, steps
from app.application.agent.state import AgentState
from app.domain.messages_bn import DECISION_NOTE
from app.domain.value_objects import AnswerStatus, Channel
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from tests.fakes import FakeLLM
from tests.unit.test_agent import ALL_RELEVANT, GOOD_DRAFT, PASSAGES, StepLLM, deps

FREE_DRAFT: dict[str, Any] = {
    **GOOD_DRAFT,
    "display_text": "**বয়স্ক ভাতা**\n- ফি: বিনামূল্যে",
    "checklist": {"who": "পুরুষ ৬৫+", "papers": ["জাতীয় পরিচয়পত্র"], "fee": "বিনামূল্যে", "where": "উপজেলা",
                  "decision": "কমিটি"},
}  # fmt: skip


def verdict(display_ok: bool, bad: list[str]) -> dict[str, Any]:
    return {
        "claims": [{"index": i, "supported": True} for i in range(3)],
        "speech_supported": True,
        "display_supported": display_ok,
        "unsupported_checklist": bad,
    }


def test_verify_prompt_shows_the_screen_text_and_every_checklist_field() -> None:
    llm = FakeLLM([verdict(True, [])])
    steps.verify({"draft": FREE_DRAFT, "passages": PASSAGES}, deps(llm=llm))
    prompt = llm.prompts[0]
    assert "Screen text: **বয়স্ক ভাতা**" in prompt
    assert "- fee: বিনামূল্যে" in prompt and "- papers: জাতীয় পরিচয়পত্র" in prompt


def test_verify_keeps_only_known_checklist_field_names() -> None:
    out = steps.verify(
        {"draft": FREE_DRAFT, "passages": PASSAGES}, deps(llm=FakeLLM([verdict(False, ["fee", "x"])]))
    )
    assert out["unsupported_checklist"] == ["fee"] and out["display_supported"] is False


def test_finalize_blanks_unsupported_fields_and_replaces_unsupported_screen_text() -> None:
    state: AgentState = {
        "draft": FREE_DRAFT, "service_id": "old_age_allowance", "passages": PASSAGES,
        "display_supported": False, "unsupported_checklist": ["fee", "where", "papers"],
    }  # fmt: skip
    answer = steps.finalize(state, deps())["answer"]
    assert answer.checklist.fee == steps.UNKNOWN_BN
    assert answer.checklist.where == steps.UNKNOWN_BN  # not the unverified office name from services.yaml
    assert answer.checklist.papers == ()
    assert answer.checklist.who == "পুরুষ ৬৫+"  # supported fields stay
    assert "বিনামূল্যে" not in answer.display_text
    assert answer.display_text.startswith(answer.speech_text) and DECISION_NOTE in answer.display_text


def test_old_verifier_replies_without_the_new_fields_change_nothing() -> None:
    state: AgentState = {"draft": FREE_DRAFT, "service_id": "old_age_allowance", "passages": PASSAGES}
    answer = steps.finalize(state, deps())["answer"]
    assert answer.checklist.fee == "বিনামূল্যে" and "বিনামূল্যে" in answer.display_text


def test_end_to_end_a_fee_copied_from_history_never_reaches_the_citizen() -> None:
    llm = StepLLM(grade=[ALL_RELEVANT], generate=[FREE_DRAFT], verify=[verdict(False, ["fee"])])
    answer = LangGraphAnswerEngine(deps(llm=llm)).answer("বয়স্ক ভাতা পাবো?", [], Channel.APP)
    assert answer.status is AnswerStatus.ANSWERED
    assert answer.checklist.fee == steps.UNKNOWN_BN and "বিনামূল্যে" not in answer.display_text


def test_generate_prompt_says_history_is_not_a_source() -> None:
    prompt = prompts.build_generate_prompt(
        "q", deps().services["old_age_allowance"], PASSAGES, [], Channel.APP
    )
    assert "never copy facts, amounts, fees or wording from them" in prompt
