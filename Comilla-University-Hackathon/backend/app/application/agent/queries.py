"""Query expansion for retrieval (sprint T4, FR-AGT-20). Pure functions: domain + stdlib only.

Callers say "স্বামী মারা গেছেন"; the documents say "বিধবা". So each service is searched with
(a) the caller's words, (b) the service's official words from services.yaml and (c) the query
`understand` wrote, and the results are merged by chunk, keeping the best score.
"""

from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar

from app.domain.entities import Service


class _Scored(Protocol):
    @property
    def chunk_id(self) -> str: ...

    @property
    def score(self) -> float: ...


P = TypeVar("P", bound=_Scored)


def build_queries(question: str, service: Service, llm_query: str = "", expansion: bool = True) -> list[str]:
    """[question, "<name> <official words>", llm_query] without empty or repeated ones.

    With expansion off only the caller's words are searched (the old behaviour).
    """
    if not expansion:
        return [question.strip()] if question.strip() else []
    official = f"{service.name_bn} {service.search_terms_bn}".strip()
    queries: list[str] = []
    for raw in (question, official, llm_query):
        query = " ".join((raw or "").split())
        if query and query.casefold() not in {q.casefold() for q in queries}:
            queries.append(query)
    return queries


def merge_best(results: Iterable[Sequence[P]], k: int) -> list[P]:
    """One list, best first: each chunk once with its best score, at most `k`."""
    best: dict[str, P] = {}
    for found in results:
        for passage in found:
            kept = best.get(passage.chunk_id)
            if kept is None or passage.score > kept.score:
                best[passage.chunk_id] = passage
    return sorted(best.values(), key=lambda p: p.score, reverse=True)[:k]
