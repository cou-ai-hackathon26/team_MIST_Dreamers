"""ChromaRetriever on a real (temporary) Chroma store with a tiny word-based embedder.

The real e5 model is tested separately (test_e5_embedder.py); here we test our own logic:
storing, filtering by service, the score, the "too few good results -> search all" merge, rebuild.
"""

import hashlib
import math
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.application.ports.retrieval import Retriever
from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever
from app.infrastructure.retrieval.chunker import Chunk

DIM = 64


class WordEmbedder:
    """Bag of words hashed into 64 numbers: texts sharing words point the same way."""

    def _vector(self, text: str) -> list[float]:
        v = [0.0] * DIM
        for word in text.split():
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t.split("\n", 1)[1]) for t in texts]  # drop the title line


def chunk(chunk_id: str, service_id: str, text: str) -> Chunk:
    return Chunk(chunk_id, service_id, f"title {service_id}", f"https://x.gov.bd/{service_id}", "h", text)


CHUNKS = [
    chunk("old_age_allowance-001", "old_age_allowance", "বয়স ৬৫ বছর হলে বয়স্ক ভাতা"),
    chunk("old_age_allowance-002", "old_age_allowance", "ভাতা মোবাইলে পাঠানো হয়"),
    chunk("e_passport-001", "e_passport", "পাসপোর্ট ফি ৪০২৫ টাকা"),
    chunk("e_passport-002", "e_passport", "পাসপোর্ট অফিসে ছবি তোলা হয়"),
]


@pytest.fixture
def retriever(tmp_path: Path) -> ChromaRetriever:
    r = ChromaRetriever(tmp_path / "chroma", WordEmbedder(), min_score=0.5)
    r.rebuild(CHUNKS)
    return r


def test_fits_the_retriever_port(retriever: ChromaRetriever) -> None:
    assert isinstance(retriever, Retriever)


def test_rebuild_stores_every_chunk_and_replaces_old_ones(retriever: ChromaRetriever) -> None:
    assert retriever.count() == 4
    assert retriever.rebuild(CHUNKS[:1]) == 1  # re-running replaces, never appends
    assert retriever.count() == 1


def test_count_is_zero_before_any_ingest(tmp_path: Path) -> None:
    assert ChromaRetriever(tmp_path / "new", WordEmbedder()).count() == 0


def test_search_returns_best_first_with_metadata(retriever: ChromaRetriever) -> None:
    found = retriever.search("পাসপোর্ট ফি ৪০২৫ টাকা", None, k=2)
    assert found[0].chunk_id == "e_passport-001"
    assert found[0].score == pytest.approx(1.0)
    assert found[0].source_url == "https://x.gov.bd/e_passport"
    assert found[0].title == "title e_passport"
    assert found[0].score >= found[1].score


def test_filter_keeps_only_the_chosen_service_when_enough_results_are_good(tmp_path: Path) -> None:
    r = ChromaRetriever(tmp_path / "c", WordEmbedder(), min_score=0.1, min_filtered=1)
    r.rebuild(CHUNKS)
    found = r.search("বয়স্ক ভাতা", "old_age_allowance", k=5)
    assert {p.service_id for p in found} == {"old_age_allowance"}


def test_too_few_good_filtered_results_also_searches_all_services(retriever: ChromaRetriever) -> None:
    # The router guessed old age, but the question is about passports: the merge finds it anyway.
    found = retriever.search("পাসপোর্ট ফি ৪০২৫ টাকা", "old_age_allowance", k=3)
    assert found[0].chunk_id == "e_passport-001"
    assert len({p.chunk_id for p in found}) == len(found)  # merged without duplicates


def test_search_never_crashes_the_caller(tmp_path: Path) -> None:
    empty = ChromaRetriever(tmp_path / "nothing", WordEmbedder())
    assert empty.search("প্রশ্ন", None, k=3) == []  # no collection yet -> logged, empty answer
