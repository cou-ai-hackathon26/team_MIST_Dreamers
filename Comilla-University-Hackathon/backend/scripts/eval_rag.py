"""RAG evaluation and answer check (D2-T3, FR-DATA-09, SRS 11).

Run from backend/ (PowerShell: first `$env:PYTHONIOENCODING = "utf-8"`):
    python -m scripts.eval_rag                 # everything (about 180 Gemini calls, 5 to 10 minutes)
    python -m scripts.eval_rag --no-llm        # Recall@5 only
    python -m scripts.eval_rag --score         # after the team marked answer_check.csv: update the report

What it measures (the answer cache is switched off, so latencies are real):
1. Recall@5: is a passage of the question's service in the top 5 when searching ALL services?
2. Safe refusal: off-topic questions (out_of_scope.csv + test questions labelled `other`) must
   end in the fixed FALLBACK text.
3. Answers: 4 test questions per service on the app channel -> docs/results/answer_check.csv for
   the team to mark (column `correct`: yes / no), plus LLM calls and latency.
4. Voice latency: 2 questions per service on the voice channel (fast mode).
Writes docs/results/rag_eval.md, stating which LLM backend and models produced it (SRS 11).
"""

import argparse
import csv
import dataclasses
import logging
import random
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date

from app.config import BACKEND_DIR, Settings
from app.container import Container
from app.domain.entities import Answer
from app.domain.errors import DomainError, LLMUnavailable
from app.domain.messages_bn import FALLBACK
from app.domain.policies import TOP_K
from app.domain.value_objects import AnswerStatus, Channel
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever

QUESTIONS = BACKEND_DIR / "data" / "questions"
RESULTS = BACKEND_DIR.parent / "docs" / "results"
REPORT = RESULTS / "rag_eval.md"
ANSWER_CSV = RESULTS / "answer_check.csv"
SEED = 7
BUSY_ATTEMPTS = 3  # a question is tried this many times when Gemini says "high demand"
BUSY_WAIT_SECONDS = 10
START, END = "<!-- correctness:start -->", "<!-- correctness:end -->"
YES = {"yes", "y", "1", "true", "ঠিক", "হ্যাঁ", "correct"}
NO = {"no", "n", "0", "false", "ভুল", "না", "incorrect", "wrong"}


@dataclasses.dataclass
class Run:
    question: str
    service: str
    answer: Answer | None
    seconds: float
    error: str = ""


def read(name: str) -> list[dict[str, str]]:
    with (QUESTIONS / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pick(rows: list[dict[str, str]], per_service: int, skip: set[str] = frozenset()) -> list[dict[str, str]]:  # type: ignore[assignment]
    """`per_service` questions per service (not `other`), same choice every run."""
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["label"] != "other" and row["text"] not in skip:
            by_label[row["label"]].append(row)
    rng = random.Random(SEED)
    return [row for label in sorted(by_label) for row in rng.sample(by_label[label], per_service)]


def pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "-"


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))] if ordered else 0.0


# ---------------------------------------------------------------- 1. retrieval


def recall_at_k(container: Container) -> tuple[dict[str, list[bool]], list[float]]:
    retriever = ChromaRetriever(container.settings.chroma_dir, container.embedder, min_filtered=0)
    if retriever.count() == 0:
        raise SystemExit("The search index is empty. Run: python -m scripts.ingest")
    hits: dict[str, list[bool]] = defaultdict(list)
    ranks: list[float] = []
    for row in read("test.csv"):
        if row["label"] == "other":
            continue
        found = retriever.search(row["text"], None, TOP_K)
        services = [p.service_id for p in found]
        hits[row["label"]].append(row["label"] in services)
        ranks.append(1 / (services.index(row["label"]) + 1) if row["label"] in services else 0.0)
    return hits, ranks


# ---------------------------------------------------------------- 2 to 4. the agent


def ask_all(
    engine: LangGraphAnswerEngine, rows: list[tuple[str, str]], channel: Channel, title: str
) -> list[Run]:
    runs = []
    for i, (question, service) in enumerate(rows, 1):
        answer, error = None, ""
        for _ in range(BUSY_ATTEMPTS):
            started = time.perf_counter()  # a busy-Gemini retry is not part of the measured time
            try:
                answer, error = engine.answer(question, [], channel), ""
                break
            except LLMUnavailable as exc:  # Gemini overloaded (503): wait and try again
                answer, error = None, exc.code
                time.sleep(BUSY_WAIT_SECONDS)
            except DomainError as exc:
                answer, error = None, exc.code
                break
        runs.append(Run(question, service, answer, time.perf_counter() - started, error))
        status = answer.status.value if answer else f"ERROR {error}"
        print(f"  {title} {i}/{len(rows)}  {status:<10} {runs[-1].seconds:5.1f} s  {question[:50]}")
    return runs


