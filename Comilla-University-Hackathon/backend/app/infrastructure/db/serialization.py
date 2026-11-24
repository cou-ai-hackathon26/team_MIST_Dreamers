"""Domain objects <-> JSON text, for the *_json columns. Bangla is kept readable (ensure_ascii=False)."""

import json
from collections.abc import Sequence
from typing import Any

from app.domain.entities import Answer, Checklist, Citation
from app.domain.value_objects import AnswerStatus, RouterSource


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def checklist_to_dict(c: Checklist) -> dict[str, Any]:
    return {
        "service_id": c.service_id,
        "who": c.who,
        "papers": list(c.papers),
        "fee": c.fee,
        "where": c.where,
        "decision": c.decision,
    }


def checklist_from_dict(d: dict[str, Any]) -> Checklist:
    return Checklist(
        service_id=d["service_id"],
        who=d["who"],
        papers=tuple(d["papers"]),
        fee=d["fee"],
        where=d["where"],
        decision=d["decision"],
    )


def citation_to_dict(c: Citation) -> dict[str, Any]:
    return {"title": c.title, "source_url": c.source_url, "snippet": c.snippet, "chunk_id": c.chunk_id}


def citation_from_dict(d: dict[str, Any]) -> Citation:
    return Citation(
        title=d["title"], source_url=d["source_url"], snippet=d["snippet"], chunk_id=d["chunk_id"]
    )


def checklist_to_json(c: Checklist) -> str:
    return _dumps(checklist_to_dict(c))


def checklist_from_json(text: str) -> Checklist:
    return checklist_from_dict(json.loads(text))


def citations_to_json(citations: Sequence[Citation]) -> str:
    return _dumps([citation_to_dict(c) for c in citations])


def citations_from_json(text: str) -> tuple[Citation, ...]:
    return tuple(citation_from_dict(d) for d in json.loads(text))


def answer_to_json(a: Answer) -> str:
    return _dumps(
        {
            "status": a.status.value,
            "speech_text": a.speech_text,
            "display_text": a.display_text,
            "service_id": a.service_id,
            "confidence": a.confidence,
            "router_source": a.router_source.value if a.router_source else None,
            "checklist": checklist_to_dict(a.checklist) if a.checklist else None,
            "citations": [citation_to_dict(c) for c in a.citations],
            "follow_up_question": a.follow_up_question,
            "timings": dict(a.timings),
            "llm_calls": a.llm_calls,
            "llm_backend": a.llm_backend,
        }
    )


def answer_from_json(text: str) -> Answer:
    d = json.loads(text)
    return Answer(
        status=AnswerStatus(d["status"]),
        speech_text=d["speech_text"],
        display_text=d["display_text"],
        service_id=d["service_id"],
        confidence=d["confidence"],
        router_source=RouterSource(d["router_source"]) if d["router_source"] else None,
        checklist=checklist_from_dict(d["checklist"]) if d["checklist"] else None,
        citations=tuple(citation_from_dict(c) for c in d["citations"]),
        follow_up_question=d["follow_up_question"],
        timings=d["timings"],
        llm_calls=d["llm_calls"],
        llm_backend=d.get("llm_backend"),
    )
