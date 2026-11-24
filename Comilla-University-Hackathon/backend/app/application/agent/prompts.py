"""Prompt templates and JSON schemas for the agent's LLM calls (SRS Appendix B, FR-AGT-03, 06 to 10).

Passages are shown as `[P1] title: text` so claims can cite `P1`. Instructions are in English
(models follow them best); everything the citizen sees must come back in Bangla.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from app.application.ports.retrieval import Passage
from app.domain.entities import Message, Service
from app.domain.messages_bn import DECISION_NOTE
from app.domain.policies import HISTORY_TURNS_FOR_PROMPT, MAX_SPEECH_WORDS
from app.domain.value_objects import Channel, Role

# ---------------------------------------------------------------- shared pieces


def passage_id(index: int) -> str:
    return f"P{index + 1}"


def format_passages(passages: Sequence[Passage]) -> str:
    return "\n\n".join(f"[{passage_id(i)}] {p.title}: {p.text}" for i, p in enumerate(passages))


def format_history(history: Sequence[Message], turns: int = HISTORY_TURNS_FOR_PROMPT) -> str:
    """The last `turns` question/answer pairs, oldest first, or "(none)"."""
    recent = list(history)[-2 * turns :]
    if not recent:
        return "(none)"
    who = {Role.USER: "Citizen", Role.ASSISTANT: "Ek Call"}
    return "\n".join(f"{who[m.role]}: {m.text}" for m in recent)


def format_services(services: Mapping[str, Service]) -> str:
    return "\n".join(f"- {s.id}: {s.name_bn} ({s.name_en})" for s in services.values())


# ---------------------------------------------------------------- llm_classify (FR-AGT-03)

CLASSIFY_PROMPT = """You route questions for "Ek Call", a Bangla phone helpline about Bangladesh
government services. Pick the ONE label the citizen's latest question is about.

Labels:
{labels}
Use `other` for anything that is not one of these services (other government services, land
disputes, health, weather, jokes...).

Hints from a small classifier (may be wrong): {hints}

Conversation so far (use it to understand short replies such as "হ্যাঁ" or "আর কী লাগে?"):
{history}

Latest question: {question}

Return JSON with `service_id` (one label), `confidence` (0 to 1) and `search_query`: the latest
question rewritten in Bangla as one complete question that makes sense without the conversation
(for example "আর কোথায় জমা দেবো?" after a widow allowance question -> "বিধবা ভাতার আবেদন কোথায়
জমা দিতে হয়?")."""


def classify_schema(labels: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "service_id": {"type": "string", "enum": list(labels)},
            "confidence": {"type": "number"},
            "search_query": {"type": "string"},
        },
        "required": ["service_id", "confidence"],
    }


def build_classify_prompt(
    question: str,
    services: Mapping[str, Service],
    hints: Sequence[tuple[str, float]] = (),
    history: Sequence[Message] = (),
) -> str:
    hint_text = ", ".join(f"{label} {score:.2f}" for label, score in hints[:3]) or "(none)"
    return CLASSIFY_PROMPT.format(
        labels=format_services(services),
        hints=hint_text,
        history=format_history(history),
        question=question,
    )


# ---------------------------------------------------------------- generate (FR-AGT-08, 09, 11)

