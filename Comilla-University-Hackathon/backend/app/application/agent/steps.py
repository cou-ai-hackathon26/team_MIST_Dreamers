"""The agent's steps (SRS 7.4): pure functions `(state, deps) -> the state keys they change`.

They only use ports, so unit tests run them with fakes, and the LangGraph wiring in
infrastructure/agent stays a thin layer around them.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.application.agent import multi, prompts
from app.application.agent.cache_key import cache_key
from app.application.agent.grounding import grounding_guard
from app.application.agent.queries import build_queries, merge_best
from app.application.agent.routing import OTHER
from app.application.agent.state import AgentState
from app.application.formatting import limit_sentences, trim_speech
from app.application.ports.classifier import ServiceClassifier
from app.application.ports.llm import LLM, ModelRole
from app.application.ports.repositories import AnswerCache
from app.application.ports.retrieval import Passage, Retriever
from app.domain.entities import Answer, Checklist, Citation, Message, Service, SituationProfile
from app.domain.errors import ClassifierUnavailable
from app.domain.messages_bn import DECISION_NOTE, FALLBACK
from app.domain.policies import (
    HINT_MIN_CONFIDENCE,
    MAX_RETRIEVAL_RETRIES,
    MAX_SERVICES_PER_QUESTION,
    MAX_SPEECH_WORDS_MULTI,
    MULTI_SERVICE_MIN_PROB,
    MULTI_TOP_K,
    ROUTER_CONFIDENCE_THRESHOLD,
    TOP_K,
)
from app.domain.service_set import ServiceSet
from app.domain.value_objects import AnswerStatus, Channel, Role, RouterSource

log = logging.getLogger(__name__)

SNIPPET_WORDS = 30
FEE_QUERY = "ফি কত টাকা"
FEE_PASSAGES = 2  # fee passages added next to the top-k, see _with_fee_passages
AMOUNT_WORD = "টাকা"
SHORT_QUESTION_WORDS = 6  # a question this short, after an answer, may only make sense with the conversation
UNKNOWN_BN = "তথ্য পাওয়া যায়নি"
_BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


@dataclass(frozen=True)
class AgentDeps:
    classifier: ServiceClassifier
    retriever: Retriever
    llm: LLM
    services: Mapping[str, Service]  # all 9 labels, `other` included
    confidence_threshold: float = ROUTER_CONFIDENCE_THRESHOLD
    top_k: int = TOP_K
    max_retries: int = MAX_RETRIEVAL_RETRIES
    cache: AnswerCache | None = None  # FR-AGT-15; None = no caching
    voice_fast_mode: bool = True  # calls skip `grade` (FR-AGT-06)
    llm_backend: str | None = None  # FR-AGT-18: recorded on every answer
    # Situations and mixed questions (FR-AGT-19 to 22). Off by default = the old flow; the
    # container turns them on from SITUATION_MODE / QUERY_EXPANSION.
    situation_mode: bool = False
    multi_service_min_prob: float = MULTI_SERVICE_MIN_PROB
    max_services: int = MAX_SERVICES_PER_QUESTION
    query_expansion: bool = False
    multi_top_k: int = MULTI_TOP_K
    max_speech_words_multi: int = MAX_SPEECH_WORDS_MULTI
    # A second, cheap local router trained with situations (TF-IDF v2). When it disagrees with a
    # confident main router, or sees a likely 2nd service, `understand` reads the question (T6).
    hint_classifier: ServiceClassifier | None = None
    hint_min_confidence: float = HINT_MIN_CONFIDENCE

    def fast_mode(self, channel: Channel | None) -> bool:
        return self.voice_fast_mode and channel is Channel.VOICE


# ---------------------------------------------------------------- small helpers


def to_bangla_digits(text: str) -> str:
    return text.translate(_BANGLA_DIGITS)


def pending_follow_up(history: Sequence[Message]) -> tuple[str | None, str | None]:
    """(service_id, the question that led to it) when the last assistant turn asked a follow-up.

    `service_id` may hold two services ("a,b", see ServiceSet) for a mixed question.
    """
    for i in range(len(history) - 1, -1, -1):
        message = history[i]
        if message.role is Role.ASSISTANT:
            if message.status is AnswerStatus.FOLLOW_UP and message.service_id:
                earlier = [m.text for m in history[:i] if m.role is Role.USER]
                return message.service_id, earlier[-1] if earlier else None
            return None, None
    return None, None


def last_turn_was_follow_up(history: Sequence[Message]) -> bool:
    """The last assistant turn asked a question (with or without a service)."""
    for message in reversed(history):
        if message.role is Role.ASSISTANT:
            return message.status is AnswerStatus.FOLLOW_UP
    return False


def previous_service(history: Sequence[Message]) -> str | None:
    """The service of the last assistant turn (a real service, not `other`), if any."""
    for message in reversed(history):
        if message.role is Role.ASSISTANT:
            service = message.service_id
            return service if service and service != OTHER else None
    return None


def _clamp(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


# ---------------------------------------------------------------- steps


def classify(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Local router (FR-AGT-01), or the service of a pending follow-up (FR-AGT-17)."""
    question = state["question"]
    history = state.get("history", ())
    stored, earlier_question = pending_follow_up(history)
    pending = [sid for sid in ServiceSet.parse(stored) if sid in deps.services and sid != OTHER]
    if pending:
        # A short reply such as "হ্যাঁ" finds nothing alone, so search with the earlier question too.
        query = f"{earlier_question} {question}" if earlier_question else question
        pending = pending[: deps.max_services]
        return {
            "pending_service_id": pending[0], "service_id": pending[0], "confidence": 1.0,
            "router_source": RouterSource.CONTEXT, "candidates": [], "query": query,
            "service_ids": pending, "mode": "multi" if len(pending) > 1 else "single",
        }  # fmt: skip
    try:
        scores = deps.classifier.classify(question)
    except ClassifierUnavailable as exc:
        log.warning("router unavailable, asking the LLM instead: %s", exc)
        scores = []
    candidates = [(label, _clamp(score)) for label, score in scores[:3]]
    label, confidence = candidates[0] if candidates else (OTHER, 0.0)
    if label not in deps.services:
        label, confidence = OTHER, 0.0
    update: dict[str, Any] = {
        "pending_service_id": None, "candidates": candidates, "service_id": label,
        "confidence": confidence, "router_source": deps.classifier.source, "query": question,
        "service_ids": [label] if label != OTHER else [], "mode": "single",
        "follow_up_done": last_turn_was_follow_up(history),
    }  # fmt: skip
    local = deps.classifier.source is not RouterSource.LLM
    if deps.situation_mode and local and deps.hint_classifier is not None:
        update["hint_candidates"] = _hint_candidates(question, deps.hint_classifier)
    previous = previous_service(state.get("history", ()))
    if (
        local
        and previous in deps.services
        and label != previous
        and len(question.split()) <= SHORT_QUESTION_WORDS
    ):
        # "আর কোথায় জমা দেবো?" has no topic of its own: a local router guesses a wrong service, even
        # with high confidence. Let the LLM decide with the last turns, and never cache this question.
        update["needs_context"] = True
        return update
    # FR-AGT-15: cache only when the local router was sure, so short replies such as "হ্যাঁ"
    # (which depend on the conversation) are never served from the cache.
    if deps.cache is not None and local and label != OTHER and confidence >= deps.confidence_threshold:
        update["cache_key"] = cache_key(question, label, state["channel"])
    return update


