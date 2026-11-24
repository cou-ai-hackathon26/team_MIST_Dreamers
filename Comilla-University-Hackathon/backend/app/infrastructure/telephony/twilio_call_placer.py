"""CallPlacer adapter: outbound calls through Twilio (FR-CALL-07, 08).

When the citizen answers, Twilio fetches /voice/start and the normal call flow begins;
/voice/status gets the end of the call (FR-CALL-11).
"""

import logging

from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.rest import Client

from app.domain.errors import DomainError
from app.domain.value_objects import PhoneNumber

log = logging.getLogger(__name__)

START_PATH = "/voice/start"
STATUS_PATH = "/voice/status"


class CallFailed(DomainError):
    """Twilio refused the call (e.g. an unverified number on a trial account, or wrong credentials)."""

    code = "CALL_FAILED"


class TwilioCallPlacer:
    def __init__(self, account_sid: str, auth_token: str, from_number: str, public_url: str) -> None:
        self._client = Client(account_sid, auth_token) if account_sid and auth_token else None
        self._from = from_number
        base = public_url.rstrip("/")
        self._start_url = base + START_PATH
        self._status_url = base + STATUS_PATH

    def call(self, phone: PhoneNumber) -> str:
        if self._client is None or not self._from:
            raise CallFailed("Twilio is not configured (TWILIO_ACCOUNT_SID, _AUTH_TOKEN, _NUMBER)")
        try:
            call = self._client.calls.create(
                to=phone.e164,
                from_=self._from,
                url=self._start_url,  # Twilio uses POST by default; trial accounts refuse extra parameters
                status_callback=self._status_url,
            )
        except TwilioRestException as e:  # 21219: trial account, number not verified
            log.warning("twilio call failed code=%s status=%s msg=%s", e.code, e.status, e.msg)
            raise CallFailed(f"twilio refused the call (code {e.code})") from e
        except TwilioException as e:
            log.warning("twilio call failed: %s", type(e).__name__)
            raise CallFailed("twilio call failed") from e
        log.info("call-back placed call_sid=%s", call.sid)
        return str(call.sid)