GENERATE_PROMPT = """You are "Ek Call", a Bangla helpline that explains Bangladesh government
services to rural and elderly citizens. Service: {service_name}. Channel: {channel}.

Official passages (the ONLY allowed source of facts):
{passages}

Conversation so far (ONLY to understand what the citizen means; earlier answers in it may be
wrong or sample text, so never copy facts, amounts, fees or wording from them):
{history}

Citizen's question: {question}

Rules:
1. Answer only from the passages above. If they do not answer the question, return
   "no_answer": true and leave the other text fields empty. A passage on a related topic is
   NOT an answer: if the citizen asks how to do something (for example how to file a court
   case or settle a boundary dispute) and the passages only describe a different procedure
   (for example how to check whether a case exists), return "no_answer": true.
2. Write everyday Bangla in short sentences for an elderly listener. In speech_text avoid
   English words unless there is no Bangla word. Write all numbers in Bangla digits (৬৫, not 65).
   Never assume facts the citizen did not say (gender, income, residence); state the rule instead.
3. speech_text: at most {max_words} words, the direct answer first. {channel_rule}
4. Never promise that the citizen will get the benefit. Explain the rules and who decides.
   The checklist field `decision` says who decides; if unsure, use: "{decision_note}"
5. display_text: Bangla markdown for a screen: a bold title line, then short bullet points.
6. checklist: who (who can apply), papers (list of documents), fee, where (office or website),
   decision. Use only facts from the passages; write "তথ্য পাওয়া যায়নি" for an unknown field.
   In `where`, name the person or office to go to in plain words a villager understands: write
   the person instead of his equipment ("ইউনিয়ন সমাজকর্মীর ডিভাইস" -> "ইউনিয়ন সমাজকর্মীর কাছে"),
   and keep every office or website the passage names.
7. claims: every fact you state, each with the passage_ids that support it (for example ["P1"])
   and core = true when the answer is wrong without it.
8. follow_up_question: almost always EMPTY. Conditions the citizen did not mention (gender,
   income, residence, documents) are explained in the answer as rules, never asked. Ask ONE
   short Bangla question only when the question cannot be answered usefully at all without one
   fact (for example: they ask "কী লাগবে?" for a correction but did not say what is wrong).
   Still fill every other field. Never ask about something already said in the conversation.
9. Output JSON only, matching the schema exactly."""

# The call adds the SMS sentence itself, only when an SMS is really queued (speech.py, FR-SMS-01).
_VOICE_RULE = (
    "It is spoken on a phone call: at most 3 short sentences, no lists, the most important fact "
    "first. Do not mention SMS."
)
_APP_RULE = "The citizen reads the answer on a screen."

GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "no_answer": {"type": "boolean"},
        "speech_text": {"type": "string"},
        "display_text": {"type": "string"},
        "checklist": {
            "type": "object",
            "properties": {
                "who": {"type": "string"},
                "papers": {"type": "array", "items": {"type": "string"}},
                "fee": {"type": "string"},
                "where": {"type": "string"},
                "decision": {"type": "string"},
            },
            "required": ["who", "papers", "fee", "where", "decision"],
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "passage_ids": {"type": "array", "items": {"type": "string"}},
                    "core": {"type": "boolean"},
                },
                "required": ["text", "passage_ids", "core"],
            },
        },
        "follow_up_question": {"type": "string"},
    },
    "required": ["no_answer", "speech_text", "display_text", "checklist", "claims"],
}


def build_generate_prompt(
    question: str,
    service: Service,
    passages: Sequence[Passage],
    history: Sequence[Message],
    channel: Channel,
) -> str:
    return GENERATE_PROMPT.format(
        service_name=f"{service.name_bn} ({service.name_en})",
        channel="phone call" if channel is Channel.VOICE else "web app",
        passages=format_passages(passages),
        history=format_history(history),
        question=question,
        max_words=MAX_SPEECH_WORDS,
        channel_rule=_VOICE_RULE if channel is Channel.VOICE else _APP_RULE,
        decision_note=DECISION_NOTE,
    )


# ---------------------------------------------------------------- grade (FR-AGT-06)

GRADE_PROMPT = """You check search results for a Bangla helpline about Bangladesh government services.
Citizen's question: {question}

Passages:
{passages}

Return the IDs of the passages that contain information useful for answering the question
(rules, eligibility, papers, fees, offices, steps or amounts on the same topic). Be generous:
partly useful counts. Return an empty list only when none of them is about the question."""

GRADE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"relevant_ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["relevant_ids"],
}


def build_grade_prompt(question: str, passages: Sequence[Passage]) -> str:
    return GRADE_PROMPT.format(question=question, passages=format_passages(passages))


# ---------------------------------------------------------------- rewrite_query (FR-AGT-07)

REWRITE_PROMPT = """A search over official Bangla documents about "{service_name}" found nothing useful
for the citizen's question. Rewrite it as one clear, formal Bangla search query (the words an
official document would use), keeping the meaning. Use the conversation to fill in what a short
reply refers to. Previous query: {query}

Conversation so far:
{history}

Citizen's question: {question}

Return JSON with `query`."""

REWRITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}


