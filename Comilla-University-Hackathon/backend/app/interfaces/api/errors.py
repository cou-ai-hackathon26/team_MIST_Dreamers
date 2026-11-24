"""Turns every error into the SRS error JSON with a Bangla message (SRS 8, NFR-REL-01).

    {"error": {"code": "...", "message_bn": "...", "message_en": "..."}}

Users never see a stack trace; the details go to the server log.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain import messages_bn
from app.domain.errors import DomainError, InvalidPhone, LLMUnavailable, NotFound, RateLimited

log = logging.getLogger(__name__)

# domain error -> (HTTP status, Bangla message, English message)
_DOMAIN_ERRORS: dict[type[DomainError], tuple[int, str, str]] = {
    InvalidPhone: (422, messages_bn.INVALID_PHONE, "Not a valid Bangladeshi mobile number."),
    NotFound: (404, messages_bn.NOT_FOUND, "Nothing was found."),
    RateLimited: (429, messages_bn.RATE_LIMITED, "Too many requests. Please wait a minute."),
    LLMUnavailable: (503, messages_bn.ERROR, "The AI service is unavailable right now."),
}
_FALLBACK = (500, messages_bn.ERROR, "Something went wrong. Please try again later.")


def error_body(code: str, message_bn: str, message_en: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message_bn": message_bn, "message_en": message_en}}


def _respond(status: int, code: str, message_bn: str, message_en: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(code, message_bn, message_en))


async def _domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status, bn, en = next(
        (v for cls, v in _DOMAIN_ERRORS.items() if isinstance(exc, cls)), (400, messages_bn.ERROR, str(exc))
    )
    log.info("domain error %s on %s %s: %s", exc.code, request.method, request.url.path, exc)
    return _respond(status, exc.code, bn, en)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    log.info("bad request on %s %s: %s", request.method, request.url.path, exc)
    return _respond(422, "BAD_REQUEST", messages_bn.BAD_REQUEST, "Missing or invalid fields.")


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        return _respond(404, "NOT_FOUND", messages_bn.NOT_FOUND, "This address does not exist.")
    return _respond(exc.status_code, "HTTP_ERROR", messages_bn.BAD_REQUEST, str(exc.detail))


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unexpected error on %s %s", request.method, request.url.path)
    status, bn, en = _FALLBACK
    return _respond(status, "INTERNAL_ERROR", bn, en)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
