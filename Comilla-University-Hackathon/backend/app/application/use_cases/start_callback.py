"""Use case: call a citizen back (FR-CALL-07 "Call me", FR-CALL-08 missed call).

At most one call-back per number per `cooldown_s` (default 60 s); a repeat raises RateLimited,
which the API turns into HTTP 429 with the Bangla RATE_LIMITED message.

The call row is stored as soon as Twilio accepts the call, so a second tap before the phone is
answered is limited too. A lock makes two taps at the same moment place only one call.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.application.ports.background import BackgroundRunner
from app.application.ports.messaging import CallPlacer
from app.application.ports.repositories import CallRepo
from app.domain.errors import InvalidPhone, RateLimited
from app.domain.policies import CALLBACK_COOLDOWN_SECONDS
from app.domain.value_objects import PhoneNumber

log = logging.getLogger(__name__)

OUTBOUND = "outbound-api"  # the Direction Twilio sends for calls we place
MISSED_CALL_DELAY_S = 3.0  # the caller's line is free again before we ring (FR-CALL-08: within 10 s)


class StartCallback:
    def __init__(
        self,
        placer: CallPlacer,
        calls: CallRepo,
        cooldown_s: float = CALLBACK_COOLDOWN_SECONDS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._placer = placer
        self._calls = calls
        self._cooldown = timedelta(seconds=cooldown_s)
        self._now = now
        self._lock = threading.Lock()

    def execute(self, phone: str) -> str:
        """Places the call and returns its call SID. Raises InvalidPhone, RateLimited or CallFailed."""
        number = PhoneNumber.parse(phone)
        with self._lock:
            last = self._calls.last_outbound_at(number)
            if last is not None and self._now() - _aware(last) < self._cooldown:
                log.info("call-back rate limited (last call %s ago)", self._now() - _aware(last))
                raise RateLimited("one call-back per number per minute")
            call_sid = self._placer.call(number)
            self._calls.record_start(call_sid, number, OUTBOUND)
        return call_sid

    def run_quietly(self, phone: str) -> None:
        """For background work (missed call): failures are logged, never raised."""
        try:
            self.execute(phone)
        except RateLimited:
            log.info("missed call ignored: this number was called back less than a minute ago")
        except InvalidPhone:
            log.warning("missed call from a number we cannot call back")
        except Exception:
            log.exception("missed-call call-back failed")


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class HandleMissedCall:
    """FR-CALL-08: the incoming call is rejected (caller pays nothing) and we call back shortly."""

    def __init__(
        self, callback: StartCallback, runner: BackgroundRunner, delay_s: float = MISSED_CALL_DELAY_S
    ) -> None:
        self._callback = callback
        self._runner = runner
        self._delay_s = delay_s

    def execute(self, phone: str) -> bool:
        """True when a call-back was scheduled; False for a number we cannot call (not Bangladeshi)."""
        try:
            PhoneNumber.parse(phone)
        except InvalidPhone:
            log.warning("missed call from a non-Bangladeshi number; no call-back")
            return False
        self._runner.submit(self._callback.run_quietly, phone, delay_s=self._delay_s)
        log.info("missed call: call-back in %.0f s", self._delay_s)
        return True
