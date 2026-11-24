"""Use cases: group logged questions into topics for the officer dashboard (D2-T2, FR-ADM-03, 04).

RebuildClusters: embed every logged question -> K-Means -> a short Bangla label per cluster (one
FAST LLM call for all clusters; top keywords if the LLM is unavailable) -> store the clusters and
each question's cluster id. ListClusters: the stored clusters, biggest first.
"""

import logging
import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.application.ports.clustering import Cluster, Clusterer
from app.application.ports.llm import LLM, ModelRole
from app.application.ports.repositories import ClusterRepo, QuestionLogRepo
from app.application.ports.retrieval import Embedder
from app.domain.errors import LLMUnavailable

log = logging.getLogger(__name__)

EXAMPLES_PER_CLUSTER = 3
QUESTIONS_SHOWN_TO_LLM = 6
KEYWORDS_IN_LABEL = 3

LABEL_PROMPT = """These are groups of questions that citizens asked a Bangla helpline about Bangladesh
government services. Give each group a short Bangla label of 3 to 5 words that says what the
questions are about (for example "এনআইডি নামের বানান ভুল" or "বয়স্ক ভাতার বয়সসীমা").

{groups}

Return JSON: `labels` = one item per group with its `group` number and `label`."""

LABEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"group": {"type": "integer"}, "label": {"type": "string"}},
                "required": ["group", "label"],
            },
        }
    },
    "required": ["labels"],
}

# Words that say nothing about the topic (question words, pronouns, common verbs).
STOP_WORDS = frozenset(
    "কি কী কত কোথায় কিভাবে কীভাবে কেমনে কবে কেন কোন কোনো আমি আমার আমাকে আমাদের আপনি আপনার উনি তিনি "
    "তার এর ও আর এবং না নাই নেই হয় হবে হলে হয়েছে করতে করবো করব করে করা করার দিতে দিব দেব নিতে পাবো পাব পাওয়া "
    "যায় লাগে লাগবে জন্য থেকে এখন এই সেই একটা একটু কিছু সব ভাই দয়া করে বলুন জানতে চাই আছে "
    "ki koto kothay kivabe korbo korte lagbe pabo amar ami jonno ar na hobe".split()
)
_WORD = re.compile(r"[ঀ-৿a-zA-Z]+")


@dataclass(frozen=True)
class RebuildResult:
    clusters: int
    questions: int
    labelled_by: str  # "llm" | "keywords" | "none"


class RebuildClusters:
    def __init__(
        self,
        question_logs: QuestionLogRepo,
        embedder: Embedder,
        clusterer: Clusterer,
        clusters: ClusterRepo,
        llm: LLM | None = None,
    ) -> None:
        self._logs = question_logs
        self._embedder = embedder
        self._clusterer = clusterer
        self._clusters = clusters
        self._llm = llm

    def execute(self) -> RebuildResult:
        rows = self._logs.texts_for_clustering()
        if not rows:
            self._clusters.replace_all([])
            return RebuildResult(clusters=0, questions=0, labelled_by="none")

        texts = [text for _, text in rows]
        vectors = [self._embedder.embed_query(text) for text in texts]
        numbers = self._clusterer.cluster(vectors)

        groups: dict[int, list[int]] = {}
        for i, number in enumerate(numbers):
            groups.setdefault(number, []).append(i)
        ordered = sorted(groups.values(), key=len, reverse=True)  # biggest topic first
        examples = [central_examples([texts[i] for i in g], [vectors[i] for i in g]) for g in ordered]

        labels, labelled_by = self._llm_labels(examples, [[texts[i] for i in g] for g in ordered])
        if labels is None:
            labels, labelled_by = keyword_labels([[texts[i] for i in g] for g in ordered]), "keywords"

        stored = [
            Cluster(label=label, size=len(g), examples=tuple(ex))
            for label, g, ex in zip(labels, ordered, examples, strict=True)
        ]
        ids = self._clusters.replace_all(stored)
        self._logs.set_cluster_ids(
            {rows[i][0]: cluster_id for cluster_id, g in zip(ids, ordered, strict=True) for i in g}
        )
        log.info(
            "clusters rebuilt: %d clusters from %d questions (labels: %s)", len(ids), len(rows), labelled_by
        )
        return RebuildResult(clusters=len(ids), questions=len(rows), labelled_by=labelled_by)

    def _llm_labels(
        self, examples: Sequence[Sequence[str]], groups: Sequence[Sequence[str]]
    ) -> tuple[list[str] | None, str]:
        if self._llm is None:
            return None, "keywords"
        blocks = []
        for i, (central, all_texts) in enumerate(zip(examples, groups, strict=True)):
            shown = list(dict.fromkeys([*central, *all_texts]))[:QUESTIONS_SHOWN_TO_LLM]
            blocks.append(f"Group {i}:\n" + "\n".join(f"- {t}" for t in shown))
        try:
            data = self._llm.generate_json(
                LABEL_PROMPT.format(groups="\n\n".join(blocks)),
                LABEL_SCHEMA,
                role=ModelRole.FAST,
                temperature=0.2,
            )
        except LLMUnavailable:
            log.warning("cluster labels: LLM unavailable, using keywords")
            return None, "keywords"
        by_group = {
            item.get("group"): str(item.get("label", "")).strip()
            for item in data.get("labels") or []
            if isinstance(item, dict)
        }
        labels = [by_group.get(i) or "" for i in range(len(groups))]
        if not all(labels):  # a missing label is filled with keywords for that group only
            fallback = keyword_labels(groups)
            labels = [label or fallback[i] for i, label in enumerate(labels)]
        return labels, "llm"


class ListClusters:
    def __init__(self, clusters: ClusterRepo) -> None:
        self._clusters = clusters

    def execute(self) -> list[Cluster]:
        return sorted(self._clusters.list_all(), key=lambda c: c.size, reverse=True)


# ---------------------------------------------------------------- pure helpers


def central_examples(texts: Sequence[str], vectors: Sequence[Sequence[float]]) -> list[str]:
    """The questions closest to the cluster centre (most typical), without repeats."""
    dims = len(vectors[0])
    centre = [sum(v[d] for v in vectors) / len(vectors) for d in range(dims)]
    norm = math.sqrt(sum(c * c for c in centre)) or 1.0
    scores = [sum(a * b for a, b in zip(v, centre, strict=True)) / norm for v in vectors]
    ranked = [texts[i] for i in sorted(range(len(texts)), key=lambda i: scores[i], reverse=True)]
    return list(dict.fromkeys(" ".join(t.split()) for t in ranked))[:EXAMPLES_PER_CLUSTER]


def keyword_labels(groups: Sequence[Sequence[str]]) -> list[str]:
    """Top words of each group that are rare in the other groups (a small TF-IDF), joined by " · "."""
    counts = [Counter(w for t in g for w in _words(t)) for g in groups]
    document_freq = Counter(w for c in counts for w in c)
    labels = []
    for c in counts:
        scored = sorted(c, key=lambda w: (-c[w] * math.log((len(groups) + 1) / document_freq[w]), w))
        labels.append(" · ".join(scored[:KEYWORDS_IN_LABEL]) or "অন্যান্য")
    return labels


def _words(text: str) -> list[str]:
    return [w for w in (m.lower() for m in _WORD.findall(text)) if len(w) > 1 and w not in STOP_WORDS]
