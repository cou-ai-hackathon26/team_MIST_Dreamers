"""Per-call silence counter for the webhook flow (FR-CALL-04).

Twilio calls /voice/respond once per turn, so the count between turns lives here, keyed by CallSid.
In memory is enough: one server process, and a call lasts minutes.
"""

from threading import Lock


class SilenceCounter:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = Lock()  # FastAPI runs sync routes in a thread pool

    def silent(self, call_sid: str) -> int:
        """Records one empty result and returns how many in a row this call has had."""
        with self._lock:
            self._counts[call_sid] = self._counts.get(call_sid, 0) + 1
            return self._counts[call_sid]

    def heard(self, call_sid: str) -> None:
        """The caller spoke: the next silence counts as the first again."""
        with self._lock:
            self._counts.pop(call_sid, None)

    def forget(self, call_sid: str) -> None:
        """The call ended: drop its entry."""
        self.heard(call_sid)
