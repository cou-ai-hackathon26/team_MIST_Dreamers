"""Use cases: store a call's start and end in the calls table (FR-CALL-11).

Turns are counted by HandleVoiceTurn (speech.py). Webhooks can repeat or arrive late, so both
steps are safe to run twice and never raise into the call flow.
"""

import logging

from app.application.ports.repositories import CallRepo
from app.domain.errors import InvalidPhone
from app.domain.value_objects import PhoneNumber

log = logging.getLogger(__name__)


class RecordCallStart:
    def __init__(self, calls: CallRepo) -> None:
        self._calls = calls

    def execute(self, call_sid: str, phone: str, direction: str) -> bool:
        """Returns False (and stores nothing) when the citizen's number is not a Bangladeshi one."""
        try:
            number = PhoneNumber.parse(phone)
        except InvalidPhone:
            log.warning("call %s from a non-Bangladeshi number; not stored", call_sid)
            return False
        self._calls.record_start(call_sid, number, direction)
        log.info("call started call_sid=%s direction=%s", call_sid, direction)
        return True


class HandleCallEnd:
    def __init__(self, calls: CallRepo) -> None:
        self._calls = calls

    def execute(self, call_sid: str) -> None:
        self._calls.record_end(call_sid)  # an unknown call is ignored by the repository
        log.info("call ended call_sid=%s", call_sid)
