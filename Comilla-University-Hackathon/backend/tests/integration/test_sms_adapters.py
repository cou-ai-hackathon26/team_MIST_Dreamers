"""SMS adapters and their wiring (D1-A4: FR-SMS-03, 05, NFR-PRIV-01). No real network: httpx.MockTransport."""

import json
import logging

import httpx
import pytest

from app.application.ports.background import BackgroundRunner
from app.application.ports.messaging import SmsSender
from app.config import Settings
from app.container import Container
from app.domain.value_objects import PhoneNumber
from app.infrastructure.background.thread_runner import ThreadPoolRunner
from app.infrastructure.sms.common import masked
from app.infrastructure.sms.console_sms import ConsoleSms
from app.infrastructure.sms.textbee_sms import TEXTBEE_BASE_URL, TextbeeSms

PHONE = PhoneNumber.parse("01712345678")
TEXT = "এক কল: বয়স্ক ভাতা\nফি: বিনামূল্যে"


def textbee_with(handler, device_id: str = "dev-1") -> TextbeeSms:
    client = httpx.Client(
        base_url=TEXTBEE_BASE_URL, headers={"x-api-key": "test-key"}, transport=httpx.MockTransport(handler)
    )
    return TextbeeSms("test-key", device_id, client=client)


def test_masked_hides_most_of_the_number() -> None:
    assert masked(PHONE) == "+880171*****78"
    assert len(masked(PHONE)) == len(PHONE.e164)


def test_console_sms_logs_the_text_without_the_number(caplog: pytest.LogCaptureFixture) -> None:
    sms = ConsoleSms()
    with caplog.at_level(logging.INFO):
        assert sms.send(PHONE, TEXT) is True
    logged = caplog.text
    assert "এক কল: বয়স্ক ভাতা" in logged
    assert PHONE.e164 not in logged and "1712345678" not in logged


def test_textbee_sends_the_documented_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"data": {"success": True}})

    assert textbee_with(handler).send(PHONE, TEXT) is True
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "https://api.textbee.dev/api/v1/gateway/send-sms"
    assert request.headers["x-api-key"] == "test-key"
    assert json.loads(request.content) == {"recipients": [PHONE.e164], "message": TEXT, "deviceId": "dev-1"}


def test_textbee_without_device_id_uses_the_default_device() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={})

    assert textbee_with(handler, device_id="").send(PHONE, TEXT) is True
    assert "deviceId" not in bodies[0]


@pytest.mark.parametrize("status", [400, 401, 429, 500])
def test_textbee_rejection_returns_false(status: int, caplog: pytest.LogCaptureFixture) -> None:
    sms = textbee_with(lambda request: httpx.Response(status, json={"error": "nope"}))
    with caplog.at_level(logging.WARNING):
        assert sms.send(PHONE, TEXT) is False
    assert PHONE.e164 not in caplog.text and "test-key" not in caplog.text


@pytest.mark.parametrize("error", [httpx.ConnectTimeout("slow"), httpx.ConnectError("down")])
def test_textbee_network_errors_return_false_never_raise(error: Exception) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    assert textbee_with(handler).send(PHONE, TEXT) is False


# ---------------------------------------------------------------- container wiring


def container_for(**settings) -> Container:
    return Container(Settings(_env_file=None, database_url="sqlite://", **settings))


def test_console_is_the_default_backend() -> None:
    c = container_for()
    assert isinstance(c.sms, ConsoleSms) and isinstance(c.sms, SmsSender)
    c.close()


def test_textbee_backend_is_chosen_from_config() -> None:
    c = container_for(sms_backend="textbee", textbee_api_key="k", textbee_device_id="d")
    assert isinstance(c.sms, TextbeeSms)
    c.close()


def test_runner_is_a_thread_pool_and_is_shared() -> None:
    c = container_for()
    assert isinstance(c.runner, ThreadPoolRunner) and isinstance(c.runner, BackgroundRunner)
    assert c.runner is c.runner  # one pool for SMS, call-back and async voice
    c.runner.close()
    c.close()


def test_ask_question_gets_the_sms_sender_and_the_runner() -> None:
    c = container_for()
    use_case = c.ask_question
    assert use_case._sms is c.sms and use_case._runner is c.runner
    c.runner.close()
    c.close()
