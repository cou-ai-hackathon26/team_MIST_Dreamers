"""SMS adapter for development: prints the SMS to the server log instead of sending it (FR-SMS-03).

SMS_BACKEND=console (the default). Lets the whole SMS flow be tested with no phone and no cost.
"""

import logging

from app.domain.value_objects import PhoneNumber
from app.infrastructure.sms.common import masked

log = logging.getLogger(__name__)


class ConsoleSms:
    def __init__(self) -> None:
        self.sent_count = 0

    def send(self, phone: PhoneNumber, text: str) -> bool:
        self.sent_count += 1
        log.info("SMS (console, not sent) to %s, %d chars:\n%s", masked(phone), len(text), text)
        return True
