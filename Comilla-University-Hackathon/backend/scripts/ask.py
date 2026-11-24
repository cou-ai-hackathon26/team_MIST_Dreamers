"""Ask the real agent one question from the terminal (D1-T4 done-check). No database is touched.

Run from backend/ (PowerShell: first `$env:PYTHONIOENCODING = "utf-8"`):
    python -m scripts.ask "আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?"
    python -m scripts.ask --voice "বিধবা ভাতার জন্য কী লাগে?"
    python -m scripts.ask "বিধবা ভাতার জন্য কী লাগে?" --then "হ্যাঁ"      # follow-up turn (FR-AGT-17)
"""

import argparse
import logging
import sys

from app.config import Settings
from app.container import Container
from app.domain.entities import Answer, Message
from app.domain.errors import DomainError
from app.domain.value_objects import Channel, Role


def show(answer: Answer) -> None:
    print(f"status   : {answer.status}")
    print(f"service  : {answer.service_id}  ", end="")
    print(f"(router={answer.router_source}, confidence={answer.confidence:.2f})")
    print(f"speech   : {answer.speech_text}")
    if answer.follow_up_question:
        print(f"follow-up: {answer.follow_up_question}")
    if answer.checklist:
        c = answer.checklist
        print("checklist:")
        print(f"  who     : {c.who}")
        print(f"  papers  : {', '.join(c.papers) or '-'}")
        print(f"  fee     : {c.fee}")
        print(f"  where   : {c.where}")
        print(f"  decision: {c.decision}")
    for i, cite in enumerate(answer.citations, 1):
        print(f"source {i} : {cite.title}  {cite.source_url}")
    print(f"llm_calls: {answer.llm_calls}  backend={answer.llm_backend}")
    print("timings  : " + ", ".join(f"{k} {v:.0f} ms" for k, v in answer.timings.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--voice", action="store_true", help="answer as on a phone call")
    parser.add_argument("--then", default=None, help="a second turn in the same conversation")
    parser.add_argument("--display", action="store_true", help="also print the app's markdown text")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    container = Container(Settings())
    channel = Channel.VOICE if args.voice else Channel.APP
    history: list[Message] = []
    try:
        for turn in [args.question, args.then] if args.then else [args.question]:
            print(f"\n>>> {turn}")
            answer = container.answer_engine.answer(turn, history, channel)
            show(answer)
            if args.display:
                print("display  :\n" + answer.display_text)
            history += [
                Message(role=Role.USER, channel=channel, text=turn),
                Message(
                    role=Role.ASSISTANT,
                    channel=channel,
                    text=answer.speech_text,
                    service_id=answer.service_id,
                    status=answer.status,
                ),  # fmt: skip
            ]
    except DomainError as exc:
        print(f"FAILED ({exc.code}): {exc}")
        return 1
    finally:
        container.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
