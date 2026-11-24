"""grounding_guard (sprint T5, FR-AGT-22): plain code, no LLM, runs after `generate`, before `verify`.

Rules can never be blended across services:
- a claim is dropped if it cites an unknown passage, or a passage of another service;
- a conflict is kept only with at least 2 sides, from different services, each citing a passage
  of its own service, that really differ (two sides stating the same rule are agreement);
- `combine_rule.stated` (the documents say whether both benefits can be received) and
  `direct_answer.stated` (a one-line answer to "which first?") stay true only when their passages exist;
- `dropped_core` tells routing that a core claim was lost (retry, then fall back).

In single mode an unknown passage id is removed from the claim instead (the claim stays when a
valid id is left), so a typo in one id does not throw away a supported fact; a claim that cites
another service's passage is still dropped.

Standard library only: passages come in as a {passage_id: service_id} map.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

MULTI = "multi"


@dataclass(frozen=True)
class GuardResult:
    draft: dict[str, Any]
    dropped_core: bool = False
    dropped: list[str] = field(default_factory=list)  # short reasons, for the logs


def clean_id(raw: Any) -> str:
    return str(raw).strip().strip("[]").upper() if isinstance(raw, str) else ""


def _ids(item: Mapping[str, Any]) -> list[str]:
    raw = item.get("passage_ids")
    return [clean_id(x) for x in raw] if isinstance(raw, list) else []


def _claim_ok(
    claim: Mapping[str, Any], service_id: str, passages: Mapping[str, str], strict: bool
) -> tuple[dict[str, Any] | None, str]:
    """The claim as kept (possibly with fewer ids), or None and the reason it was dropped."""
    ids = _ids(claim)
    unknown = [i for i in ids if i not in passages]
    if unknown and strict:
        return None, f"unknown passage {unknown[0]}"
    known = [i for i in ids if i in passages]
    if not known:
        return None, "no valid passage"
    if any(passages[i] != service_id for i in known):
        return None, f"cites another service's passage for {service_id}"
    return {**claim, "service_id": service_id, "passage_ids": known}, ""


def _guard_claims(
    claims: Any, service_id: str, passages: Mapping[str, str], strict: bool, dropped: list[str]
) -> tuple[list[dict[str, Any]], bool]:
    kept: list[dict[str, Any]] = []
    core_lost = False
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, Mapping):
            continue
        tagged = str(claim.get("service_id") or service_id)
        if tagged != service_id:  # a claim tagged with another service inside this section
            dropped.append(f"claim tagged {tagged} in the {service_id} section")
            core_lost = core_lost or bool(claim.get("core"))
            continue
        ok, reason = _claim_ok(claim, service_id, passages, strict)
        if ok is None:
            dropped.append(reason)
            core_lost = core_lost or bool(claim.get("core"))
        else:
            kept.append(ok)
    return kept, core_lost


def _guard_conflicts(
    conflicts: Any, services: Sequence[str], passages: Mapping[str, str]
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for conflict in conflicts if isinstance(conflicts, list) else []:
        if not isinstance(conflict, Mapping):
            continue
        sides = []
        for side in conflict.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            sid = str(side.get("service_id") or "")
            ids = _ids(side)
            if (
                sid in services
                and ids
                and all(passages.get(i) == sid for i in ids)
                and str(side.get("rule_bn") or "").strip()
            ):
                sides.append({**side, "service_id": sid, "passage_ids": ids})
        if len(sides) >= 2 and len({s["service_id"] for s in sides}) >= 2 and not _same_rule(sides):
            kept.append({**conflict, "sides": sides})
    return kept


SAME_RULE_OVERLAP = 0.8  # word overlap at which two sides say the same thing


def _rule_words(text: str) -> set[str]:
    # ী/ি and ূ/ু are common spelling variants ("সরকারী" = "সরকারি"); punctuation is ignored.
    text = text.replace("\u09c0", "\u09bf").replace("\u09c2", "\u09c1")
    return set(re.findall(r"[\w\u0980-\u09ff]+", text.lower()))


def _same_rule(sides: Sequence[Mapping[str, Any]]) -> bool:
    """Two services that state the same rule do not conflict: that is agreement, not a conflict."""
    words = [_rule_words(str(side.get("rule_bn") or "")) for side in sides]
    a, b = words[0], words[1]
    return bool(a and b) and len(a & b) / len(a | b) >= SAME_RULE_OVERLAP


def _guard_combine(rule: Any, passages: Mapping[str, str]) -> dict[str, Any]:
    data = dict(rule) if isinstance(rule, Mapping) else {}
    ids = _ids(data)
    stated = bool(data.get("stated")) and bool(ids) and all(i in passages for i in ids)
    stated = stated and bool(str(data.get("text_bn") or "").strip())
    return {
        "stated": stated,
        "text_bn": data.get("text_bn") if stated else None,
        "passage_ids": ids if stated else [],
    }


def grounding_guard(
    draft: Mapping[str, Any],
    passages: Mapping[str, str],
    mode: str = "single",
    primary: str = "",
    services: Sequence[str] = (),
) -> GuardResult:
    """Returns the draft with every ungrounded claim, conflict and combine rule removed."""
    out = dict(draft)
    dropped: list[str] = []
    if mode != MULTI:
        claims, core_lost = _guard_claims(
            draft.get("claims"), primary, passages, strict=False, dropped=dropped
        )
        out["claims"] = claims
        return GuardResult(out, core_lost, dropped)

    allowed = list(services)
    sections: list[dict[str, Any]] = []
    core_lost = False
    for section in draft.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        sid = str(section.get("service_id") or "")
        if sid not in allowed or any(s["service_id"] == sid for s in sections):
            dropped.append(f"section for {sid or 'no service'} not asked for")
            continue
        claims, lost = _guard_claims(section.get("claims"), sid, passages, strict=True, dropped=dropped)
        core_lost = core_lost or lost
        sections.append({**section, "service_id": sid, "claims": claims})
    out["sections"] = sections
    out["conflicts"] = _guard_conflicts(draft.get("conflicts"), allowed, passages)
    out["combine_rule"] = _guard_combine(draft.get("combine_rule"), passages)
    out["direct_answer"] = _guard_combine(draft.get("direct_answer"), passages)  # same rule: real passages
    if len(out["conflicts"]) < len(draft.get("conflicts") or []):
        dropped.append("conflict without two grounded sides")
    return GuardResult(out, core_lost, dropped)
