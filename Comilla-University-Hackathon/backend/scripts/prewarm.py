"""Fill the answer cache with the demo questions (D2-T4, FR-AGT-15). No conversation is saved.

Run from backend/ (PowerShell: first `$env:PYTHONIOENCODING = "utf-8"`), before judging or a rehearsal:
    python -m scripts.prewarm                  # app answers
    python -m scripts.prewarm --voice          # phone answers too (fast mode, shorter text)
    python -m scripts.prewarm --file my.txt    # your own list, one question per line

Run it twice: the second run shows the cache hits and their times (target: under 3 s each).
Cached answers live 24 hours in the SQLite database, so they survive a server restart. For phone
calls Twilio's transcript rarely matches typed text exactly, so also ask each demo question once in
a real call during the rehearsal.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from app.config import BACKEND_DIR, Settings
from app.container import Container
from app.domain.errors import DomainError
from app.domain.value_objects import Channel

DEFAULT_FILE = BACKEND_DIR / "data" / "questions" / "demo_questions.txt"


def read_questions(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--voice", action="store_true", help="also warm the phone answers")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    container = Container(Settings())
    container.init_database()  # the cache table lives in the app database
    engine = container.answer_engine
    channels = [Channel.APP, Channel.VOICE] if args.voice else [Channel.APP]
    questions = read_questions(args.file)
    failures = 0
    try:
        for channel in channels:
            print(f"\n--- {channel.value}")
            for question in questions:
                started = time.perf_counter()
                try:
                    answer = engine.answer(question, [], channel)
                except DomainError as exc:
                    failures += 1
                    print(f"FAILED ({exc.code})  {question}")
                    continue
                seconds = time.perf_counter() - started
                if "cache_lookup" in answer.timings and answer.llm_calls == 0:
                    note = "cache hit"
                elif "cache_lookup" in answer.timings and answer.status.value == "answered":
                    note = "stored"
                else:
                    note = "not cacheable (router unsure, other or fallback)"
                print(f"{seconds:5.1f} s  {answer.status.value:<9} {note:<48} {question}")
    finally:
        container.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
