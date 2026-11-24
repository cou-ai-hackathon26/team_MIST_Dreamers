"""Which step runs next (SRS 7.4). Pure functions of the state, so each branch is easy to test.

classify -> (cache_lookup) | (llm_classify, or understand in situation mode) -> retrieve -> grade ->
generate -> verify -> finalize, with
rewrite_query -> retrieve loops sharing one `retries` counter, finalize_follow_up for a missing
fact, and fallback for `other` or when nothing reliable is left. Voice fast mode skips grade.
"""

from dataclasses import dataclass

from app.application.agent.state import AgentState
from app.domain.policies import HINT_MIN_CONFIDENCE, MULTI_SERVICE_MIN_PROB
from app.domain.value_objects import RouterSource

OTHER = "other"

CLASSIFY = "classify"
CACHE_LOOKUP = "cache_lookup"
DONE = "done"  # the graph's end, used as a routing target
LLM_CLASSIFY = "llm_classify"
UNDERSTAND = "understand"
RETRIEVE = "retrieve"
GRADE = "grade"
REWRITE_QUERY = "rewrite_query"
GENERATE = "generate"
GUARD = "grounding_guard"
VERIFY = "verify"
FINALIZE = "finalize"
FINALIZE_FOLLOW_UP = "finalize_follow_up"
FALLBACK = "fallback"


def _retry_or_fallback(state: AgentState, max_retries: int) -> str:
    return REWRITE_QUERY if state.get("retries", 0) < max_retries else FALLBACK  # FR-AGT-07


@dataclass(frozen=True)
class SituationRouting:
    """Sprint switches for `after_classify` (FR-AGT-19). `enabled=False` is the old flow."""

    enabled: bool = False
    multi_min_prob: float = MULTI_SERVICE_MIN_PROB
    hint_min_confidence: float = HINT_MIN_CONFIDENCE


OLD_FLOW = SituationRouting()


def second_service_likely(state: AgentState, min_prob: float, key: str = "candidates") -> bool:
    """A router's 2nd label is a real service and at least `min_prob` likely (a mixed question)."""
    candidates = state.get(key) or []  # type: ignore[misc]
    if len(candidates) < 2:
        return False
    label, prob = candidates[1]
    return label != OTHER and prob >= min_prob


def hint_doubts(state: AgentState, min_prob: float, min_confidence: float = 0.0) -> bool:
    """The hint router (trained with situations) picks another service, sees a 2nd one, or is
    itself unsure, as with vague questions such as "আমি খুব গরিব, কিছু পাবো?" (T6)."""
    hints = state.get("hint_candidates") or []
    if not hints:
        return False
    return (
        hints[0][0] != state.get("service_id")
        or hints[0][1] < min_confidence
        or second_service_likely(state, min_prob, "hint_candidates")
    )


def after_classify(state: AgentState, threshold: float, situation: SituationRouting = OLD_FLOW) -> str:
    if state.get("pending_service_id"):
        return RETRIEVE  # FR-AGT-17: keep the service(s) of the pending follow-up
    by_llm = state.get("router_source") is RouterSource.LLM
    second_opinion = UNDERSTAND if situation.enabled and not by_llm else LLM_CLASSIFY
    if state.get("needs_context") and not by_llm:
        return second_opinion  # a short follow-up question: the LLM reads the last turns
    label = state.get("service_id")
    confident = state.get("confidence", 0.0) >= threshold
    if situation.enabled and not by_llm and confident:
        # FR-AGT-19: a situation can look like `other`, and a likely 2nd service means a mixed question.
        if label == OTHER or not label or second_service_likely(state, situation.multi_min_prob):
            return UNDERSTAND
        if hint_doubts(state, situation.multi_min_prob, situation.hint_min_confidence):
            return UNDERSTAND
    if confident or by_llm:  # the LLM router is not asked twice
        if label == OTHER or not label:
            return FALLBACK
        return CACHE_LOOKUP if state.get("cache_key") else RETRIEVE  # FR-AGT-15
    return second_opinion  # FR-AGT-03


def after_cache_lookup(state: AgentState) -> str:
    return DONE if state.get("answer") is not None else RETRIEVE


def after_llm_classify(state: AgentState) -> str:
    return FALLBACK if state.get("service_id") in (None, "", OTHER) else RETRIEVE  # FR-AGT-04


def after_understand(state: AgentState) -> str:
    """FR-AGT-19, 23: out of scope -> fallback; one question to ask -> follow-up; else retrieve."""
    if (state.get("follow_up") or "").strip():
        return FINALIZE_FOLLOW_UP
    if state.get("service_id") in (None, "", OTHER):
        return FALLBACK
    return RETRIEVE


def after_retrieve(state: AgentState, fast_mode: bool) -> str:
    """Voice fast mode skips grading: generate itself says `no_answer` (FR-AGT-06)."""
    return GENERATE if fast_mode else GRADE


def after_grade(state: AgentState, max_retries: int) -> str:
    return GENERATE if state.get("relevant_ids") else _retry_or_fallback(state, max_retries)


def _has_text(draft: dict) -> bool:  # type: ignore[type-arg]
    if draft.get("sections"):  # a two-service draft (FR-AGT-21)
        return any(str(s.get("speech_text", "")).strip() for s in draft["sections"] if isinstance(s, dict))
    return bool(str(draft.get("speech_text", "")).strip())


def after_generate(state: AgentState, max_retries: int) -> str:
    """VERIFY here means "check it": the graph runs grounding_guard first, then verify."""
    draft = state.get("draft") or {}
    if draft.get("no_answer") or not _has_text(draft):
        return _retry_or_fallback(state, max_retries)
    follow_up = str(draft.get("follow_up_question") or "").strip()
    if follow_up and not state.get("pending_service_id"):  # FR-AGT-09: at most one follow-up
        return FINALIZE_FOLLOW_UP
    return VERIFY


def after_guard(state: AgentState, max_retries: int) -> str:
    """A core claim cited the wrong service or no real passage: retry, then fall back (FR-AGT-22)."""
    draft = state.get("draft") or {}
    if state.get("dropped_core") or not _has_text(draft):
        return _retry_or_fallback(state, max_retries)
    return VERIFY


def after_verify(state: AgentState, max_retries: int) -> str:
    """All core claims and the spoken answer supported -> finalize; else retry, then fall back (FR-AGT-10)."""
    if state.get("answers_question") is False:
        return FALLBACK  # true facts, but for another question: a retry would not change that
    claims = state.get("verified_claims") or []
    supported = [c for c in claims if c.get("supported")]
    core_failed = any(c.get("core") and not c.get("supported") for c in claims)
    if supported and not core_failed and state.get("speech_supported", True):
        return FINALIZE
    return _retry_or_fallback(state, max_retries)