def build_rewrite_prompt(question: str, query: str, service: Service, history: Sequence[Message]) -> str:
    return REWRITE_PROMPT.format(
        service_name=f"{service.name_bn} ({service.name_en})",
        query=query,
        history=format_history(history),
        question=question,
    )


# ---------------------------------------------------------------- verify (FR-AGT-10)

VERIFY_PROMPT = """You are a strict fact checker for a Bangla helpline about government services.
Check every numbered claim, and the spoken answer, against the official passages ONLY.
A claim is supported when a passage states the same fact (other wording is fine). Numbers,
ages, amounts and fees must have the same value; Bangla digits, English digits and numbers
written as words are the same (৬৫ = 65 = পঁয়ষট্টি). Repeating what the citizen said about
themselves (for example their age), conditional wording ("পুরুষ হলে ...") and general advice
such as "contact the office" or "the office decides" count as supported.

Passages:
{passages}

Citizen's question: {question}

Claims:
{claims}

Spoken answer: {speech}

Screen text: {display}

Checklist:
{checklist}

Return JSON: `claims` = one item per claim with its `index` and `supported` (true/false);
`speech_supported` = false if the spoken answer states any fact the passages do not support;
`display_supported` = false if the screen text states any fact the passages do not support;
`unsupported_checklist` = the checklist fields (who, papers, fee, where, decision) that state a
fact the passages do not support. "তথ্য পাওয়া যায়নি" (not found) is always supported. A fee such
as "বিনামূল্যে" (free) is supported only if a passage says so.
`answers_question` = true only if the spoken answer gives what the citizen asked for. It is false
when it answers a different question on the same topic (for example the citizen asks what to do
when a court case happens and the answer only says how to find out whether a case exists)."""

VERIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "supported": {"type": "boolean"}},
                "required": ["index", "supported"],
            },
        },
        "speech_supported": {"type": "boolean"},
        "display_supported": {"type": "boolean"},
        "answers_question": {"type": "boolean"},
        "unsupported_checklist": {
            "type": "array",
            "items": {"type": "string", "enum": ["who", "papers", "fee", "where", "decision"]},
        },
    },
    "required": [
        "claims",
        "speech_supported",
        "display_supported",
        "answers_question",
        "unsupported_checklist",
    ],
}


CHECKLIST_FIELDS = ("who", "papers", "fee", "where", "decision")


def format_checklist(checklist: Mapping[str, Any] | None) -> str:
    lines = []
    for field in CHECKLIST_FIELDS:
        value = (checklist or {}).get(field)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"- {field}: {value or '(empty)'}")
    return "\n".join(lines)


# Two-service answers end with fixed sentences (CONFLICT_NOTE, COMBINE_UNKNOWN). They never come
# from the LLM, and an honest "the documents do not say" answers that part of the question.
VERIFY_MULTI_NOTE = """

This answer covers TWO services. Its last sentences are fixed texts of the helpline (they say the
rules differ, or that the official documents do not say whether both can be received together).
Do not check them against the passages. For `answers_question`, such a sentence counts as an
honest answer to that part of the question."""


def build_verify_prompt(
    claims: Sequence[str],
    speech: str,
    passages: Sequence[Passage],
    display: str = "",
    checklist: Mapping[str, Any] | None = None,
    question: str = "",
    multi: bool = False,
) -> str:
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(claims)) or "(none)"
    return VERIFY_PROMPT.format(
        passages=format_passages(passages),
        question=question or "(unknown)",
        claims=numbered,
        speech=speech,
        display=display or "(none)",
        checklist=format_checklist(checklist),
    ) + (VERIFY_MULTI_NOTE if multi else "")


# ---------------------------------------------------------------- understand (FR-AGT-19, 23)