def _hint_candidates(question: str, hint: ServiceClassifier) -> list[tuple[str, float]]:
    try:
        return [(label, _clamp(score)) for label, score in hint.classify(question)[:3]]
    except ClassifierUnavailable as exc:  # the hint is optional: the main router still decides
        log.warning("hint router unavailable: %s", exc)
        return []


def llm_classify(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Second opinion for unsure routers, with the top 3 hints and recent turns (FR-AGT-03)."""
    prompt = prompts.build_classify_prompt(
        state["question"], deps.services, state.get("candidates", []), state.get("history", ())
    )
    data = deps.llm.generate_json(
        prompt, prompts.classify_schema(list(deps.services)), role=ModelRole.FAST, temperature=0.0
    )
    label = _text(data.get("service_id"))
    if label not in deps.services:
        label = OTHER
    update: dict[str, Any] = {
        "service_id": label, "confidence": _clamp(data.get("confidence")),
        "router_source": RouterSource.LLM, "llm_calls": 1,
    }  # fmt: skip
    standalone = _text(data.get("search_query"))
    if standalone:  # "আর কোথায় জমা দেবো?" alone finds nothing; the full question does
        update["query"] = standalone
    return update


def understand(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Reads the caller's situation (FR-AGT-19, 23): up to 2 services, facts, a summary and one
    search query per service. One FAST call; it replaces `llm_classify` in situation mode.

    Labels the LLM invents are ignored (never trust its list blindly). Situation and multi
    answers are never cached, so the cache key is cleared.
    """
    hints = [*state.get("candidates", []), *state.get("hint_candidates", [])]
    prompt = prompts.build_understand_prompt(
        state["question"], deps.services, hints, state.get("history", ()),
        max_services=deps.max_services, follow_up_used=bool(state.get("follow_up_done")),
    )  # fmt: skip
    data = deps.llm.generate_json(
        prompt, prompts.understand_schema(list(deps.services)), role=ModelRole.FAST, temperature=0.0
    )
    raw = data.get("services") if isinstance(data.get("services"), list) else []
    services: list[str] = []
    for item in raw:
        sid = _text(item)
        if sid in deps.services and sid != OTHER and sid not in services:
            services.append(sid)
    services = services[: deps.max_services]
    out_of_scope = bool(data.get("out_of_scope")) or not services  # the refusal wins (FR-AGT-04)
    follow_up = _text(data.get("follow_up_question")) if data.get("needs_follow_up") else ""
    if data.get("out_of_scope") or state.get("follow_up_done") or state.get("pending_service_id"):
        follow_up = ""  # off-topic is refused, never asked about; FR-AGT-09: at most one follow-up
    queries = data.get("search_queries") if isinstance(data.get("search_queries"), Mapping) else {}
    update: dict[str, Any] = {
        "router_source": RouterSource.SITUATION,
        "cache_key": "",
        "llm_calls": 1,
        "service_ids": services,
        "mode": "multi" if len(services) > 1 else "single",
        "situation": _situation(data),
        "search_queries": {sid: _text(queries.get(sid)) for sid in services if _text(queries.get(sid))},
        "follow_up": follow_up,
    }
    if out_of_scope and not follow_up:
        update.update(service_id=OTHER, confidence=_router_score(state, OTHER), service_ids=[])
        return update
    primary = services[0] if services else OTHER
    update.update(service_id=primary, confidence=_router_score(state, primary) if services else 0.0)
    return update


def _situation(data: Mapping[str, Any]) -> dict[str, Any] | None:
    summary = _text(data.get("summary_bn"))
    raw = data.get("facts") if isinstance(data.get("facts"), Mapping) else {}
    facts = {_text(k): _text(v) for k, v in raw.items() if _text(k) and _text(v)}
    if not summary and not facts:
        return None
    return {"summary_bn": to_bangla_digits(summary), "facts": facts}


def _router_score(state: AgentState, label: str) -> float:
    """The router's probability for `label` (the Answer's confidence), 0 when not in the top 3."""
    for candidate, score in state.get("candidates") or []:
        if candidate == label:
            return _clamp(score)
    return 0.0


def cache_lookup(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """A repeated question within 24 hours is answered from the cache, with no LLM call (FR-AGT-15)."""
    key = state.get("cache_key")
    if not key or deps.cache is None:
        return {}
    try:
        hit = deps.cache.get(key)
    except Exception:  # a broken cache must never break answering
        log.exception("answer cache read failed")
        return {}
    return {"answer": hit} if hit is not None else {}


def retrieve(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Top-k official passages per chosen service (FR-AGT-05, 20, 21).

    Every query of `build_queries` is searched with the service filter and the results are merged
    per chunk. Single mode keeps the adapter's "also search all services" fallback; in multi mode
    a service only keeps its own passages, so two services' rules never mix.
    """
    query = state.get("query") or state["question"]
    ids = active_services(state, deps)
    multi = len(ids) > 1
    k = deps.multi_top_k if multi else deps.top_k
    llm_queries = state.get("search_queries") or {}
    passages: list[Passage] = []
    fee_ids: list[str] = []
    for sid in ids:
        queries = build_queries(query, deps.services[sid], llm_queries.get(sid, ""), deps.query_expansion)
        found = merge_best((deps.retriever.search(q, sid, k) for q in queries), k)
        if multi:
            found = [p for p in found if p.service_id == sid]
        have = {p.chunk_id for p in passages} | {p.chunk_id for p in found}
        fees = [p for p in _fee_passages(sid, deps) if not multi or p.service_id == sid]
        passages += found + [p for p in fees if p.chunk_id not in have]
        fee_ids += [p.chunk_id for p in fees]
    return {"query": query, "passages": passages, "fee_ids": fee_ids}


def active_services(state: AgentState, deps: AgentDeps) -> list[str]:
    """The services to answer for, primary first. `service_ids` counts only while its first entry
    is still `service_id` (a later step such as llm_classify may have changed the service)."""
    ids = [sid for sid in state.get("service_ids") or [] if sid in deps.services and sid != OTHER]
    primary = state.get("service_id")
    if ids and ids[0] == primary:
        return ids[: deps.max_services]
    return [primary] if primary in deps.services and primary != OTHER else ids[:1]


def _fee_passages(service_id: str, deps: AgentDeps) -> list[Passage]:
    """The service's fee passages, so the checklist fee is filled even when the question is not
    about money ("how do I correct my name" still needs the fee table). `grade` keeps them.

    One more local search (no LLM call). Only passages that state an amount are kept.
    """
    fee_query = f"{deps.services[service_id].name_bn} {FEE_QUERY}"
    found = deps.retriever.search(fee_query, service_id, FEE_PASSAGES)
    return [p for p in found if AMOUNT_WORD in p.text]


def generate(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """One JSON answer from the passages only (FR-AGT-08, 09, 11)."""
    passages = state.get("passages") or []
    if not passages:
        return {"draft": {"no_answer": True}}
    ids = active_services(state, deps)
    if is_multi(state, deps):
        situation = (state.get("situation") or {}).get("summary_bn", "")
        prompt = prompts.build_generate_multi_prompt(
            state["question"], [deps.services[sid] for sid in ids], passages,
            state.get("history", ()), state["channel"], situation=situation,
        )  # fmt: skip
        data = deps.llm.generate_json(
            prompt, prompts.GENERATE_MULTI_SCHEMA, role=ModelRole.MAIN, temperature=0.2
        )
        return {"draft": data, "llm_calls": 1}
    prompt = prompts.build_generate_prompt(
        state["question"], deps.services[state["service_id"]], passages,
        state.get("history", ()), state["channel"],
    )  # fmt: skip
    data = deps.llm.generate_json(prompt, prompts.GENERATE_SCHEMA, role=ModelRole.MAIN, temperature=0.2)
    return {"draft": data, "llm_calls": 1}


def is_multi(state: AgentState, deps: AgentDeps) -> bool:
    return state.get("mode") == "multi" and len(active_services(state, deps)) > 1


def guard(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """grounding_guard (FR-AGT-22): plain code, no LLM. No claim may cite another service's passage."""
    passages = state.get("passages") or []
    by_id = {prompts.passage_id(i): p.service_id for i, p in enumerate(passages)}
    multi = is_multi(state, deps)
    result = grounding_guard(
        state["draft"], by_id, mode="multi" if multi else "single", primary=state["service_id"],
        services=active_services(state, deps),
    )  # fmt: skip
    if result.dropped:
        log.info("grounding_guard dropped %d item(s): %s", len(result.dropped), "; ".join(result.dropped))
    return {"draft": result.draft, "dropped_core": result.dropped_core}


def grade(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """One FAST call for all passages; keeps only the useful ones for `generate` (FR-AGT-06)."""
    passages = state.get("passages") or []
    if not passages:
        return {"relevant_ids": []}
    data = deps.llm.generate_json(
        prompts.build_grade_prompt(state["question"], passages),
        prompts.GRADE_SCHEMA,
        role=ModelRole.FAST,
        temperature=0.0,
    )
    raw = data.get("relevant_ids") if isinstance(data.get("relevant_ids"), list) else []
    wanted = {_text(pid).strip("[]").upper() for pid in raw}
    kept = [p for i, p in enumerate(passages) if prompts.passage_id(i) in wanted]
    if kept:  # the fee passages are not about the question, but the checklist card needs them
        fee_ids = set(state.get("fee_ids") or [])
        kept += [p for p in passages if p.chunk_id in fee_ids and p not in kept]
    return {
        "relevant_ids": [prompts.passage_id(i) for i in range(len(kept))],
        "passages": kept,
        "llm_calls": 1,
    }


def rewrite_query(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """A clearer, more formal search query, then retrieve again (FR-AGT-07). Counts one retry."""
    question = state["question"]
    data = deps.llm.generate_json(
        prompts.build_rewrite_prompt(
            question, state.get("query") or question, deps.services[state["service_id"]],
            state.get("history", ()),
        ),
        prompts.REWRITE_SCHEMA,
        role=ModelRole.FAST,
        temperature=0.3,
    )  # fmt: skip
    query = _text(data.get("query")) or question
    return {"query": query, "retries": state.get("retries", 0) + 1, "llm_calls": 1}


def verify(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """One MAIN call checks every claim and the spoken answer against the passages (FR-AGT-10)."""
    if is_multi(state, deps):
        return _verify_multi(state, deps)
    draft = state["draft"]
    claims = [c for c in draft.get("claims") or [] if isinstance(c, Mapping) and _text(c.get("text"))]
    if not claims:
        return {"verified_claims": [], "speech_supported": False}  # nothing checkable = not reliable
    checklist = draft.get("checklist") if isinstance(draft.get("checklist"), Mapping) else {}
    data = deps.llm.generate_json(
        prompts.build_verify_prompt(
            [_text(c.get("text")) for c in claims],
            _text(draft.get("speech_text")),
            state.get("passages") or [],
            display=_text(draft.get("display_text")),
            checklist=checklist,
            question=state.get("question", ""),
        ),
        prompts.VERIFY_SCHEMA,
        role=ModelRole.MAIN,
        temperature=0.0,
    )
    verdicts: dict[int, bool] = {}
    for item in data.get("claims") or []:
        if isinstance(item, Mapping) and isinstance(item.get("index"), int):
            verdicts[item["index"]] = bool(item.get("supported"))
    checked = [
        {**c, "core": bool(c.get("core")), "supported": verdicts.get(i, False)} for i, c in enumerate(claims)
    ]
    unsupported = [c["text"] for c in checked if not c["supported"]]
    if unsupported:
        log.info("verify: %d of %d claims unsupported", len(unsupported), len(checked))
    raw_fields = (
        data.get("unsupported_checklist") if isinstance(data.get("unsupported_checklist"), list) else []
    )
    bad_fields = [f for f in (_text(x) for x in raw_fields) if f in prompts.CHECKLIST_FIELDS]
    display_ok = bool(data.get("display_supported", True))
    if bad_fields or not display_ok:
        log.info("verify: checklist fields unsupported %s, screen text supported %s", bad_fields, display_ok)
    answers = bool(data.get("answers_question", True))
    if not answers:
        log.info("verify: the answer is about another question than the one asked")
    return {
        "verified_claims": checked,
        "answers_question": answers,
        "speech_supported": bool(data.get("speech_supported", True)),
        "display_supported": display_ok,
        "unsupported_checklist": bad_fields,
        "llm_calls": 1,
    }


def _verify_multi(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Claims, checklist fields, conflict sides and a stated combine rule, in one call (FR-AGT-22)."""
    draft = state["draft"]
    names = {sid: s.name_bn for sid, s in deps.services.items()}
    items = multi.verify_items(draft, names)
    if not any(item.kind == "claim" for item in items):
        return {"verified_claims": [], "speech_supported": False}
    speech = " ".join(_text(s.get("speech_text")) for s in draft.get("sections") or [])
    notes = multi.fixed_notes(draft)  # the fixed sentences finalize will add (never from the LLM)
    direct = multi.direct_text(draft) or ""  # also an item below, so it is checked too
    data = deps.llm.generate_json(
        prompts.build_verify_prompt(
            [item.text for item in items],
            f"{direct} {speech} {notes}".strip(),
            state.get("passages") or [],
            question=state.get("question", ""),
            multi=True,
        ),
        prompts.VERIFY_SCHEMA,
        role=ModelRole.MAIN,
        temperature=0.0,
    )
    verdicts = {
        item["index"]: bool(item.get("supported"))
        for item in data.get("claims") or []
        if isinstance(item, Mapping) and isinstance(item.get("index"), int)
    }
    checked = multi.apply_verdicts(draft, items, verdicts)
    claims = [
        {**c, "core": bool(c.get("core")), "supported": bool(c.get("supported"))}
        for c in multi.flat_claims(checked)
    ]
    unsupported = sum(1 for c in claims if not c["supported"])
    if unsupported:
        log.info("verify (multi): %d of %d claims unsupported", unsupported, len(claims))
    return {
        "draft": checked,
        "verified_claims": claims,
        "answers_question": bool(data.get("answers_question", True)),
        "speech_supported": bool(data.get("speech_supported", True)),
        "display_supported": True,
        "unsupported_checklist": [],
        "llm_calls": 1,
    }


def finalize(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Turns the checked draft into an `answered` Answer (FR-AGT-08, 12).

    Unsupported non-core claims are dropped, so only passages behind supported claims are cited.
    A screen text with an unsupported fact is replaced by the (verified) spoken answer, and
    unsupported checklist fields become "তথ্য পাওয়া যায়নি".
    """
    if is_multi(state, deps):
        return _finalize_multi(state, deps)
    draft = state["draft"]
    service = deps.services[state["service_id"]]
    speech = trim_speech(_text(draft.get("speech_text")))
    if state.get("channel") is Channel.VOICE:
        speech = limit_sentences(speech)
    speech = to_bangla_digits(speech)
    display = _text(draft.get("display_text")) if state.get("display_supported", True) else ""
    display = display or speech
    if DECISION_NOTE not in display:
        display = f"{display}\n\n_{DECISION_NOTE}_"
    answer = Answer(
        status=AnswerStatus.ANSWERED,
        speech_text=speech,
        display_text=display,
        service_id=service.id,
        confidence=_clamp(state.get("confidence")),
        router_source=state.get("router_source"),
        checklist=build_checklist(draft.get("checklist"), service, state.get("unsupported_checklist") or ()),
        citations=build_citations(_supported_claims(state), state.get("passages") or []),
        llm_backend=deps.llm_backend,
        service_ids=(service.id,),
        situation=situation_profile(state.get("situation")),
    )
    _store_in_cache(state, deps, answer)
    return {"answer": answer}


def _finalize_multi(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Two services (FR-AGT-21, 22): one section, checklist and SMS per service, conflicts side by side.

    A service whose section has no supported claim is left out; with one left the answer is a
    normal single answer for it.
    """
    draft = state["draft"]
    passages = state.get("passages") or []
    sections = []
    for section in draft.get("sections") or []:
        supported = [c for c in section.get("claims") or [] if c.get("supported", True)]
        if supported:
            sections.append({**section, "claims": supported})
    services = [deps.services[s["service_id"]] for s in sections]
    conflicts = multi.build_conflicts(draft.get("conflicts"), passages) if len(services) > 1 else ()
    combine = draft.get("combine_rule") or {}
    combine_text = to_bangla_digits(_text(combine.get("text_bn"))) if combine.get("stated") else None
    asks_combine = bool(draft.get("asks_combine")) and len(services) > 1
    lines = [to_bangla_digits(_text(s.get("speech_text"))) for s in sections]
    direct = multi.direct_text(draft) if len(services) > 1 else None
    direct = to_bangla_digits(direct) if direct else None
    if len(services) > 1:
        speech = multi.build_speech(
            [s.name_bn for s in services], lines, bool(conflicts), combine_text, asks_combine,
            deps.max_speech_words_multi, direct=direct,
        )  # fmt: skip
    else:
        speech = trim_speech(lines[0])
    checklists = tuple(
        build_checklist(
            s.get("checklist"), deps.services[s["service_id"]], s.get("unsupported_checklist") or ()
        )
        for s in sections
    )
    claims = [c for s in sections for c in s["claims"]]
    used_ids = [
        {"passage_ids": side.get("passage_ids", [])}
        for c in draft.get("conflicts") or []
        for side in c["sides"]
    ]
    if combine_text:
        used_ids.append({"passage_ids": combine.get("passage_ids") or []})
    if direct:
        used_ids.append({"passage_ids": (draft.get("direct_answer") or {}).get("passage_ids") or []})
    answer = Answer(
        status=AnswerStatus.ANSWERED,
        speech_text=speech,
        display_text=multi.build_display(services, sections, conflicts, combine_text, asks_combine, direct),
        service_id=services[0].id,
        confidence=_clamp(state.get("confidence")),
        router_source=state.get("router_source"),
        checklist=checklists[0],
        citations=build_citations([*claims, *used_ids], passages),
        llm_backend=deps.llm_backend,
        service_ids=tuple(s.id for s in services),
        checklists=checklists,
        conflicts=conflicts,
        situation=situation_profile(state.get("situation")),
        mode="multi" if len(services) > 1 else "single",
    )
    return {"answer": answer}


def _store_in_cache(state: AgentState, deps: AgentDeps, answer: Answer) -> None:
    """Only `answered` results are stored (FR-AGT-15), and only if a cache key was set."""
    key = state.get("cache_key")
    if not key or deps.cache is None or answer.status is not AnswerStatus.ANSWERED:
        return
    try:
        deps.cache.set(key, answer)
    except Exception:
        log.exception("answer cache write failed")


def _supported_claims(state: AgentState) -> list[dict[str, Any]]:
    verified = state.get("verified_claims")
    if verified is None:  # not verified (follow-up path, tests): use the draft's claims
        return list(state["draft"].get("claims") or [])
    return [c for c in verified if c.get("supported")]


def finalize_follow_up(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Asks the one missing eligibility fact (FR-AGT-09); the next turn keeps this service.

    The question comes from `understand` (FR-AGT-23, possibly before any service is known, or to
    tell two services apart) or from `generate`. Two candidate services are kept as "a,b".
    """
    raw = _text(state.get("follow_up")) or _text((state.get("draft") or {}).get("follow_up_question"))
    question = to_bangla_digits(raw)
    ids = [sid for sid in state.get("service_ids") or [] if sid in deps.services and sid != OTHER]
    service_id = state.get("service_id")
    if len(ids) > 1:
        service_id = ServiceSet.format(ids)
    elif service_id == OTHER:
        service_id = None
    answer = Answer(
        status=AnswerStatus.FOLLOW_UP,
        speech_text=question,
        display_text=question,
        service_id=service_id or None,
        service_ids=tuple(ids),
        confidence=_clamp(state.get("confidence")),
        router_source=state.get("router_source"),
        follow_up_question=question,
        llm_backend=deps.llm_backend,
        situation=situation_profile(state.get("situation")),
    )
    return {"answer": answer}


def fallback(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """The exact FALLBACK text (FR-AGT-04, FR-AGT-13)."""
    service_id = state.get("service_id")
    answer = Answer(
        status=AnswerStatus.FALLBACK,
        speech_text=FALLBACK,
        display_text=FALLBACK,
        service_id=service_id if service_id and service_id != OTHER else None,
        confidence=_clamp(state.get("confidence")),
        router_source=state.get("router_source"),
        llm_backend=deps.llm_backend,
    )
    return {"answer": answer}


# ---------------------------------------------------------------- answer parts


def situation_profile(raw: Any) -> SituationProfile | None:
    """The `understand` result as a domain value (None when there was none)."""
    if not isinstance(raw, Mapping):
        return None
    facts = raw.get("facts") if isinstance(raw.get("facts"), Mapping) else {}
    summary = _text(raw.get("summary_bn"))
    pairs = tuple((str(k), str(v)) for k, v in facts.items())
    return SituationProfile(summary, pairs) if summary or pairs else None


def build_checklist(raw: Any, service: Service, unsupported: Sequence[str] = ()) -> Checklist:
    """The checklist card and SMS. Fields the verifier found unsupported are replaced, never shown."""
    data = dict(raw) if isinstance(raw, Mapping) else {}
    for field in unsupported:
        data[field] = [] if field == "papers" else ""
    papers = data.get("papers") if isinstance(data.get("papers"), list) else []
    where = _text(data.get("where")) or (UNKNOWN_BN if "where" in unsupported else service.office_bn)
    return Checklist(
        service_id=service.id,
        who=to_bangla_digits(_text(data.get("who")) or UNKNOWN_BN),
        papers=tuple(to_bangla_digits(_text(p)) for p in papers if _text(p)),
        fee=to_bangla_digits(_text(data.get("fee")) or UNKNOWN_BN),
        where=where,
        decision=_text(data.get("decision")) or DECISION_NOTE,
    )


def build_citations(claims: Any, passages: Sequence[Passage]) -> tuple[Citation, ...]:
    """The documents the claims cite, in order, one citation per document (source URL).

    If no claim cites a valid passage, the best passage is used, so an answer always has a source.
    """
    by_id = {prompts.passage_id(i): p for i, p in enumerate(passages)}
    cited: list[Passage] = []
    for claim in claims if isinstance(claims, list) else []:
        ids = claim.get("passage_ids", []) if isinstance(claim, Mapping) else []
        for pid in ids if isinstance(ids, list) else []:
            passage = by_id.get(_text(pid).strip("[]").upper())
            if passage is not None and all(p.source_url != passage.source_url for p in cited):
                cited.append(passage)
    if not cited and passages:
        cited = [passages[0]]
    return tuple(
        Citation(title=p.title, source_url=p.source_url, snippet=_snippet(p.text), chunk_id=p.chunk_id)
        for p in cited
    )


def _snippet(text: str) -> str:
    words = text.split()
    return " ".join(words[:SNIPPET_WORDS]) + (" …" if len(words) > SNIPPET_WORDS else "")
