"""Sprint T4: query expansion and per-service retrieval (FR-AGT-20, 21). Fakes only."""

import dataclasses

from app.application.agent import steps
from app.application.agent.queries import build_queries, merge_best
from app.application.agent.steps import AgentDeps
from app.application.ports.retrieval import Passage
from app.domain.entities import Service
from app.domain.value_objects import Channel
from tests.fakes import FakeClassifier, FakeLLM, FakeRetriever

WIDOW = Service("widow_allowance", "বিধবা ভাতা", "Widow", "অফিস", "বিধবা ভাতা", search_terms_bn="বিধবা স্বামী")
OLD = Service("old_age_allowance", "বয়স্ক ভাতা", "Old age", "অফিস", "বয়স্ক ভাতা", search_terms_bn="বয়স্কভাতা")
OTHER = Service("other", "অন্যান্য", "Other", "৩৩৩", "অন্যান্য")
SERVICES = {s.id: s for s in (OLD, WIDOW, OTHER)}


def passage(chunk: str, service: str, score: float, text: str = "নিয়ম") -> Passage:
    return Passage(chunk, service, "title", f"https://x/{service}", text, score)


def deps(passages: list[Passage], expansion: bool = True) -> AgentDeps:
    return AgentDeps(
        classifier=FakeClassifier({"other": 1.0}), retriever=FakeRetriever(passages), llm=FakeLLM(),
        services=SERVICES, query_expansion=expansion, top_k=5, multi_top_k=3,
    )  # fmt: skip


def test_queries_built_and_deduplicated() -> None:
    queries = build_queries("স্বামী মারা গেছেন", WIDOW, "বিধবা ভাতা যোগ্যতা")
    assert queries == ["স্বামী মারা গেছেন", "বিধবা ভাতা বিধবা স্বামী", "বিধবা ভাতা যোগ্যতা"]
    assert build_queries("বিধবা ভাতা  বিধবা স্বামী", WIDOW, "") == ["বিধবা ভাতা বিধবা স্বামী"]
    assert build_queries("প্রশ্ন", WIDOW, "প্রশ্ন") == ["প্রশ্ন", "বিধবা ভাতা বিধবা স্বামী"]


def test_expansion_off_gives_one_query() -> None:
    assert build_queries("স্বামী মারা গেছেন", WIDOW, "বিধবা ভাতা", expansion=False) == ["স্বামী মারা গেছেন"]


def test_merge_keeps_the_best_score_per_chunk() -> None:
    merged = merge_best([[passage("a", "w", 0.5), passage("b", "w", 0.7)], [passage("a", "w", 0.9)]], k=5)
    assert [(p.chunk_id, p.score) for p in merged] == [("a", 0.9), ("b", 0.7)]
    assert len(merge_best([[passage(str(i), "w", i / 10) for i in range(9)]], k=3)) == 3


def test_single_mode_searches_every_query_with_the_service_filter() -> None:
    d = deps([passage("w1", "widow_allowance", 0.9)])
    state = {"question": "স্বামী নেই", "service_id": "widow_allowance", "service_ids": ["widow_allowance"],
             "search_queries": {"widow_allowance": "বিধবা ভাতা"}, "channel": Channel.APP}  # fmt: skip
    out = steps.retrieve(state, d)  # type: ignore[arg-type]
    searched = d.retriever.searches  # type: ignore[attr-defined]
    assert [q for q, _, _ in searched[:3]] == ["স্বামী নেই", "বিধবা ভাতা বিধবা স্বামী", "বিধবা ভাতা"]
    assert all(sid == "widow_allowance" for _, sid, _ in searched)
    assert [p.chunk_id for p in out["passages"]] == ["w1"]


def test_multi_mode_calls_the_retriever_with_each_service_filter_and_top_3() -> None:
    found = [passage(f"o{i}", "old_age_allowance", 0.9 - i / 10) for i in range(5)]
    found += [passage(f"w{i}", "widow_allowance", 0.8 - i / 10) for i in range(5)]
    d = deps(found)
    state = {"question": "বিধবা, বয়স ৬৬", "service_id": "old_age_allowance",
             "service_ids": ["old_age_allowance", "widow_allowance"], "channel": Channel.APP}  # fmt: skip
    out = steps.retrieve(state, d)  # type: ignore[arg-type]
    filters = {sid for _, sid, _ in d.retriever.searches}  # type: ignore[attr-defined]
    assert filters == {"old_age_allowance", "widow_allowance"}
    assert all(k == 3 for _, _, k in d.retriever.searches[:2])  # type: ignore[attr-defined]
    ids = [p.chunk_id for p in out["passages"]]
    assert ids == ["o0", "o1", "o2", "w0", "w1", "w2"]  # grouped by service, primary first


def test_multi_mode_drops_passages_of_another_service() -> None:
    class MixingRetriever(FakeRetriever):
        """Like the real adapter's fallback: also returns other services' passages."""

        def search(self, query: str, service_id: str | None, k: int) -> list[Passage]:
            self.searches.append((query, service_id, k))
            return sorted(self.passages, key=lambda p: p.score, reverse=True)[:k]

    d = dataclasses.replace(
        deps([]),
        retriever=MixingRetriever(
            [passage("o1", "old_age_allowance", 0.9), passage("w1", "widow_allowance", 0.8)]
        ),
    )
    state = {"question": "q", "service_id": "old_age_allowance",
             "service_ids": ["old_age_allowance", "widow_allowance"], "channel": Channel.APP}  # fmt: skip
    out = steps.retrieve(state, d)  # type: ignore[arg-type]
    assert [(p.chunk_id, p.service_id) for p in out["passages"]] == [
        ("o1", "old_age_allowance"), ("w1", "widow_allowance"),
    ]  # fmt: skip


def test_service_ids_are_ignored_when_the_primary_changed() -> None:
    d = deps([passage("w1", "widow_allowance", 0.9)])
    state = {"question": "q", "service_id": "widow_allowance", "service_ids": ["old_age_allowance"]}
    assert steps.active_services(state, d) == ["widow_allowance"]  # type: ignore[arg-type]