UNDERSTAND_PROMPT = """You help "Ek Call", a Bangla phone helpline about Bangladesh government services.
Citizens often describe their life situation instead of naming a service ("my husband died and I
cannot run the family" means widow allowance). Read the situation and decide which services it is
about.

Services (id: Bangla name (English name) - words the official documents use):
{labels}

Hints from small classifiers (may be wrong): {hints}

Conversation so far (use it to understand short replies such as "হ্যাঁ" or "৭০ বছর"):
{history}

Latest message: {question}

Rules:
1. `services`: at most {max_services} ids from the list above, the most relevant first. Use two
   only when the citizen really asks about two services (for example a widow aged 66 asking about
   two allowances). Never use `other` here.
2. `out_of_scope`: true when none of the services fits (crops, animals, health, disputes, weather,
   bills, other government offices...); then `services` is empty.
3. `facts`: only facts the citizen actually said (age, gender, marital_status, disability, goal,
   relation...), as short Bangla values. Never guess a fact that was not said.
4. `summary_bn`: one short Bangla line with what you understood, for example
   "স্বামী মারা গেছেন, দুই সন্তান, আয় নেই". Empty if out of scope.
5. `search_queries`: for every chosen service, one formal Bangla search query in the official
   documents' own words (for example "বিধবা ভাতা পাওয়ার যোগ্যতা ও প্রয়োজনীয় কাগজ").
6. `needs_follow_up`: almost always false. True only when the message is too vague to pick any
   service (for example "আমি খুব গরিব, সরকার থেকে কি কিছু পাওয়া যায়?"), or when one short question
   would decide between two services. Then `follow_up_question` is ONE short, polite Bangla
   question (for example "আপনার বা আপনার পরিবারের কারো বয়স কি ৬৫ বছরের বেশি, নাকি কেউ বিধবা বা
   প্রতিবন্ধী?"). {follow_up_rule}
7. Output JSON only, matching the schema."""

_FOLLOW_UP_ALLOWED = "Never ask about something the conversation already says."
_FOLLOW_UP_USED = (
    "A follow-up question was ALREADY asked in this conversation: needs_follow_up must be false; "
    "choose the best service(s) from what was said, or out_of_scope."
)


def understand_schema(labels: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "services": {"type": "array", "items": {"type": "string", "enum": list(labels)}},
            "out_of_scope": {"type": "boolean"},
            "facts": {"type": "object", "additionalProperties": {"type": "string"}},
            "summary_bn": {"type": "string"},
            "search_queries": {"type": "object", "additionalProperties": {"type": "string"}},
            "needs_follow_up": {"type": "boolean"},
            "follow_up_question": {"type": "string"},
        },
        "required": ["services", "out_of_scope", "summary_bn", "search_queries", "needs_follow_up"],
    }


def format_services_with_terms(services: Mapping[str, Service]) -> str:
    lines = []
    for s in services.values():
        if s.id == "other":
            continue
        terms = f" - {s.search_terms_bn}" if s.search_terms_bn else ""
        lines.append(f"- {s.id}: {s.name_bn} ({s.name_en}){terms}")
    return "\n".join(lines)


def build_understand_prompt(
    question: str,
    services: Mapping[str, Service],
    hints: Sequence[tuple[str, float]] = (),
    history: Sequence[Message] = (),
    max_services: int = 2,
    follow_up_used: bool = False,
) -> str:
    hint_text = ", ".join(f"{label} {score:.2f}" for label, score in hints[:6]) or "(none)"
    return UNDERSTAND_PROMPT.format(
        labels=format_services_with_terms(services),
        hints=hint_text,
        history=format_history(history),
        question=question,
        max_services=max_services,
        follow_up_rule=_FOLLOW_UP_USED if follow_up_used else _FOLLOW_UP_ALLOWED,
    )


# ---------------------------------------------------------------- generate, two services (FR-AGT-21, 22)


def format_passages_grouped(passages: Sequence[Passage]) -> str:
    """`[old_age_allowance][P1] title: text`, so every passage shows which service it belongs to."""
    return "\n\n".join(
        f"[{p.service_id}][{passage_id(i)}] {p.title}: {p.text}" for i, p in enumerate(passages)
    )


