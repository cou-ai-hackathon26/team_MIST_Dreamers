"""Twilio request signatures for every /voice/* webhook (FR-CALL-12, NFR-SEC-02).

Twilio signs each webhook with the account's auth token (X-Twilio-Signature header). We rebuild
the exact URL Twilio called (PUBLIC_URL + path + query string, e.g. /voice/result?job=...) because
behind ngrok the server itself sees a different host. Off unless VALIDATE_TWILIO_SIGNATURE=true.
"""

import logging

from fastapi import HTTPException, Request
from twilio.request_validator import RequestValidator

from app.interfaces.api.deps import get_container

log = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Twilio-Signature"


def called_url(public_url: str, request: Request) -> str:
    query = request.url.query
    return public_url.rstrip("/") + request.url.path + (f"?{query}" if query else "")


async def verify_twilio_signature(request: Request) -> None:
    settings = get_container(request).settings
    if not settings.validate_twilio_signature:
        return
    url = called_url(settings.public_url, request)
    form = await request.form()  # cached, so the route can still read its Form fields
    params = {key: str(value) for key, value in form.items()}
    signature = request.headers.get(SIGNATURE_HEADER, "")
    validator = RequestValidator(settings.twilio_auth_token.get_secret_value())
    if not signature or not validator.validate(url, params, signature):
        log.warning("rejected a voice webhook with a bad Twilio signature path=%s", request.url.path)
        raise HTTPException(status_code=403, detail="invalid Twilio signature")
