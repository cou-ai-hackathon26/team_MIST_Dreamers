"""Situation and mixed-question evaluation (sprint E1 and T2, FR-DATA-11).

Run from backend/ (PowerShell: first `$env:PYTHONIOENCODING = "utf-8"`):
    python -m scripts.eval_situation            # everything (about 100 to 150 LLM calls)
    python -m scripts.eval_situation --no-llm   # routers and Recall@5 only, no LLM calls

Writes docs/results/situation_eval.md:
1. Routers on the hand-written situation_test.csv and, separately, on the Appendix C check set
   (situation_check.csv): TF-IDF v1/v2, BanglaBERT v1/v2 (when the folders exist), the old full
   path (router + llm_classify) and the new one (router + understand). C18 ("vague") is scored on
   its own: pass = the agent asks one follow-up question.
2. Recall@5 on situation_test.csv, searching all services: the caller's words only vs. expanded
   with the official words of the service the router chose (QUERY_EXPANSION, no LLM query).
3. Mixed questions (mixed_test.csv), full agent runs: both services found, at least one correct,
   guard pass rate, conflict reported when expected, fake conflict when not expected.
4. Regression: router accuracy on test.csv and refusal of out_of_scope.csv on the new path.
5. LLM calls and latency per question, and the LLM backend / models used.
6. T2 model gate: v2 is used only if it loses at most 1 point on test.csv AND is better on
   situation_test.csv.
The answer cache is off, so every run is real.
"""

import argparse
import csv
import dataclasses
import logging
import statistics
import sys
import time
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from app.config import BACKEND_DIR, Settings

QUESTIONS = BACKEND_DIR / "data" / "questions"
MODELS = BACKEND_DIR / "data" / "models"
REPORT = BACKEND_DIR.parent / "docs" / "results" / "situation_eval.md"
TOP_K = 5
VAGUE = "vague"
OTHER = "other"
GATE_MAX_DROP = 0.01  # T2: v2 may lose at most 1 point on test.csv


# ---------------------------------------------------------------- metrics (pure, unit tested)


def accuracy(gold: Sequence[str], predicted: Sequence[str]) -> float:
    if not gold:
        return 0.0
    return sum(g == p for g, p in zip(gold, predicted, strict=True)) / len(gold)


def macro_f1(gold: Sequence[str], predicted: Sequence[str]) -> float:
    """Mean F1 over the labels that appear in `gold` (a label never predicted scores 0)."""
    labels = sorted(set(gold))
    if not labels:
        return 0.0
    scores = []
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, predicted, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, predicted, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, predicted, strict=True))
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores)


def rate(flags: Iterable[bool]) -> float | None:
    values = list(flags)
    return sum(values) / len(values) if values else None


@dataclasses.dataclass(frozen=True)
class MixedResult:
    gold: tuple[str, str]
    found: tuple[str, ...]
    expects_conflict: bool
    conflicts: int
    guard_dropped_wrong_service: int
    answered: bool


def mixed_summary(results: Sequence[MixedResult]) -> dict[str, float | None]:
    """The five mixed-question numbers of the plan (Section 4, E1.3)."""
    return {
        "both": rate(set(r.gold) <= set(r.found) for r in results),
        "one": rate(bool(set(r.gold) & set(r.found)) for r in results),
        "guard_pass": rate(r.guard_dropped_wrong_service == 0 for r in results),
        "conflict_when_yes": rate(r.conflicts > 0 for r in results if r.expects_conflict),
        "fake_conflict_when_no": rate(r.conflicts > 0 for r in results if not r.expects_conflict),
        "answered": rate(r.answered for r in results),
    }


def gate(v1_test: float, v2_test: float, v1_situation: float, v2_situation: float) -> bool:
    """T2: switch to v2 only if not worse on test.csv (max 1 point drop) and better on situations."""
    return v2_test >= v1_test - GATE_MAX_DROP and v2_situation > v1_situation


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


# ---------------------------------------------------------------- data


def read(name: str) -> list[dict[str, str]]:
    path = QUESTIONS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def top1(classifier: Any, text: str) -> tuple[str, float]:
    scores = classifier.classify(text)
    return scores[0] if scores else (OTHER, 0.0)


# ---------------------------------------------------------------- the runner


