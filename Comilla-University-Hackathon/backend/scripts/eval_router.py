"""Router evaluation: TF-IDF vs BanglaBERT on the hand-written test set (D2-T1, FR-DATA-08).

Run from backend/ (PowerShell: first `$env:PYTHONIOENCODING = "utf-8"`):
    python -m scripts.eval_router            # also measures the LLM second opinion (uses Gemini quota)
    python -m scripts.eval_router --no-llm   # local routers only

For each router: accuracy, macro-F1, per-label F1, confusion matrix, inference time, how many
questions fall below ROUTER_CONFIDENCE_THRESHOLD, and how many out-of-scope questions become
`other`. With the LLM: the accuracy after the agent's `llm_classify` step re-decides the unsure
questions (FR-AGT-03), exactly as in the live agent. Writes docs/results/router_eval.md.
"""

import argparse
import csv
import dataclasses
import logging
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from app.application.agent import steps
from app.application.ports.classifier import ServiceClassifier
from app.config import BACKEND_DIR, Settings
from app.container import Container
from app.domain.errors import LLMUnavailable

QUESTIONS = BACKEND_DIR / "data" / "questions"
REPORT = BACKEND_DIR.parent / "docs" / "results" / "router_eval.md"
SHORT = {
    "old_age_allowance": "old", "widow_allowance": "widow", "disability_allowance": "disab",
    "birth_registration": "birth", "nid_correction": "nid", "e_passport": "pass",
    "land_mutation": "land", "trade_licence": "trade", "other": "other",
}  # fmt: skip
LABELS = list(SHORT)


@dataclasses.dataclass
class Result:
    name: str
    predicted: list[str]
    confidence: list[float]
    ms: list[float]
    oos_other: float
    after_llm: list[str] | None = None
    llm_calls: int = 0
    llm_failures: int = 0


def read(path: Path, column: str) -> list[str]:
    with path.open(encoding="utf-8", newline="") as f:
        return [row[column] for row in csv.DictReader(f)]


def run_router(name: str, clf: ServiceClassifier, texts: list[str], oos: list[str]) -> Result:
    clf.classify("warm up")  # model loading is not part of the timing
    predicted, confidence, ms = [], [], []
    for text in texts:
        started = time.perf_counter()
        top_label, top_score = clf.classify(text)[0]
        ms.append((time.perf_counter() - started) * 1000)
        predicted.append(top_label)
        confidence.append(top_score)
    oos_other = sum(clf.classify(t)[0][0] == "other" for t in oos) / len(oos)
    return Result(name, predicted, confidence, ms, oos_other)


def add_llm_second_opinion(
    result: Result, clf: ServiceClassifier, texts: list[str], deps: steps.AgentDeps
) -> None:
    """Questions below the threshold are re-decided by the agent's own llm_classify step."""
    final = list(result.predicted)
    for i, text in enumerate(texts):
        if result.confidence[i] >= deps.confidence_threshold:
            continue
        state = {"question": text, "history": [], "candidates": clf.classify(text)[:3]}
        try:
            final[i] = steps.llm_classify(state, deps)["service_id"]  # type: ignore[arg-type]
            result.llm_calls += 1
        except LLMUnavailable:
            result.llm_failures += 1  # keep the router's answer
    result.after_llm = final


def matrix_table(gold: list[str], predicted: list[str]) -> str:
    cm = confusion_matrix(gold, predicted, labels=LABELS)
    head = "| true \\ predicted | " + " | ".join(SHORT[label] for label in LABELS) + " |"
    sep = "|---" * (len(LABELS) + 1) + "|"
    rows = [
        f"| {SHORT[label]} | " + " | ".join(f"**{n}**" if i == j else (str(n) if n else "·")
                                            for j, n in enumerate(cm[i])) + " |"
        for i, label in enumerate(LABELS)
    ]  # fmt: skip
    return "\n".join([head, sep, *rows])


def error_section(r: Result, gold: list[str], texts: list[str]) -> list[str]:
    """Which questions the router gets wrong, how sure it was, and what other thresholds would do."""
    wrong = sorted(
        (
            (r.confidence[i], gold[i], r.predicted[i], texts[i])
            for i in range(len(gold))
            if gold[i] != r.predicted[i]
        ),
        reverse=True,
    )
    lines = [
        "",
        f"## Wrong answers: {r.name}",
        "",
        "| Confidence | True | Predicted | Question |",
        "|---|---|---|---|",
    ]
    lines += [f"| {c:.2f} | `{g}` | `{p}` | {t} |" for c, g, p, t in wrong]
    lines += [
        "",
        f"## Threshold check: {r.name}",
        "",
        "| Threshold | Questions sent to the LLM | Wrong answers sent to the LLM |",
        "|---|---|---|",
    ]
    for th in (0.6, 0.7, 0.8, 0.85, 0.9):
        sent = sum(c < th for c in r.confidence) / len(gold)
        caught = sum(c < th for c, *_ in wrong)
        lines.append(f"| {th} | {sent:.0%} | {caught} of {len(wrong)} |")
    return lines