def write_answer_csv(runs: list[Run]) -> None:
    with ANSWER_CSV.open("w", encoding="utf-8-sig", newline="") as f:  # BOM: Excel shows Bangla
        writer = csv.writer(f)
        writer.writerow(["id", "service", "question", "status", "router", "speech_text", "checklist",
                         "sources", "correct", "notes"])  # fmt: skip
        for i, r in enumerate(runs, 1):
            a = r.answer
            checklist = ""
            if a and a.checklist:
                c = a.checklist
                checklist = f"কারা: {c.who} | লাগবে: {', '.join(c.papers)} | ফি: {c.fee} | কোথায়: {c.where}"
            sources = " ;; ".join(f"{c.title} <{c.source_url}>" for c in a.citations) if a else ""
            writer.writerow([
                i, r.service, r.question, a.status.value if a else f"error {r.error}",
                a.router_source.value if a and a.router_source else "", a.speech_text if a else "",
                checklist, sources, "", "",
            ])  # fmt: skip


def marked_rows() -> list[dict[str, str]]:
    if not ANSWER_CSV.exists():
        return []
    with ANSWER_CSV.open(encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if row.get("correct", "").strip()]


# ---------------------------------------------------------------- report


def correctness_block() -> str:
    rows = marked_rows()
    yes = sum(r["correct"].strip().lower() in YES for r in rows)
    no = sum(r["correct"].strip().lower() in NO for r in rows)
    if not rows:
        body = ("Not marked yet. Ragib and Ariful open `docs/results/answer_check.csv`, compare each answer "
                "with its sources and write `yes` or `no` in `correct` (and a short note when no). "
                "Then run `python -m scripts.eval_rag --score`.")  # fmt: skip
    else:
        unclear = len(rows) - yes - no
        body = (
            f"**{pct(yes, yes + no)}** correct ({yes} yes, {no} no, {unclear} unclear). Target: at least 90%."
        )
        wrong = [r for r in rows if r["correct"].strip().lower() in NO]
        if wrong:
            body += "\n\n| # | Service | Question | Note |\n|---|---|---|---|\n" + "\n".join(
                f"| {r['id']} | `{r['service']}` | {r['question']} | {r.get('notes', '')} |" for r in wrong
            )
    return f"{START}\n{body}\n{END}"


