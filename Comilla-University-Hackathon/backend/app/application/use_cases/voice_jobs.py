"""Use case: async voice answers (FR-CALL-10, NFR-PERF-01, SRS 3.1).

Twilio stops waiting for a webhook after a few seconds, but a fresh agent answer can take 7 to 16 s.
So each turn runs in the background (BackgroundRunner) and the webhook waits only a short time:

- answer ready within `inline_wait_s`: it is spoken at once (cache hits, goodbyes, fast answers);
- not ready: the caller hears WAIT_FILLER and Twilio is redirected to /voice/result?job=<id>;
- /voice/result waits up to `poll_wait_s` again; after `max_polls` waits it gives up with ERROR.

Jobs live in memory (one server process). Old jobs, e.g. from a caller who hung up, are removed.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from app.application.ports.background import BackgroundRunner
from app.application.use_cases.speech import VoiceReply
from app.domain import messages_bn

log = logging.getLogger(__name__)

# Measured on live calls: a 7.5 s reply was already too late for Twilio, 1 s replies always worked.
INLINE_WAIT_S = 4.0
POLL_WAIT_S = 4.0
MAX_POLLS = 5  # with the filler and pauses: about 25 s before the caller hears ERROR
JOB_TTL_S = 300.0

TurnFn = Callable[[str, str, str, str], VoiceReply]  # (call_sid, phone, text, direction)

GAVE_UP = VoiceReply(say=(messages_bn.ERROR,), status="error")


@dataclass(frozen=True)
class Pending:
    """The answer is not ready yet: say WAIT_FILLER (first time) and ask again for this job."""

    job_id: str


@dataclass
class _Job:
    call_sid: str
    created: float
    done: threading.Event = field(default_factory=threading.Event)
    reply: VoiceReply | None = None
    polls: int = 0


class VoiceAnswers:
    def __init__(
        self,
        turn: TurnFn,
        runner: BackgroundRunner,
        inline_wait_s: float = INLINE_WAIT_S,
        poll_wait_s: float = POLL_WAIT_S,
        max_polls: int = MAX_POLLS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._turn = turn
        self._runner = runner
        self._inline_wait_s = inline_wait_s
        self._poll_wait_s = poll_wait_s
        self._max_polls = max_polls
        self._clock = clock
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()

    def start(self, call_sid: str, phone: str, text: str, direction: str) -> VoiceReply | Pending:
        """Starts the turn in the background; returns its reply if it is ready in time."""
        self._drop_old_jobs()
        job_id = uuid.uuid4().hex
        job = _Job(call_sid=call_sid, created=self._clock())
        with self._lock:
            self._jobs[job_id] = job
        self._runner.submit(self._run, job, call_sid, phone, text, direction)
        return self._wait(job_id, job, self._inline_wait_s)

    def result(self, job_id: str) -> VoiceReply | Pending:
        """Called from /voice/result: the reply if ready, Pending to wait again, or ERROR."""
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:  # unknown or expired job (e.g. after a server restart)
            log.warning("voice job not found job=%s", job_id)
            return GAVE_UP
        job.polls += 1
        outcome = self._wait(job_id, job, self._poll_wait_s)
        if isinstance(outcome, Pending) and job.polls >= self._max_polls:
            self._forget(job_id)
            log.warning("voice job gave up job=%s call_sid=%s polls=%d", job_id, job.call_sid, job.polls)
            return GAVE_UP
        return outcome

    def _run(self, job: _Job, call_sid: str, phone: str, text: str, direction: str) -> None:
        try:
            job.reply = self._turn(call_sid, phone, text, direction)
        except Exception:  # the turn already catches errors; this is a last guard
            log.exception("voice job failed call_sid=%s", call_sid)
            job.reply = GAVE_UP
        finally:
            job.done.set()

    def _wait(self, job_id: str, job: _Job, timeout_s: float) -> VoiceReply | Pending:
        if job.done.wait(timeout_s) and job.reply is not None:
            self._forget(job_id)
            return job.reply
        log.info("voice job pending job=%s call_sid=%s polls=%d", job_id, job.call_sid, job.polls)
        return Pending(job_id)

    def _forget(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def _drop_old_jobs(self) -> None:
        cutoff = self._clock() - JOB_TTL_S
        with self._lock:
            for job_id in [j for j, job in self._jobs.items() if job.created < cutoff]:
                del self._jobs[job_id]
