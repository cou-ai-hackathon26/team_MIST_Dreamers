"""SMS adapter: sends through the textbee Android app on a phone with a Bangladeshi SIM (FR-SMS-03, 05).

POST https://api.textbee.dev/api/v1/gateway/send-sms
    header x-api-key: <TEXTBEE_API_KEY>
    body   {"recipients": ["+8801..."], "message": "...", "deviceId": "<TEXTBEE_DEVICE_ID>"}

Never raises to the caller: a timeout, a network error or a rejected request is logged and returns
False, so a failed SMS can never break a call or an answer.
"""

import logging

import httpx

from app.domain.value_objects import PhoneNumber
from app.infrastructure.sms.common import masked

log = logging.getLogger(__name__)

TEXTBEE_BASE_URL = "https://api.textbee.dev/api/v1"


class TextbeeSms:
    def __init__(
        self,
        api_key: str,
        device_id: str = "",
        timeout_s: float = 10.0,
        base_url: str = TEXTBEE_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self._device_id = device_id
        self._http = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            headers={"x-api-key": api_key},
        )

    def send(self, phone: PhoneNumber, text: str) -> bool:
        body: dict[str, object] = {"recipients": [phone.e164], "message": text}
        if self._device_id:
            body["deviceId"] = self._device_id
        try:
            response = self._http.post("/gateway/send-sms", json=body)
        except httpx.HTTPError as exc:  # timeout, DNS, connection refused ...
            log.warning("textbee SMS to %s failed: %s", masked(phone), type(exc).__name__)
            return False
        if response.is_success:
            log.info("textbee SMS accepted for %s (%d chars)", masked(phone), len(text))
            return True
        # The body explains the reason (bad key, device offline ...); it never contains our key.
        log.warning(
            "textbee SMS to %s rejected: HTTP %d %s", masked(phone), response.status_code, response.text[:200]
        )
        return False

    def close(self) -> None:
        self._http.close()
