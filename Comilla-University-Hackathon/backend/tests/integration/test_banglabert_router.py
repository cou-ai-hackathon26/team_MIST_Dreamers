"""BanglaBERT router (D2-T1, FR-AGT-02, NFR-PERF-03) and how the container picks the router."""

import time
from pathlib import Path

import pytest

from app.application.ports.classifier import ServiceClassifier
from app.config import BACKEND_DIR, Settings
from app.container import NOT_CONFIGURED, Container
from app.domain.errors import ClassifierUnavailable
from app.domain.value_objects import RouterSource
from app.infrastructure.ml.banglabert_classifier import BanglaBertClassifier
from app.infrastructure.ml.llm_classifier import LLMClassifier
from app.infrastructure.ml.tfidf_classifier import TfidfClassifier

MODEL_DIR = BACKEND_DIR / "data" / "models" / "router"
NOWHERE = Path(__file__).parent / "no_such_model"
needs_model = pytest.mark.skipif(
    not (MODEL_DIR / "labels.json").exists(), reason="BanglaBERT router not trained on this laptop"
)


def container_for(router: str, model_dir: Path = NOWHERE, tfidf: Path = NOWHERE / "r.joblib") -> Container:
    return Container(
        Settings(
            _env_file=None, database_url="sqlite://", router_backend=router,  # type: ignore[arg-type]
            router_model_dir=model_dir, tfidf_model_path=tfidf,
        )
    )  # fmt: skip


def test_missing_model_folder_raises_a_domain_error() -> None:
    clf = BanglaBertClassifier(NOWHERE)
    assert isinstance(clf, ServiceClassifier) and clf.source is RouterSource.BANGLABERT
    assert not clf.available
    with pytest.raises(ClassifierUnavailable):
        clf.classify("যেকোনো প্রশ্ন")


def test_banglabert_without_a_model_falls_back_to_tfidf(tmp_path: Path) -> None:
    tfidf_file = tmp_path / "tfidf.joblib"
    tfidf_file.write_bytes(b"x")  # only its existence matters for /health
    c = container_for("banglabert", tfidf=tfidf_file)
    assert isinstance(c.classifier, TfidfClassifier)
    assert c.check_router() == "tfidf"
    assert container_for("banglabert").check_router() == NOT_CONFIGURED  # nothing trained at all


def test_llm_router_is_selectable() -> None:
    c = container_for("llm")
    assert isinstance(c.classifier, LLMClassifier)
    assert c.check_router() == NOT_CONFIGURED  # Gemini without keys


@needs_model
def test_container_uses_banglabert_when_the_model_exists() -> None:
    c = container_for("banglabert", model_dir=MODEL_DIR)
    assert isinstance(c.classifier, BanglaBertClassifier)
    assert c.check_router() == "banglabert"
    assert "_loaded" in c.classifier.__dict__ and c.classifier._loaded is None  # health loads nothing


@needs_model
def test_trained_router_is_fast_sorted_and_routes_banglish() -> None:
    clf = BanglaBertClassifier(MODEL_DIR)
    clf.classify("warm up")  # loading is not counted
    started = time.perf_counter()
    scores = clf.classify("NID-te namer banan bhul, ki korbo?")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert scores[0][0] == "nid_correction"
    assert len(scores) == 9 and sum(p for _, p in scores) == pytest.approx(1.0, abs=1e-4)
    assert [p for _, p in scores] == sorted((p for _, p in scores), reverse=True)
    assert elapsed_ms < 200, f"router took {elapsed_ms:.0f} ms (NFR-PERF-03: at most 200 ms)"
