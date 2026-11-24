"""Two-service answers (sprint T5, FR-AGT-21, 22): verify items and build the final Answer.

One `verify` call checks every section claim, every non-empty checklist field, every conflict side
and a stated combine rule. Results are mapped back: an unsupported conflict side drops the
conflict, an unsupported checklist field becomes "তথ্য পাওয়া যায়নি", an unsupported combine rule
becomes "not stated" (so COMBINE_UNKNOWN is said instead).

Speech: MULTI_INTRO + one short line per service + CONFLICT_NOTE (if conflicts) + COMBINE_UNKNOWN
(the caller asked about getting both and no document says it), capped at MAX_SPEECH_WORDS_MULTI.
The fixed notes are never cut; the per-service lines share the remaining words.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.application.agent import prompts
from app.application.agent.grounding import clean_id
from app.application.ports.retrieval import Passage
from app.domain.entities import Checklist, Conflict, ConflictSide, Service
from app.domain.messages_bn import COMBINE_UNKNOWN, CONFLICT_NOTE, DECISION_NOTE, MULTI_INTRO

UNKNOWN_BN = "তথ্য পাওয়া যায়নি"


@dataclass(frozen=True)
class Item:
    """One thing the verifier checks, and where its verdict goes back to."""

    text: str
    kind: str  # claim | checklist | conflict | combine
    service_id: str = ""
    ref: tuple[int, ...] = ()  # (section, claim) | (section,) + field via `field` | (conflict, side)
    field: str = ""
    core: bool = False


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def verify_items(draft: Mapping[str, Any], names: Mapping[str, str]) -> list[Item]:
    items: list[Item] = []
    for si, section in enumerate(draft.get("sections") or []):
        sid = section["service_id"]
        name = names.get(sid, sid)
        for ci, claim in enumerate(section.get("claims") or []):
            if _text(claim.get("text")):
                items.append(
                    Item(
                        f"[{name}] {_text(claim['text'])}",
                        "claim",
                        sid,
                        (si, ci),
                        core=bool(claim.get("core")),
                    )
                )
        checklist = section.get("checklist") if isinstance(section.get("checklist"), Mapping) else {}
        for field in prompts.CHECKLIST_FIELDS:
            value = checklist.get(field)
            value = (
                ", ".join(_text(v) for v in value if _text(v)) if isinstance(value, list) else _text(value)
            )
            if value and value != UNKNOWN_BN and field != "decision":
                items.append(Item(f"[{name}] {field}: {value}", "checklist", sid, (si,), field=field))
    for ki, conflict in enumerate(draft.get("conflicts") or []):
        for di, side in enumerate(conflict.get("sides") or []):
            sid = side["service_id"]
            items.append(
                Item(f"[{names.get(sid, sid)}] {_text(side.get('rule_bn'))}", "conflict", sid, (ki, di))
            )
    combine = draft.get("combine_rule") or {}
    if combine.get("stated"):
        items.append(Item(_text(combine.get("text_bn")), "combine"))
    direct = draft.get("direct_answer") or {}
    if direct.get("stated"):
        items.append(Item(_text(direct.get("text_bn")), "direct"))
    return items


def apply_verdicts(
    draft: Mapping[str, Any], items: Sequence[Item], verdicts: Mapping[int, bool]
) -> dict[str, Any]:
    """The draft with each claim marked `supported`, unsupported parts removed or blanked."""
    out = {**draft, "sections": [dict(s) for s in draft.get("sections") or []]}
    for section in out["sections"]:
        section["claims"] = [dict(c) for c in section.get("claims") or []]
        section["unsupported_checklist"] = []
    bad_conflicts: set[int] = set()
    combine_ok = direct_ok = True
    for index, item in enumerate(items):
        ok = verdicts.get(index, False)
        if item.kind == "claim":
            out["sections"][item.ref[0]]["claims"][item.ref[1]]["supported"] = ok
        elif item.kind == "checklist" and not ok:
            out["sections"][item.ref[0]]["unsupported_checklist"].append(item.field)
        elif item.kind == "conflict" and not ok:
            bad_conflicts.add(item.ref[0])
        elif item.kind == "combine":
            combine_ok = ok
        elif item.kind == "direct":
            direct_ok = ok
    out["conflicts"] = [c for i, c in enumerate(draft.get("conflicts") or []) if i not in bad_conflicts]
    if not combine_ok:
        out["combine_rule"] = {"stated": False, "text_bn": None, "passage_ids": []}
    if not direct_ok:
        out["direct_answer"] = {"stated": False, "text_bn": None, "passage_ids": []}
    return out


def direct_text(draft: Mapping[str, Any]) -> str | None:
    """The checked one-line answer to the caller's direct question ("which first?"), if any."""
    direct = draft.get("direct_answer") or {}
    return _text(direct.get("text_bn")) or None if direct.get("stated") else None


