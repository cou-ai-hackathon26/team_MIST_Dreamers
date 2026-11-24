"""Question clusters for the dashboard (D2-T2, FR-ADM-03, 04). Fakes only, no network."""

from typing import Any

from app.application.ports.clustering import Cluster
from app.application.use_cases.clusters import (
    ListClusters,
    RebuildClusters,
    central_examples,
    keyword_labels,
)
from app.domain.entities import QuestionLog
from app.domain.value_objects import AnswerStatus, Channel
from tests.fakes import FakeEmbedder, FakeLLM, InMemoryClusterRepo, InMemoryQuestionLogRepo

QUESTIONS = [
    "এনআইডি কার্ডে নামের বানান ভুল",  # 0 -> group 0
    "বয়স্ক ভাতা কত টাকা",  # 1 -> group 1
    "পাসপোর্ট ফি কত",  # 2 -> group 2
    "এনআইডি নামের বানান সংশোধন",  # 3 -> group 0
    "বয়স্ক ভাতার বয়স কত",  # 4 -> group 1
    "এনআইডি বানান ভুল ঠিক করবো কিভাবে",  # 5 -> group 0
]


class ByIndexClusterer:
    """Puts question i into group GROUPS[i], so the test controls the clusters."""

    GROUPS = [0, 1, 2, 0, 1, 0]

    def cluster(self, vectors: Any) -> list[int]:
        return self.GROUPS[: len(vectors)]


def logs_with(questions: list[str]) -> InMemoryQuestionLogRepo:
    repo = InMemoryQuestionLogRepo()
    for q in questions:
        repo.add(QuestionLog(phone_hash="h", channel=Channel.APP, text=q, status=AnswerStatus.ANSWERED))
    return repo


def rebuild(llm: FakeLLM | None) -> tuple[Any, InMemoryQuestionLogRepo, InMemoryClusterRepo]:
    logs, clusters = logs_with(QUESTIONS), InMemoryClusterRepo()
    result = RebuildClusters(logs, FakeEmbedder(), ByIndexClusterer(), clusters, llm).execute()
    return result, logs, clusters


def test_rebuild_stores_clusters_biggest_first_with_llm_labels() -> None:
    labels = [
        {"group": 0, "label": "এনআইডি নামের বানান"},
        {"group": 1, "label": "বয়স্ক ভাতা"},
        {"group": 2, "label": "পাসপোর্ট ফি"},
    ]
    llm = FakeLLM([{"labels": labels}])
    result, logs, clusters = rebuild(llm)
    assert (result.clusters, result.questions, result.labelled_by) == (3, 6, "llm")
    stored = clusters.list_all()
    assert [(c.label, c.size) for c in stored] == [("এনআইডি নামের বানান", 3), ("বয়স্ক ভাতা", 2), ("পাসপোর্ট ফি", 1)]
    assert all(1 <= len(c.examples) <= 3 for c in stored)
    assert set(stored[0].examples) <= {QUESTIONS[0], QUESTIONS[3], QUESTIONS[5]}
    # every logged question now points at its cluster
    nid_id = stored[0].id
    assert [logs.logs[i].cluster_id for i in (1, 4, 6)] == [nid_id] * 3
    assert len(llm.prompts) == 1 and "Group 2:" in llm.prompts[0]  # one call for all clusters


def test_labels_fall_back_to_keywords_without_the_llm() -> None:
    result, _, clusters = rebuild(FakeLLM(fail=True))
    assert result.labelled_by == "keywords"
    nid_label = clusters.list_all()[0].label
    assert "এনআইডি" in nid_label or "বানান" in nid_label
    assert "কিভাবে" not in nid_label  # question words are ignored


def test_a_missing_llm_label_is_filled_with_keywords() -> None:
    llm = FakeLLM([{"labels": [{"group": 0, "label": "এনআইডি নামের বানান"}]}])
    _, _, clusters = rebuild(llm)
    labels = [c.label for c in clusters.list_all()]
    assert labels[0] == "এনআইডি নামের বানান" and all(labels)


def test_no_questions_clears_the_clusters() -> None:
    clusters = InMemoryClusterRepo()
    clusters.replace_all([Cluster(label="old", size=1, examples=("x",))])
    result = RebuildClusters(
        InMemoryQuestionLogRepo(), FakeEmbedder(), ByIndexClusterer(), clusters
    ).execute()
    assert result.clusters == 0 and clusters.list_all() == []


def test_list_clusters_biggest_first() -> None:
    repo = InMemoryClusterRepo()
    repo.replace_all([Cluster("ছোট", 1, ("a",)), Cluster("বড়", 5, ("b",))])
    assert [c.label for c in ListClusters(repo).execute()] == ["বড়", "ছোট"]


def test_central_examples_prefer_typical_questions_and_skip_repeats() -> None:
    texts = ["far", "near a", "near  a", "near b"]
    vectors = [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.9, 0.1]]
    assert central_examples(texts, vectors) == ["near a", "near b", "far"]


def test_keyword_labels_pick_words_specific_to_each_group() -> None:
    labels = keyword_labels([["ট্রেড লাইসেন্স ফি কত", "ট্রেড লাইসেন্স নবায়ন"], ["পাসপোর্ট ফি কত"]])
    assert labels[0].startswith("ট্রেড") or labels[0].startswith("লাইসেন্স")
    assert "পাসপোর্ট" in labels[1]
