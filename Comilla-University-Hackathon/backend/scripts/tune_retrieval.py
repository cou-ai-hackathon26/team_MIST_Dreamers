"""Measures search quality and helps choose RETRIEVAL_MIN_SCORE (Sync 1 task).

Run from backend/ after `python -m scripts.ingest`:
    python -m scripts.tune_retrieval

Uses data/questions/test.csv (in-scope questions with their correct service) and
data/questions/out_of_scope.csv plus the test questions labelled "other" (should NOT match).
Prints, without changing anything:
- Recall@5: is a passage of the correct service in the top 5 when searching ALL services?
- the best score of in-scope questions (searching their own service) vs off-topic questions,
- a suggested threshold between the two groups.
"""

import csv
import statistics
import sys
from collections import defaultdict

from app.config import BACKEND_DIR, get_settings
from app.container import Container
from app.domain import policies
from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever

QUESTIONS = BACKEND_DIR / "data" / "questions"


def read(name: str) -> list[dict[str, str]]:
    with (QUESTIONS / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


def main() -> int:
    settings = get_settings()
    container = Container(settings)
    # min_filtered=0: never merge, so we see the raw scores of exactly what we asked for.
    retriever = ChromaRetriever(settings.chroma_dir, container.embedder, min_filtered=0)
    if retriever.count() == 0:
        print("The index is empty. Run: python -m scripts.ingest")
        return 1

    test = read("test.csv")
    in_scope = [r for r in test if r["label"] != "other"]
    off_topic = [r["text"] for r in read("out_of_scope.csv")]
    off_topic += [r["text"] for r in test if r["label"] == "other"]
    k = policies.TOP_K

    hits: dict[str, list[bool]] = defaultdict(list)
    own_scores: list[float] = []
    for row in in_scope:
        everywhere = retriever.search(row["text"], None, k)
        hits[row["label"]].append(any(p.service_id == row["label"] for p in everywhere))
        own = retriever.search(row["text"], row["label"], 1)
        own_scores.append(own[0].score if own else 0.0)
    off_scores = [(retriever.search(text, None, 1) or [None])[0] for text in off_topic]
    off_values = [p.score if p else 0.0 for p in off_scores]

    print(f"Recall@{k} (correct service in the top {k}, searching all services):")
    for label, found in sorted(hits.items()):
        print(f"  {label:22} {sum(found):>3}/{len(found):<3} {100 * sum(found) / len(found):5.1f}%")
    total = [h for found in hits.values() for h in found]
    print(f"  {'ALL':22} {sum(total):>3}/{len(total):<3} {100 * sum(total) / len(total):5.1f}%")

    print("\nBest score (in-scope questions searched in their own service, off-topic in all):")
    for name, values in (("in-scope", own_scores), ("off-topic", off_values)):
        print(
            f"  {name:10} n={len(values):<3} min={min(values):.3f}  p10={quantile(values, 0.1):.3f}  "
            f"median={statistics.median(values):.3f}  p90={quantile(values, 0.9):.3f}  max={max(values):.3f}"
        )

    low_in, high_off = quantile(own_scores, 0.1), quantile(off_values, 0.9)
    suggestion = round((low_in + high_off) / 2, 3)
    print(f"\nSuggested RETRIEVAL_MIN_SCORE ~ {suggestion} (middle of in-scope p10 and off-topic p90)")
    for threshold in sorted({settings.retrieval_min_score, suggestion}):
        kept = sum(s >= threshold for s in own_scores)
        leaked = sum(s >= threshold for s in off_values)
        print(
            f"  at {threshold:.3f}: in-scope kept {kept}/{len(own_scores)}, "
            f"off-topic above it {leaked}/{len(off_values)}"
        )
    print(f"\nCurrent setting: RETRIEVAL_MIN_SCORE = {settings.retrieval_min_score}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
