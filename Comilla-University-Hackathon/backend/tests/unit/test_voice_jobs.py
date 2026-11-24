"""Async voice answers (FR-CALL-10): fast turns answer at once, slow ones through /voice/result."""

import threading
from collections.abc import Callable
from typing import Any

from app.application.use_cases.speech import VoiceReply
from app.application.use_cases.voice_jobs import GAVE_UP, Pending, VoiceAnswers
from app.domain import messages_bn

ANSWER = VoiceReply(say=("উত্তর", messages_bn.CONTINUE))
WAIT = 0.05  # seconds; small so the tests stay fast


class ThreadRunner:
    """Runs each job on its own thread, like the real runner (FakeRunner runs inline)."""

    def submit(self, fn: Callable[..., Any], *args: Any, delay_s: float = 0) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()


class Turn:
    """A turn that finishes only when released (or at once when fast=True)."""

    def __init__(self, fast: bool = False, error: bool = False) -> None:
        self.release = threading.Event()
        if fast:
            self.release.set()
        self.error = error
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, call_sid: str, phone: str, text: str, direction: str) -> VoiceReply:
        self.calls.append((call_sid, phone, text, direction))
        self.release.wait(5)
        if self.error:
            raise RuntimeError("boom")
        return ANSWER


def answers(turn: Turn, max_polls: int = 3, clock: Callable[[], float] | None = None) -> VoiceAnswers:
    extra = {"clock": clock} if clock else {}
    waits = {"inline_wait_s": WAIT, "poll_wait_s": WAIT, "max_polls": max_polls}
    return VoiceAnswers(turn, ThreadRunner(), **waits, **extra)


def test_fast_turn_is_answered_at_once() -> None:
    turn = Turn(fast=True)
    assert answers(turn).start("CA1", "+8801712345678", "বয়স্ক ভাতা", "inbound") == ANSWER
    assert turn.calls == [("CA1", "+8801712345678", "বয়স্ক ভাতা", "inbound")]


def test_slow_turn_is_pending_then_delivered_by_result() -> None:
    turn = Turn()
    voice = answers(turn)
    pending = voice.start("CA1", "+8801712345678", "প্রশ্ন", "inbound")
    assert isinstance(pending, Pending)

    assert voice.result(pending.job_id) == pending  # still not ready: wait again
    turn.release.set()
    assert voice.result(pending.job_id) == ANSWER
    assert voice.result(pending.job_id) == GAVE_UP  # delivered once, then forgotten


def test_gives_up_with_error_after_max_polls() -> None:
    turn = Turn()
    voice = answers(turn, max_polls=2)
    job_id = voice.start("CA1", "+8801712345678", "প্রশ্ন", "inbound").job_id
    assert isinstance(voice.result(job_id), Pending)
    assert voice.result(job_id) == GAVE_UP
    assert GAVE_UP.say == (messages_bn.ERROR,) and not GAVE_UP.hang_up  # the call stays alive
    turn.release.set()


def test_unknown_job_speaks_error() -> None:
    assert answers(Turn(fast=True)).result("missing") == GAVE_UP


def test_failing_turn_speaks_error() -> None:
    turn = Turn(fast=True, error=True)
    assert answers(turn).start("CA1", "+8801712345678", "প্রশ্ন", "inbound") == GAVE_UP


def test_old_jobs_are_dropped() -> None:
    now = [0.0]
    turn = Turn()
    voice = answers(turn, clock=lambda: now[0])
    old = voice.start("CA1", "+8801712345678", "প্রশ্ন", "inbound").job_id
    now[0] = 1000.0  # well past JOB_TTL_S
    voice.start("CA2", "+8801712345678", "প্রশ্ন", "inbound")
    assert voice.result(old) == GAVE_UP
    turn.release.set()
