"""The real e5 model (skipped when it has not been downloaded to data/models/e5)."""

import pytest

from app.application.ports.retrieval import Embedder
from app.config import Settings
from app.infrastructure.retrieval.e5_embedder import E5Embedder

SETTINGS = Settings(_env_file=None)
MODEL_DIR = SETTINGS.embed_cache_dir / "models--intfloat--multilingual-e5-small"

pytestmark = pytest.mark.skipif(not MODEL_DIR.exists(), reason="e5 model not downloaded")


@pytest.fixture(scope="module")
def embedder() -> E5Embedder:
    return E5Embedder(SETTINGS.embed_model, SETTINGS.embed_cache_dir)


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fits_the_port_and_gives_normalised_384_number_vectors(embedder: E5Embedder) -> None:
    assert isinstance(embedder, Embedder)
    v = embedder.embed_query("বয়স্ক ভাতা")
    assert len(v) == 384
    assert dot(v, v) == pytest.approx(1.0, abs=1e-4)
    assert embedder.embed_passages([]) == []


def test_a_bangla_question_is_closest_to_the_matching_passage(embedder: E5Embedder) -> None:
    passages = [
        "বয়স্ক ভাতা: পুরুষের বয়স সর্বনিম্ন ৬৫ বছর এবং মহিলাদের ৬২ বছর হতে হবে।",
        "ই-পাসপোর্ট ফি: ৪৮ পৃষ্ঠা ৫ বছর মেয়াদ নিয়মিত বিতরণ ৪,০২৫ টাকা।",
        "ট্রেড লাইসেন্স নবায়নের জন্য পূর্ববর্তী ইউজার থেকে আবেদন করতে হয়।",
    ]
    vectors = embedder.embed_passages(passages)
    for question, best in [("বয়স্ক ভাতা পেতে বয়স কত লাগে", 0), ("পাসপোর্ট করতে কত টাকা", 1)]:
        q = embedder.embed_query(question)
        scores = [dot(q, v) for v in vectors]
        assert scores.index(max(scores)) == best, (question, scores)


def test_token_count_includes_the_prefix(embedder: E5Embedder) -> None:
    assert embedder.token_count("ভাতা") > embedder.token_count("ভাতা", prefix="")
    assert embedder.max_tokens == 512