def write_report(
    results: list[Result], gold: list[str], texts: list[str], n_oos: int, threshold: float
) -> None:
    lines = [
        "# Router evaluation (FR-DATA-08)",
        "",
        f"Generated by `python -m scripts.eval_router` on {date.today():%d %b %Y}. "
        f"Test set: `backend/data/questions/test.csv`, {len(gold)} hand-written questions (12 per label, "
        f"never used for training or augmentation). Out-of-scope set: `out_of_scope.csv`, {n_oos} questions. "
        f"`ROUTER_CONFIDENCE_THRESHOLD` = {threshold}.",
        "",
        "## Summary",
        "",
        "| Router | Accuracy | Macro-F1 | After LLM second opinion | LLM calls | Below threshold "
        "| Out-of-scope -> `other` | Inference (mean / p95) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        acc = accuracy_score(gold, r.predicted)
        f1 = f1_score(gold, r.predicted, average="macro", labels=LABELS, zero_division=0)
        below = sum(c < threshold for c in r.confidence) / len(gold)
        p95 = sorted(r.ms)[int(0.95 * (len(r.ms) - 1))]
        after = f"{accuracy_score(gold, r.after_llm):.1%}" if r.after_llm else "not measured"
        calls = f"{r.llm_calls}" + (f" ({r.llm_failures} failed)" if r.llm_failures else "")
        lines.append(
            f"| {r.name} | {acc:.1%} | {f1:.1%} | {after} | {calls if r.after_llm else '-'} | {below:.0%} "
            f"| {r.oos_other:.0%} | {statistics.mean(r.ms):.0f} / {p95:.0f} ms |"
        )
    lines += ["", "## F1 per label", "", "| Label | " + " | ".join(r.name for r in results) + " |",
              "|---" * (len(results) + 1) + "|"]  # fmt: skip
    per_label = [f1_score(gold, r.predicted, average=None, labels=LABELS, zero_division=0) for r in results]
    for i, label in enumerate(LABELS):
        lines.append(f"| `{label}` | " + " | ".join(f"{scores[i]:.2f}" for scores in per_label) + " |")
    for r in results:
        lines += ["", f"## Confusion matrix: {r.name}", "", matrix_table(gold, r.predicted)]
    best = max(results, key=lambda r: f1_score(gold, r.predicted, average="macro", labels=LABELS))
    lines += error_section(best, gold, texts)
    lines += [
        "",
        "## Notes",
        "",
        f"- Best local router on this test set: **{best.name}**; the app uses it with `ROUTER_BACKEND`.",
        "- Questions below the threshold go to the LLM with the router's top 3 labels as hints (FR-AGT-03), "
        'so the agent\'s final routing is the "after LLM" column.',
        "- A confident wrong route is not the end of the story: the agent then grades the passages and "
        "verifies every claim (FR-AGT-06, 10), so a question the documents of that service do not cover "
        "ends in the fixed fallback text instead of a wrong answer.",
        "- Inference is measured on this laptop's CPU, one question at a time, after the model was loaded "
        "(target at most 200 ms, NFR-PERF-03).",
        "- The SRS target is at least 90% accuracy (SRS 11).",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="skip the LLM second opinion")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings()
    container = Container(settings)
    texts, gold = read(QUESTIONS / "test.csv", "text"), read(QUESTIONS / "test.csv", "label")
    oos = read(QUESTIONS / "out_of_scope.csv", "text")
    routers: list[tuple[str, ServiceClassifier]] = [("TF-IDF", container.tfidf_classifier)]
    if container.banglabert_classifier.available:
        routers.append(("BanglaBERT", container.banglabert_classifier))
    else:
        print("BanglaBERT model not found (backend/data/models/router): evaluating TF-IDF only")

    deps = dataclasses.replace(
        container.agent_deps, confidence_threshold=settings.router_confidence_threshold
    )
    results = []
    for name, clf in routers:
        print(f"{name}: routing {len(texts)} test questions ...")
        result = run_router(name, clf, texts, oos)
        if not args.no_llm:
            add_llm_second_opinion(result, clf, texts, deps)
        results.append(result)
        acc = accuracy_score(gold, result.predicted)
        after = f", after LLM {accuracy_score(gold, result.after_llm):.1%}" if result.after_llm else ""
        print(f"  accuracy {acc:.1%}{after}, mean {statistics.mean(result.ms):.0f} ms per question")

    write_report(results, gold, texts, len(oos), settings.router_confidence_threshold)
    container.close()
    print(f"wrote {REPORT.relative_to(BACKEND_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