GENERATE_MULTI_PROMPT = """You are "Ek Call", a Bangla helpline that explains Bangladesh government
services to rural and elderly citizens. The citizen asks about TWO services: {service_names}.
Channel: {channel}.

Official passages, each marked with the service it belongs to (the ONLY allowed source of facts):
{passages}

What we understood about the citizen (only to point to the relevant rule, NEVER to decide
eligibility): {situation}

Conversation so far (only to understand the question; never copy facts from it):
{history}

Citizen's question: {question}

Rules:
1. One section per service, in this order: {service_ids}. Write each service's rules ONLY from
   that service's own passages. A claim's service_id must be its section's service, and its
   passage_ids must be passages of that same service.
2. Never mix the rules of two services in one sentence or one claim.
3. If the two services' rules differ on the same point (age, papers, office, amount...), add it
   to `conflicts`: one side per service, each with its own rule and its own passage_ids. Do NOT
   say which rule wins or applies.
4. `asks_combine`: true when the citizen asks whether both can be received together.
   `combine_rule.stated` is true ONLY if a passage says whether both can be received together;
   then `text_bn` repeats what it says, as a rule ("... নিয়ম অনুযায়ী ..."), and `passage_ids` cite it.
   A passage saying that a person who already receives another regular government allowance
   cannot get this one IS such a rule. Otherwise stated=false and never write "yes" or "no" about
   receiving both. A rule that both services state the same way is NOT a conflict.
5. `direct_answer`: when the citizen asks one direct question across the services (which one to do
   first, which one fits, whether one is needed for the other), answer it in ONE short Bangla
   sentence that a passage supports, with its `passage_ids`; for example, if the passport passage
   says the online birth certificate is needed, then "আগে জন্ম নিবন্ধন করুন, কারণ পাসপোর্টের আবেদনে
   জন্ম নিবন্ধন সনদ লাগে". Set stated=true only then. If no passage supports an answer, stated=false
   and never guess.
6. Everyday Bangla, short sentences, Bangla digits. Never promise the benefit. Never assume facts
   the citizen did not say. speech_text: ONE short sentence of at most {section_words} words per
   section, with the most important rule for this citizen. {channel_rule}
7. checklist per section: who, papers, fee, where, decision, only from that service's passages;
   write "তথ্য পাওয়া যায়নি" for an unknown field.
8. claims: every fact, with passage_ids and core = true when the section is wrong without it.
9. If the passages do not answer the question for either service, return "no_answer": true.
10. follow_up_question: almost always empty (see the single-service rules: ask only when nothing
   useful can be said without one fact).
11. Output JSON only, matching the schema exactly."""

_CLAIM_ITEM: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "service_id": {"type": "string"},
        "passage_ids": {"type": "array", "items": {"type": "string"}},
        "core": {"type": "boolean"},
    },
    "required": ["text", "service_id", "passage_ids", "core"],
}

GENERATE_MULTI_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "no_answer": {"type": "boolean"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "string"},
                    "speech_text": {"type": "string"},
                    "display_text": {"type": "string"},
                    "checklist": GENERATE_SCHEMA["properties"]["checklist"],
                    "claims": {"type": "array", "items": _CLAIM_ITEM},
                },
                "required": ["service_id", "speech_text", "checklist", "claims"],
            },
        },
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic_bn": {"type": "string"},
                    "sides": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "rule_bn": {"type": "string"},
                                "passage_ids": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["service_id", "rule_bn", "passage_ids"],
                        },
                    },
                },
                "required": ["topic_bn", "sides"],
            },
        },
        "asks_combine": {"type": "boolean"},
        "combine_rule": {
            "type": "object",
            "properties": {
                "stated": {"type": "boolean"},
                "text_bn": {"type": "string"},
                "passage_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["stated"],
        },
        "direct_answer": {
            "type": "object",
            "properties": {
                "stated": {"type": "boolean"},
                "text_bn": {"type": "string"},
                "passage_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["stated"],
        },
        "follow_up_question": {"type": "string"},
    },
    "required": ["no_answer", "sections", "conflicts", "asks_combine", "combine_rule", "direct_answer"],
}

SECTION_WORDS = 10  # the fixed texts (intro and notes) take up to 37 of the 60 spoken words


def build_generate_multi_prompt(
    question: str,
    services: Sequence[Service],
    passages: Sequence[Passage],
    history: Sequence[Message],
    channel: Channel,
    situation: str = "",
) -> str:
    return GENERATE_MULTI_PROMPT.format(
        service_names=" and ".join(f"{s.name_bn} ({s.name_en})" for s in services),
        service_ids=", ".join(s.id for s in services),
        channel="phone call" if channel is Channel.VOICE else "web app",
        passages=format_passages_grouped(passages),
        situation=situation or "(nothing)",
        history=format_history(history),
        question=question,
        section_words=SECTION_WORDS,
        channel_rule=_VOICE_RULE if channel is Channel.VOICE else _APP_RULE,
    )