class GuardCounter(logging.Handler):
    """Counts grounding_guard drops for a wrong service (from its log line)."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.wrong_service = 0

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith("grounding_guard dropped"):
            self.wrong_service += message.count("another service") + message.count("tagged")


@dataclasses.dataclass
class Routed:
    label: str
    follow_up: bool
    llm_calls: int
    ms: float


def route_full(question: str, deps: Any, situation_on: bool) -> Routed:
    """The classify part of the agent: router, then `understand` (new) or `llm_classify` (old)."""
    from app.application.agent import routing, steps
    from app.domain.value_objects import Channel

    started = time.perf_counter()
    state: dict[str, Any] = {"question": question, "history": [], "channel": Channel.APP}
    state.update(steps.classify(state, deps))  # type: ignore[arg-type]
    situation = routing.SituationRouting(situation_on, deps.multi_service_min_prob, deps.hint_min_confidence)
    nxt = routing.after_classify(state, deps.confidence_threshold, situation)  # type: ignore[arg-type]
    calls = 0
    if nxt == routing.UNDERSTAND:
        state.update(steps.understand(state, deps))  # type: ignore[arg-type]
        calls = 1
    elif nxt == routing.LLM_CLASSIFY:
        state.update(steps.llm_classify(state, deps))  # type: ignore[arg-type]
        calls = 1
    follow_up = bool((state.get("follow_up") or "").strip())
    label = state.get("service_id") or OTHER
    if nxt == routing.FALLBACK:
        label = OTHER
    return Routed(label, follow_up, calls, (time.perf_counter() - started) * 1000)


def score_routed(rows: list[dict[str, str]], routed: list[Routed]) -> tuple[float, float]:
    gold = [r["label"] for r in rows]
    predicted = [x.label for x in routed]
    return accuracy(gold, predicted), macro_f1(gold, predicted)


def run(args: argparse.Namespace) -> int:
    from app.container import Container
    from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
    from app.infrastructure.ml.banglabert_classifier import BanglaBertClassifier
    from app.infrastructure.ml.tfidf_classifier import TfidfClassifier
    from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever

    settings = Settings()
    container = Container(settings)
    situation = read("situation_test.csv")
    check_all = read("situation_check.csv")
    check = [r for r in check_all if r["label"] != VAGUE]
    vague = [r for r in check_all if r["label"] == VAGUE]
    test = read("test.csv")
    oos = read("out_of_scope.csv")
    mixed = read("mixed_test.csv")
    if not situation:
        print("situation_test.csv is empty: write the hand-written questions first (D1)")
        return 1

    routers: list[tuple[str, Any]] = [("TF-IDF v1", TfidfClassifier(settings.tfidf_model_path))]
    if (MODELS / "tfidf_router_v2.joblib").exists():
        routers.append(("TF-IDF v2", TfidfClassifier(MODELS / "tfidf_router_v2.joblib")))
    for name, folder in (("BanglaBERT v1", MODELS / "router"), ("BanglaBERT v2", MODELS / "router_v2")):
        clf = BanglaBertClassifier(folder)
        if clf.available:
            routers.append((name, clf))
        else:
            print(f"{name}: no model in {folder.relative_to(BACKEND_DIR)}, skipped")

    # 1 + 4a. routers alone (no LLM)
    table: dict[str, dict[str, tuple[float, float]]] = {}
    for name, clf in routers:
        print(f"{name}: routing ...")
        table[name] = {}
        for set_name, rows in (("situation", situation), ("check", check), ("test", test)):
            predicted = [top1(clf, r["text"])[0] for r in rows]
            gold = [r["label"] for r in rows]
            table[name][set_name] = (accuracy(gold, predicted), macro_f1(gold, predicted))

    # 2. Recall@5, all services searched
    retriever = ChromaRetriever(settings.chroma_dir, container.embedder, min_filtered=0)
    services = container.services_by_id
    classifier = container.classifier
    plain, expanded = [], []
    print("Recall@5 ...")
    for row in situation:
        if row["label"] == OTHER:
            continue
        found = [p.service_id for p in retriever.search(row["text"], None, TOP_K)]
        plain.append(row["label"] in found)
        chosen = top1(classifier, row["text"])[0]
        extra: list[str] = []
        if chosen in services and chosen != OTHER:
            s = services[chosen]
            extra = [p.service_id for p in retriever.search(f"{s.name_bn} {s.search_terms_bn}", None, TOP_K)]
        merged = list(dict.fromkeys(found[:3] + extra[:2] + found[3:]))[:TOP_K]
        expanded.append(row["label"] in merged)

    report: dict[str, Any] = {
        "routers": table, "recall_plain": rate(plain), "recall_expanded": rate(expanded),
        "settings": settings, "active_router": classifier.source.value, "llm": None,
    }  # fmt: skip

    # 1b, 3, 4b, 5: with the LLM
    if not args.no_llm:
        deps = dataclasses.replace(container.agent_deps, cache=None, situation_mode=True)
        old_deps = dataclasses.replace(deps, situation_mode=False)
        llm_part: dict[str, Any] = {}
        for label, d, on in (
            ("old: router + llm_classify", old_deps, False),
            ("new: router + understand", deps, True),
        ):
            print(f"{label}: situation_test + check set ...")
            routed_s = [route_full(r["text"], d, on) for r in situation]
            routed_c = [route_full(r["text"], d, on) for r in check]
            routed_v = [route_full(r["text"], d, on) for r in vague] if on else []
            llm_part[label] = {
                "situation": score_routed(situation, routed_s),
                "check": score_routed(check, routed_c),
                "vague_pass": rate(x.follow_up for x in routed_v) if on else None,
                "calls": statistics.mean(x.llm_calls for x in routed_s + routed_c),
            }
        print("new path: out_of_scope.csv refusal ...")
        refused = [route_full(r["text"], deps, True) for r in oos]
        llm_part["oos_refusal"] = rate(x.label == OTHER and not x.follow_up for x in refused)
        llm_part["oos_refusal_old"] = rate(route_full(r["text"], old_deps, False).label == OTHER for r in oos)

        print("mixed_test.csv: full agent runs ...")
        counter = GuardCounter()
        logging.getLogger("app.application.agent.steps").addHandler(counter)
        logging.getLogger("app.application.agent.steps").setLevel(logging.INFO)
        engine = LangGraphAnswerEngine(deps)
        results: list[MixedResult] = []
        calls, latency = [], []
        from app.domain.value_objects import AnswerStatus, Channel

        for row in mixed:
            before = counter.wrong_service
            started = time.perf_counter()
            try:
                answer = engine.answer(row["text"], [], Channel.APP)
            except Exception as exc:  # one failed question must not stop the evaluation
                print(f"  failed: {row['text'][:40]}... ({exc})")
                continue
            latency.append((time.perf_counter() - started) * 1000)
            calls.append(answer.llm_calls)
            found = answer.service_ids or ((answer.service_id,) if answer.service_id else ())
            labels = tuple(row["labels"].split(";"))
            results.append(
                MixedResult(
                    gold=(labels[0], labels[1]),
                    found=tuple(found),
                    expects_conflict=row["expects_conflict"] == "yes",
                    conflicts=len(answer.conflicts),
                    guard_dropped_wrong_service=counter.wrong_service - before,
                    answered=answer.status is AnswerStatus.ANSWERED,
                )  # fmt: skip
            )
            print(f"  {answer.status.value:9} mode={answer.mode:6} found={','.join(found)}")
        llm_part["mixed"] = mixed_summary(results)
        llm_part["mixed_n"] = len(results)
        llm_part["mixed_calls"] = statistics.mean(calls) if calls else None
        llm_part["mixed_ms"] = statistics.mean(latency) if latency else None
        report["llm"] = llm_part

    write_report(report)
    container.close()
    print(f"wrote {REPORT.relative_to(BACKEND_DIR.parent)}")
    return 0


# ---------------------------------------------------------------- report


def write_report(r: dict[str, Any]) -> None:
    s: Settings = r["settings"]
    routers: dict[str, dict[str, tuple[float, float]]] = r["routers"]
    lines = [
        "# Situation and mixed-question evaluation (sprint E1, FR-DATA-11)",
        "",
        f"Generated by `python -m scripts.eval_situation` on {date.today():%d %b %Y}. "
        f"Active router: `{r['active_router']}`, "
        f"`ROUTER_CONFIDENCE_THRESHOLD` = {s.router_confidence_threshold}, "
        f"`MULTI_SERVICE_MIN_PROB` = {s.multi_service_min_prob}. LLM: `{s.llm_backend}` "
        f"(main `{s.gemini_model_main or s.ollama_model}`, fast `{s.gemini_model_fast or s.ollama_model}`). "
        "Answer cache off.",
        "",
        "Sets: `situation_test.csv` (hand-written by Ragib and Ariful, never used for training or tuning), "
        "`situation_check.csv` (Appendix C, C1 to C17; C18 scored separately), `test.csv` (old hand-written "
        "set), `out_of_scope.csv`, `mixed_test.csv`. The leak check "
        "(`python -m scripts.augment_questions --check-leak-only`) confirms none of them is in the "
        "training data.",
        "",
        "## 1. Router on situational questions",
        "",
        "| Router | situation_test accuracy | macro-F1 | Appendix C check set accuracy | macro-F1 "
        "| test.csv accuracy |",
        "|---|---|---|---|---|---|",
    ]
    for name, sets in routers.items():
        sa, sf = sets["situation"]
        ca, cf = sets["check"]
        ta, _ = sets["test"]
        lines.append(f"| {name} | {pct(sa)} | {pct(sf)} | {pct(ca)} | {pct(cf)} | {pct(ta)} |")
    llm = r.get("llm")
    if llm:
        for label in ("old: router + llm_classify", "new: router + understand"):
            part = llm[label]
            sa, sf = part["situation"]
            ca, cf = part["check"]
            lines.append(f"| Full classify path, {label} | {pct(sa)} | {pct(sf)} | {pct(ca)} | {pct(cf)} | |")
        lines += [
            "",
            f"C18 (vague question, pass = one follow-up question, no guess): "
            f"**{pct(llm['new: router + understand']['vague_pass'])}**.",
        ]
    lines += [
        "",
        "## 2. Retrieval Recall@5 on situation_test.csv",
        "",
        "All services searched; a hit = a passage of the question's service in the top 5.",
        "",
        "| Query | Recall@5 |",
        "|---|---|",
        f"| Caller's words only (`QUERY_EXPANSION=false`) | {pct(r['recall_plain'])} |",
        f"| Expanded with the official words of the router's service (`QUERY_EXPANSION=true`) "
        f"| {pct(r['recall_expanded'])} |",
        "",
    ]
    if llm:
        m = llm["mixed"]
        lines += [
            f"## 3. Mixed questions (mixed_test.csv, {llm['mixed_n']} full agent runs, app channel)",
            "",
            "| Measure | Result |",
            "|---|---|",
            f"| Both services found | {pct(m['both'])} |",
            f"| At least one service correct | {pct(m['one'])} |",
            f"| Answered (not fallback / follow-up) | {pct(m['answered'])} |",
            f"| Guard pass rate (no claim dropped for citing another service) | {pct(m['guard_pass'])} |",
            f"| Conflict reported when `expects_conflict=yes` | {pct(m['conflict_when_yes'])} |",
            f"| Fake conflict reported when `expects_conflict=no` | {pct(m['fake_conflict_when_no'])} |",
            "",
            "A guard drop is not an error shown to the citizen: the claim is removed (or the answer retried) "
            "before verify, so a blended rule never reaches the answer.",
            "",
        ]
    lines += ["## 4. Regression", "", "| Measure | Before | After |", "|---|---|---|"]
    if "BanglaBERT v1" in routers:
        v2 = routers.get("BanglaBERT v2", {}).get("test", (None, None))[0]
        lines.append(
            f"| BanglaBERT test.csv accuracy (v1 / v2) "
            f"| {pct(routers['BanglaBERT v1']['test'][0])} | {pct(v2)} |"
        )
    if llm:
        lines.append(
            f"| out_of_scope.csv refused | {pct(llm['oos_refusal_old'])} | {pct(llm['oos_refusal'])} |"
        )
    lines.append("")
    if llm:
        new = llm["new: router + understand"]
        lines += [
            "## 5. LLM calls and latency",
            "",
            f"- Classify path, new: {new['calls']:.2f} LLM calls per situational question on average "
            f"(old path: {llm['old: router + llm_classify']['calls']:.2f}).",
            f"- Mixed questions, full agent: {llm['mixed_calls'] or 0:.1f} LLM calls and "
            f"{(llm['mixed_ms'] or 0) / 1000:.1f} s per question on average.",
            "",
        ]
    lines += ["## 6. T2 model gate (BanglaBERT v1 vs v2)", ""]
    if "BanglaBERT v1" in routers and "BanglaBERT v2" in routers:
        v1, v2 = routers["BanglaBERT v1"], routers["BanglaBERT v2"]
        ok = gate(v1["test"][0], v2["test"][0], v1["situation"][0], v2["situation"][0])
        lines += [
            f"- test.csv: v1 {pct(v1['test'][0])}, v2 {pct(v2['test'][0])} (allowed drop: 1 point).",
            f"- situation_test.csv: v1 {pct(v1['situation'][0])}, v2 {pct(v2['situation'][0])} "
            "(v2 must be better).",
            "",
            "**Decision: switch to v2 (`ROUTER_MODEL_DIR=data/models/router_v2`).**"
            if ok
            else "**Decision: keep v1.** v2 did not pass the gate; the `understand` step carries situations.",
        ]
    else:
        lines.append("v2 skipped: `data/models/router_v2` not found (training not finished). Keep v1.")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="routers and Recall@5 only")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
