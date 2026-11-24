"""What the agent knows while it works on one question (SRS 7.4).

Each step returns only the keys it changes. `timings` and `llm_calls` are merged across steps
(the Annotated reducers tell the graph how), everything else is replaced.
"""

import operator
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, TypedDict

from app.application.ports.retrieval import Passage
from app.domain.entities import Answer, Message
from app.domain.value_objects import Channel, RouterSource


def merge_timings(old: Mapping[str, float], new: Mapping[str, float]) -> dict[str, float]:
    """A step that runs again (retrieve after a rewrite) adds to its earlier time."""
    merged = dict(old)
    for step, ms in new.items():
        merged[step] = round(merged.get(step, 0.0) + ms, 1)
    return merged


class AgentState(TypedDict, total=False):
    question: str
    history: Sequence[Message]  # oldest first, without the current question
    channel: Channel
    pending_service_id: str | None  # set when the last assistant turn asked a follow-up (FR-AGT-17)
    candidates: list[tuple[str, float]]  # router top 3, best first
    hint_candidates: list[tuple[str, float]]  # the hint router's top 3 (situation mode, T6)
    service_id: str
    confidence: float
    router_source: RouterSource
    needs_context: bool  # a short question after an answer that the local router put elsewhere
    cache_key: str  # set only when the answer may be cached / served from the cache (FR-AGT-15)
    query: str  # what is sent to the retriever (rewrite_query changes it)
    passages: list[Passage]
    fee_ids: list[str]  # passages added by retrieve only for the checklist fee; grade keeps them
    relevant_ids: list[str]  # "P1", "P2"... chosen by grade
    retries: int  # one counter for the grade, generate and verify loops (max MAX_RETRIEVAL_RETRIES)
    draft: dict[str, Any]  # the generate step's JSON
    verified_claims: list[dict[str, Any]]  # draft claims, each with `supported` added by verify
    speech_supported: bool
    answers_question: bool  # the verifier found the answer is about the question that was asked
    display_supported: bool  # the screen text has no unsupported fact
    unsupported_checklist: list[str]  # checklist fields to blank out ("who", "papers", "fee", ...)
    # Situations and mixed questions (sprint T3 to T5, FR-AGT-19 to 22)
    service_ids: list[str]  # 1 or 2 services, primary first (= service_id)
    mode: str  # "single" | "multi"
    situation: dict[str, Any] | None  # {"summary_bn": str, "facts": {key: value}} from `understand`
    search_queries: dict[str, str]  # service_id -> search query in the documents' own words
    follow_up: str  # a question `understand` wants to ask before answering (FR-AGT-23)
    follow_up_done: bool  # the last assistant turn already asked one (FR-AGT-09: at most one)
    conflicts: list[dict[str, Any]]  # T5: rules that differ between the two services
    dropped_core: bool  # T5: grounding_guard dropped a core claim
    answer: Answer
    timings: Annotated[dict[str, float], merge_timings]
    llm_calls: Annotated[int, operator.add]
