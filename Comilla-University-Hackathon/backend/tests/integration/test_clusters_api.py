"""K-Means adapter and the cluster API (D2-T2, FR-ADM-03, 04, 05)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application.ports.clustering import Clusterer
from app.config import Settings
from app.domain.entities import QuestionLog
from app.domain.value_objects import AnswerStatus, Channel
from app.infrastructure.ml.kmeans_clusterer import KMeansClusterer
from app.main import create_app
from tests.fakes import FakeEmbedder, FakeLLM

NO_DIR = Path(__file__).parent / "no_such_dir"


# ---------------------------------------------------------------- K-Means


def blobs(per_blob: int) -> list[list[float]]:
    """Three clearly separated groups of 2-D points."""
    centres = [(0.0, 0.0), (10.0, 10.0), (-10.0, 10.0)]
    return [[cx + 0.1 * (i % 3), cy + 0.1 * (i // 3)] for cx, cy in centres for i in range(per_blob)]


def test_few_questions_use_a_fixed_k() -> None:
    clf = KMeansClusterer()
    assert isinstance(clf, Clusterer)
    labels = clf.cluster(blobs(4))  # 12 points < 30
    assert clf.chosen_k == 3 and len(set(labels)) == 3
    assert labels[0:4] == [labels[0]] * 4  # one group stays together


def test_enough_questions_choose_k_by_silhouette() -> None:
    clf = KMeansClusterer()
    labels = clf.cluster(blobs(15))  # 45 points
    assert set(clf.scores) == set(range(3, 9))
    assert clf.chosen_k == 3 and len(set(labels)) == 3


def test_edge_cases() -> None:
    clf = KMeansClusterer()
    assert clf.cluster([]) == []
    assert clf.cluster([[1.0, 1.0]] * 5) == [0] * 5  # identical questions: one group
    assert len(set(clf.cluster([[0.0, 0.0], [5.0, 5.0]]))) == 2  # fewer points than k


# ---------------------------------------------------------------- API


def app_client(admin_token: str = "") -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        chroma_dir=NO_DIR,
        admin_token=admin_token,  # type: ignore[arg-type]
    )
    with TestClient(create_app(settings)) as client:
        container = client.app.state.container  # type: ignore[attr-defined]
        container.__dict__.update(embedder=FakeEmbedder(), llm=FakeLLM(fail=True))  # no model, no network
        for text in ["এনআইডি নামের বানান ভুল", "বয়স্ক ভাতা কত টাকা", "পাসপোর্ট ফি কত", "ট্রেড লাইসেন্স ফি"]:
            container.question_logs.add(
                QuestionLog(phone_hash="h", channel=Channel.APP, text=text, status=AnswerStatus.ANSWERED)
            )
        yield client


@pytest.fixture
def client() -> Iterator[TestClient]:
    for c in app_client(admin_token="test-admin-password"):  # admin is closed without a password
        c.headers["X-Admin-Token"] = "test-admin-password"
        yield c


def test_rebuild_then_list(client: TestClient) -> None:
    assert client.get("/api/v1/admin/clusters").json() == {"clusters": []}
    r = client.post("/api/v1/admin/clusters/rebuild")
    assert r.status_code == 200
    assert r.json() == {"clusters": 3, "questions": 4, "labelled_by": "keywords"}
    clusters = client.get("/api/v1/admin/clusters").json()["clusters"]
    assert len(clusters) == 3 and sum(c["size"] for c in clusters) == 4
    assert clusters[0]["size"] >= clusters[-1]["size"]
    assert all(set(c) == {"id", "label", "size", "examples"} and c["label"] for c in clusters)


def test_admin_token_is_required_when_set() -> None:
    gen = app_client(admin_token="s3cret")
    client = next(gen)
    try:
        r = client.get("/api/v1/admin/clusters")
        assert r.status_code == 401 and r.json()["error"]["code"] == "HTTP_ERROR"
        assert (
            client.post("/api/v1/admin/clusters/rebuild", headers={"X-Admin-Token": "wrong"}).status_code
            == 401
        )
        assert client.get("/api/v1/admin/clusters", headers={"X-Admin-Token": "s3cret"}).status_code == 200
    finally:
        gen.close()
