"""Sample question logs for the admin dashboard and the clusters (D2-R1 / D2-R3).

    python -m scripts.seed_demo_data              # replace the sample rows with 60 new ones
    python -m scripts.seed_demo_data --count 100  # another amount
    python -m scripts.seed_demo_data --clear      # only remove the sample rows

Writes realistic question logs spread over the past 7 days: the 8 services and out-of-scope
questions, phone calls and the app, answered / follow-up / fallback. Question texts come from
data/questions/seed.csv and out_of_scope.csv. Every row has is_demo = true, so it can be removed
again at any time without touching real questions. Real conversations and checklists are not touched.
Say in the demo that the dashboard history is sample data.
"""

import argparse
import csv
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.application.privacy import hash_phone
from app.config import BACKEND_DIR, get_settings
from app.container import Container
from app.domain.entities import QuestionLog
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, RouterSource

QUESTIONS_DIR = BACKEND_DIR / "data" / "questions"
DEFAULT_COUNT = 60
DAYS = 7

# Shares of the sample rows (they add up to 1.0).
SHARE_FALLBACK = 0.12  # out-of-scope questions, safely refused
SHARE_FOLLOW_UP = 0.06  # the agent asked one more question first
SHARE_VOICE = 0.6  # the rest comes from the app


def read_questions(path: Path, label_column: str) -> list[tuple[str, str]]:
    """(text, label) pairs from one of the question CSV files."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [
            (row["text"].strip(), row[label_column].strip())
            for row in csv.DictReader(f)
            if row["text"].strip()
        ]


def demo_phone_hashes(salt: str, how_many: int = 25) -> list[str]:
    """Hashes of made-up numbers (+8801700000001 ...), so several questions share a caller."""
    return [hash_phone(PhoneNumber(f"+88017{i:08d}"), salt) for i in range(1, how_many + 1)]


def build_logs(
    count: int,
    in_scope: list[tuple[str, str]],
    out_of_scope: list[tuple[str, str]],
    phone_hashes: list[str],
    now: datetime,
    rng: random.Random,
) -> list[QuestionLog]:
    """`count` sample logs, oldest first. Pure: the same rng seed gives the same rows."""
    services = [(text, label) for text, label in in_scope if label != "other"]
    n_fallback = round(count * SHARE_FALLBACK)
    n_follow_up = round(count * SHARE_FOLLOW_UP)
    statuses = (
        [AnswerStatus.FALLBACK] * n_fallback
        + [AnswerStatus.FOLLOW_UP] * n_follow_up
        + [AnswerStatus.ANSWERED] * (count - n_fallback - n_follow_up)
    )
    rng.shuffle(statuses)

    logs: list[QuestionLog] = []
    for status in statuses:
        voice = rng.random() < SHARE_VOICE
        if status is AnswerStatus.FALLBACK:
            text, service_id = rng.choice(out_of_scope)[0], "other"
            confidence, router = rng.uniform(0.25, 0.6), RouterSource.LLM
            latency, llm_calls = rng.randint(1200, 3000), 2
        else:
            text, service_id = rng.choice(services)
            confidence = rng.uniform(0.75, 0.99)
            router = rng.choice([RouterSource.BANGLABERT, RouterSource.BANGLABERT, RouterSource.TFIDF])
            latency = rng.randint(2500, 5500) if voice else rng.randint(2000, 6500)
            llm_calls = 2 if voice else 3
            if rng.random() < 0.2:  # answered from the answer cache
                latency, llm_calls = rng.randint(150, 600), 0
        # More questions in the last days: the dashboard should look busy "now".
        age = timedelta(days=DAYS) * (rng.random() ** 1.7)
        logs.append(
            QuestionLog(
                phone_hash=rng.choice(phone_hashes),
                channel=Channel.VOICE if voice else Channel.APP,
                text=text,
                status=status,
                service_id=service_id,
                confidence=round(confidence, 3),
                router_source=router,
                latency_ms=latency,
                llm_calls=llm_calls,
                llm_backend="gemini",
                is_demo=True,
                created_at=now - age,
            )
        )
    logs.sort(key=lambda log: log.created_at)
    return logs


def seed(container: Container, count: int, rng: random.Random, now: datetime | None = None) -> int:
    """Removes old sample rows, writes `count` new ones. Returns how many were written."""
    container.init_database()
    container.question_logs.delete_demo()
    logs = build_logs(
        count,
        read_questions(QUESTIONS_DIR / "seed.csv", "label"),
        read_questions(QUESTIONS_DIR / "out_of_scope.csv", "topic"),
        demo_phone_hashes(container.settings.phone_hash_salt.get_secret_value()),
        now or datetime.now(UTC),
        rng,
    )
    for log in logs:
        container.question_logs.add(log)
    return len(logs)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sample question logs for the admin dashboard.")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="how many rows (default 60)")
    parser.add_argument("--clear", action="store_true", help="only remove the sample rows")
    parser.add_argument("--seed", type=int, default=7, help="random seed (same seed, same rows)")
    args = parser.parse_args(argv)

    container = Container(get_settings())
    try:
        if args.clear:
            container.init_database()
            print(f"Removed {container.question_logs.delete_demo()} sample rows.")
            return
        written = seed(container, max(1, args.count), random.Random(args.seed))
        stats = container.question_logs.stats()
        print(f"Wrote {written} sample rows (is_demo = true). The dashboard now has {stats.total} questions:")
        print(f"  by status:  {dict(stats.by_status)}")
        print(f"  by channel: {dict(stats.by_channel)}")
        print("Remove them again with: python -m scripts.seed_demo_data --clear")
    finally:
        container.close()


if __name__ == "__main__":
    main()