def flat_claims(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every section claim (with `supported` once verified), for routing and citations."""
    return [c for s in draft.get("sections") or [] for c in s.get("claims") or []]


# ---------------------------------------------------------------- final answer parts


def _words(text: str, limit: int) -> str:
    """At most `limit` words, cut where a listener hears a full thought: whole sentences first,
    else the first sentence up to its last comma that fits, else (rarely) a hard cut."""
    text = " ".join(text.split())
    if len(text.split()) <= limit:
        return text
    sentences = [x.strip() for x in re.split(r"(?<=[।?!])\s+", text) if x.strip()]
    kept: list[str] = []
    for sentence in sentences:
        if len(" ".join([*kept, sentence]).split()) > limit:
            break
        kept.append(sentence)
    if kept:
        return " ".join(kept)
    words = sentences[0].split()[:limit]
    for end in range(len(words), 0, -1):
        if words[end - 1].endswith(","):
            return " ".join(words[:end]).rstrip(",") + "।"
    return " ".join(words).rstrip(",;:।") + "।"


def build_speech(
    names: Sequence[str],
    lines: Sequence[str],
    has_conflicts: bool,
    combine_text: str | None,
    asks_combine: bool,
    max_words: int,
    direct: str | None = None,
) -> str:
    """`direct` (the checked answer to the caller's question) comes right after the intro and is
    never cut, like the fixed notes. The per-service lines share what is left of `max_words`:
    whole lines if they fit, else each line's first sentence, else cuts at a comma, and only as a
    last resort a hard cut."""
    intro = MULTI_INTRO.format(a=names[0], b=names[1]) if len(names) > 1 else ""
    notes = []
    if has_conflicts:
        notes.append(CONFLICT_NOTE)
    if combine_text:
        notes.append(combine_text)
    elif asks_combine:
        notes.append(COMBINE_UNKNOWN)
    head = [part for part in (intro, " ".join((direct or "").split())) if part]
    budget = max_words - sum(len(h.split()) for h in head) - sum(len(n.split()) for n in notes)
    body = _fit([" ".join(line.split()) for line in lines if line.strip()], budget)
    return " ".join(part for part in [*head, *body, *notes] if part)


def _fit(lines: list[str], budget: int) -> list[str]:
    def total(parts: list[str]) -> int:
        return sum(len(p.split()) for p in parts)

    if total(lines) <= budget:
        return lines
    firsts = [_first_sentence(line) for line in lines]
    if total(firsts) <= budget:
        return firsts
    # Shortest first: a short line stays whole and leaves its unused words to the longer one.
    out = list(firsts)
    left = budget
    order = sorted(range(len(firsts)), key=lambda i: len(firsts[i].split()))
    for n, i in enumerate(order):
        share = max(4, left // (len(order) - n))
        out[i] = _words(firsts[i], share)
        left -= len(out[i].split())
    return out


def _first_sentence(text: str) -> str:
    return next((x.strip() for x in re.split(r"(?<=[।?!])\s+", text) if x.strip()), text)


def build_conflicts(conflicts: Any, passages: Sequence[Passage]) -> tuple[Conflict, ...]:
    by_id = {prompts.passage_id(i): p for i, p in enumerate(passages)}
    out: list[Conflict] = []
    for conflict in conflicts if isinstance(conflicts, list) else []:
        sides = []
        for side in conflict.get("sides") or []:
            ids = [clean_id(x) for x in side.get("passage_ids") or []]
            passage = next((by_id[i] for i in ids if i in by_id), None)
            if passage is None:
                continue
            sides.append(
                ConflictSide(
                    service_id=side["service_id"],
                    rule_bn=_text(side.get("rule_bn")),
                    chunk_id=passage.chunk_id,
                    source_title=passage.title,
                    source_url=passage.source_url,
                )  # fmt: skip
            )
        if len(sides) >= 2:
            out.append(Conflict(topic_bn=_text(conflict.get("topic_bn")), sides=tuple(sides)))
    return tuple(out)


def build_display(
    services: Sequence[Service],
    sections: Sequence[Mapping[str, Any]],
    conflicts: Sequence[Conflict],
    combine_text: str | None,
    asks_combine: bool,
    direct: str | None = None,
) -> str:
    names = {s.id: s.name_bn for s in services}
    parts = []
    if len(services) > 1:
        parts.append(MULTI_INTRO.format(a=services[0].name_bn, b=services[1].name_bn))
    if direct:
        parts.append(f"**{direct}**")
    for section in sections:
        text = _text(section.get("display_text")) or _text(section.get("speech_text"))
        parts.append(f"**{names[section['service_id']]}**\n{text}")
    if conflicts:
        lines = []
        for conflict in conflicts:
            lines.append(f"**নিয়ম আলাদা: {conflict.topic_bn}**")
            lines += [f"- {names.get(s.service_id, s.service_id)}: {s.rule_bn}" for s in conflict.sides]
        parts.append("\n".join(lines) + f"\n\n{CONFLICT_NOTE}")
    if combine_text:
        parts.append(combine_text)
    elif asks_combine:
        parts.append(COMBINE_UNKNOWN)
    parts.append(f"_{DECISION_NOTE}_")
    return "\n\n".join(parts)


def checklist_or_none(checklist: Checklist | None) -> tuple[Checklist, ...]:
    return (checklist,) if checklist is not None else ()


def fixed_notes(draft: Mapping[str, Any]) -> str:
    """The fixed sentences finalize adds for this draft (shown to verify so it can judge the answer)."""
    notes = []
    if draft.get("conflicts"):
        notes.append(CONFLICT_NOTE)
    combine = draft.get("combine_rule") or {}
    if draft.get("asks_combine") and not combine.get("stated"):
        notes.append(COMBINE_UNKNOWN)
    return " ".join(notes)