def write_report(
    settings: Settings,
    hits: dict[str, list[bool]],
    ranks: list[float],
    refusals: list[Run] | None,
    answers: list[Run] | None,
    voice: list[Run] | None,
) -> None:
    total = [h for found in hits.values() for h in found]
    recall = sum(total) / len(total)
    lines = [
        "# RAG evaluation and answer check (FR-DATA-09, SRS 11)",
        "",
        f"Generated by `python -m scripts.eval_rag` on {date.today():%d %b %Y}. "
        f"`LLM_BACKEND={settings.llm_backend}`, main model `{settings.gemini_model_main}`, fast model "
        f"`{settings.gemini_model_fast}`, `ROUTER_BACKEND={settings.router_backend}`, "
        f"`VOICE_FAST_MODE={str(settings.voice_fast_mode).lower()}`. "
        "The answer cache was off, so times are real.",
        "",
        "## Summary",
        "",
        "| Metric | Result | Target |",
        "|---|---|---|",
        f"| Retrieval Recall@{TOP_K} (all services searched) "
        f"| **{recall:.1%}** (MRR {statistics.mean(ranks):.2f}) "
        f"| at least 90% |",
    ]
    if refusals is not None:
        safe = [r for r in refusals if r.answer and r.answer.status is AnswerStatus.FALLBACK
                and r.answer.speech_text == FALLBACK]  # fmt: skip
        lines.append(f"| Safe refusal ({len(refusals)} off-topic questions) "
                     f"| **{pct(len(safe), len(refusals))}** "
                     f"| at least 95% |")  # fmt: skip
    if answers is not None:
        lines.append("| Answer correctness (team check) | see below | at least 90% |")
    if voice is not None:
        times = [r.seconds for r in voice if r.answer]
        lines.append(f"| Voice latency, median ({len(times)} calls, fast mode) "
                     f"| **{statistics.median(times):.1f} s** "
                     f"| at most 5 s |")  # fmt: skip

    lines += [
        "",
        f"## Retrieval Recall@{TOP_K} per service",
        "",
        "| Service | Found | Recall |",
        "|---|---|---|",
    ]
    for label, found in sorted(hits.items()):
        lines.append(f"| `{label}` | {sum(found)}/{len(found)} | {pct(sum(found), len(found))} |")

    if refusals is not None:
        unsafe = [r for r in refusals if not (r.answer and r.answer.status is AnswerStatus.FALLBACK)]
        safe_count = len(refusals) - len(unsafe)
        summary = f"{safe_count} of {len(refusals)} off-topic questions ended in the exact FALLBACK text."
        lines += ["", "## Safe refusal", "", summary]
        if unsafe:
            lines += ["", "Not refused:", "", "| Question | Status | Routed to |", "|---|---|---|"]
            lines += [f"| {r.question} | {r.answer.status.value if r.answer else 'error ' + r.error} "
                      f"| `{r.answer.service_id if r.answer else '-'}` |" for r in unsafe]  # fmt: skip

    for title, runs in (("App answers", answers), ("Voice answers (fast mode)", voice)):
        if runs is None:
            continue
        ok = [r for r in runs if r.answer]
        statuses = Counter(r.answer.status.value for r in ok)
        times = [r.seconds for r in ok]
        lines += [
            "", f"## {title}: {len(runs)} questions", "",
            "| Answered | Fallback | Follow-up | Error | LLM calls (mean) | Latency median / p95 |",
            "|---|---|---|---|---|---|",
            f"| {statuses['answered']} | {statuses['fallback']} | {statuses['follow_up']} "
            f"| {len(runs) - len(ok)} "
            f"| {statistics.mean(r.answer.llm_calls for r in ok):.1f} "
            f"| {statistics.median(times):.1f} s / {quantile(times, 0.95):.1f} s |",
        ]  # fmt: skip

    lines += ["", "## Answer correctness (team check)", "", correctness_block(), ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def update_correctness_only() -> int:
    if not REPORT.exists():
        print("No report yet: run python -m scripts.eval_rag first.")
        return 1
    text = REPORT.read_text(encoding="utf-8")
    new = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: correctness_block(), text, flags=re.S)
    REPORT.write_text(new, encoding="utf-8")
    print(correctness_block().replace(START, "").replace(END, "").strip())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Recall@5 only, no Gemini calls")
    parser.add_argument("--score", action="store_true", help="only re-read the marked answer_check.csv")
    parser.add_argument("--answers", type=int, default=4, help="app questions per service")
    parser.add_argument("--voice", type=int, default=2, help="voice questions per service")
    parser.add_argument("--overwrite", action="store_true", help="replace an answer_check.csv that has marks")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.score:
        return update_correctness_only()
    if not args.no_llm and marked_rows() and not args.overwrite:
        print("answer_check.csv already has marks. Use --score, or --overwrite to throw them away.")
        return 1

    settings = Settings()
    container = Container(settings)
    print("1. Recall@5 ...")
    hits, ranks = recall_at_k(container)
    refusals = answers = voice = None
    if not args.no_llm:
        engine = LangGraphAnswerEngine(dataclasses.replace(container.agent_deps, cache=None))
        test = read("test.csv")
        off_topic = [(r["text"], "other") for r in read("out_of_scope.csv")]
        off_topic += [(r["text"], "other") for r in test if r["label"] == "other"]
        print(f"2. Safe refusal on {len(off_topic)} off-topic questions ...")
        refusals = ask_all(engine, off_topic, Channel.APP, "refusal")
        chosen = pick(test, args.answers)
        print(f"3. {len(chosen)} app answers for the team check ...")
        answers = ask_all(engine, [(r["text"], r["label"]) for r in chosen], Channel.APP, "app")
        write_answer_csv(answers)
        voice_rows = pick(test, args.voice, skip={r["text"] for r in chosen})
        print(f"4. Voice latency on {len(voice_rows)} questions ...")
        voice = ask_all(engine, [(r["text"], r["label"]) for r in voice_rows], Channel.VOICE, "voice")
    write_report(settings, hits, ranks, refusals, answers, voice)
    container.close()
    print(
        f"wrote {REPORT.relative_to(BACKEND_DIR.parent)}" + ("" if args.no_llm else " and answer_check.csv")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
