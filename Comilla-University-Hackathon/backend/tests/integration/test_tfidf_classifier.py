"""TF-IDF router adapter (D1-R4, FR-AGT-01, FR-AGT-02): fits the port, sorted scores, clear errors."""

from pathlib import Path

import joblib
import pytest

from app.application.ports.classifier import ServiceClassifier
from app.domain.errors import ClassifierUnavailable
from app.domain.value_objects import RouterSource
from app.infrastructure.ml.tfidf_classifier import TfidfClassifier
from scripts.train_baseline import build_pipeline

TEXTS = [
    ("বয়স্ক ভাতা কত টাকা", "old_age_allowance"),
    ("বয়স্ক ভাতার বয়স কত লাগে", "old_age_allowance"),
    ("boyosko vata kivabe pabo", "old_age_allowance"),
    ("পাসপোর্ট করতে কী লাগে", "e_passport"),
    ("ই পাসপোর্ট ফি কত", "e_passport"),
    ("passport korte koto din lage", "e_passport"),
    ("আজকের আবহাওয়া কেমন", "other"),
    ("ক্রিকেট খেলা কবে", "other"),
    ("ajke brishti hobe", "other"),
]


@pytest.fixture
def model_file(tmp_path: Path) -> Path:
    pipeline = build_pipeline()
    pipeline.fit([t for t, _ in TEXTS], [label for _, label in TEXTS])
    path = tmp_path / "router.joblib"
    joblib.dump({"pipeline": pipeline, "labels": list(pipeline.classes_)}, path)
    return path


def test_fits_the_port_and_returns_sorted_probabilities(model_file: Path) -> None:
    clf = TfidfClassifier(model_file)
    assert isinstance(clf, ServiceClassifier)
    assert clf.source is RouterSource.TFIDF and clf.available
    scores = clf.classify("ই-পাসপোর্ট করতে কত টাকা ফি লাগে?")
    assert scores[0][0] == "e_passport"
    assert {label for label, _ in scores} == {"old_age_allowance", "e_passport", "other"}
    assert [p for _, p in scores] == sorted((p for _, p in scores), reverse=True)
    assert sum(p for _, p in scores) == pytest.approx(1.0)


def test_missing_model_raises_a_domain_error(tmp_path: Path) -> None:
    clf = TfidfClassifier(tmp_path / "missing.joblib")
    assert not clf.available
    with pytest.raises(ClassifierUnavailable):
        clf.classify("যেকোনো প্রশ্ন")


def test_broken_model_file_raises_a_domain_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.joblib"
    path.write_bytes(b"not a joblib file")
    with pytest.raises(ClassifierUnavailable):
        TfidfClassifier(path).classify("যেকোনো প্রশ্ন")
