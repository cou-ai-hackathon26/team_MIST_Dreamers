"""Call-back API, missed-call mode and Twilio signatures end to end (FR-CALL-07, 08, 12). No network."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app.config import Settings
from app.domain import messages_bn
from app.main import create_app
from tests.fakes import FakeCallPlacer, FakeRunner

PHONE = "+8801712345678"
PUBLIC_URL = "https://example.ngrok-free.dev"
TOKEN = "test-auth-token"

MakeClient = Callable[..., TestClient]


@pytest.fixture
def make_client() -> Iterator[MakeClient]:
    clients: list[TestClient] = []

    def make(fake_twilio: bool = True, **overrides: object) -> TestClient:
        no_store = Path(__file__).parent / "no_store"  # never created
        settings = Settings(
            _env_file=None,
            database_url="sqlite://",
            chroma_dir=no_store,
            tfidf_model_path=no_store / "r.joblib",
            agent_engine="stub",
            sms_backend="console",
            public_url=PUBLIC_URL,
            twilio_account_sid="",
            twilio_auth_token=TOKEN,
            **overrides,
        )
        client = TestClient(create_app(settings))
        client.__enter__()
        container = client.app.state.container
        if fake_twilio:
            container.__dict__["call_placer"] = FakeCallPlacer()
        container.__dict__["runner"] = FakeRunner()  # missed-call call-back runs at once
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


def placed(client: TestClient) -> list[str]:
    return [p.e164 for p in client.app.state.container.call_placer.calls]


# ---------------------------------------------------------------- POST /api/v1/callback


def test_call_me_places_a_call(make_client: MakeClient) -> None:
    client = make_client()
    response = client.post("/api/v1/callback", json={"phone": "01712345678"})
    assert response.status_code == 200
    assert response.json() == {"call_sid": "CA_fake_1"}
    assert placed(client) == [PHONE]


def test_second_tap_within_a_minute_gets_429_in_bangla(make_client: MakeClient) -> None:
    client = make_client()
    client.post("/api/v1/callback", json={"phone": PHONE})
    response = client.post("/api/v1/callback", json={"phone": PHONE})
    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert error["message_bn"] == messages_bn.RATE_LIMITED
    assert placed(client) == [PHONE]


def test_invalid_number_gets_422(make_client: MakeClient) -> None:
    response = make_client().post("/api/v1/callback", json={"phone": "12345"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PHONE"


def test_twilio_not_configured_gives_the_bangla_error(make_client: MakeClient) -> None:
    response = make_client(fake_twilio=False).post("/api/v1/callback", json={"phone": PHONE})
    assert response.status_code == 400  # interfaces/api/errors.py: other domain errors
    assert response.json()["error"]["code"] == "CALL_FAILED"
    assert response.json()["error"]["message_bn"] == messages_bn.ERROR


# ---------------------------------------------------------------- missed-call mode


def test_missed_call_is_rejected_and_called_back(make_client: MakeClient) -> None:
    client = make_client(missed_call_mode=True)
    response = client.post("/voice/incoming", data={"CallSid": "CA1", "From": PHONE, "Direction": "inbound"})
    assert response.status_code == 200
    assert '<Reject reason="busy" />' in response.text
    assert "<Say" not in response.text  # nothing that would answer (and bill) the call
    assert placed(client) == [PHONE]


def test_missed_call_from_a_foreign_number_is_only_rejected(make_client: MakeClient) -> None:
    client = make_client(missed_call_mode=True)
    response = client.post("/voice/incoming", data={"CallSid": "CA1", "From": "+15005550006"})
    assert '<Reject reason="busy" />' in response.text
    assert placed(client) == []


def test_without_missed_call_mode_the_call_is_answered(make_client: MakeClient) -> None:
    response = make_client().post("/voice/incoming", data={"CallSid": "CA1", "From": PHONE})
    assert messages_bn.GREETING in response.text


# ---------------------------------------------------------------- signatures (FR-CALL-12)


def signed(path: str, form: dict[str, str]) -> dict[str, str]:
    signature = RequestValidator(TOKEN).compute_signature(PUBLIC_URL + path, form)
    return {"X-Twilio-Signature": signature}


def test_signed_webhook_is_accepted(make_client: MakeClient) -> None:
    client = make_client(validate_twilio_signature=True)
    form = {"CallSid": "CA1", "From": PHONE}
    response = client.post("/voice/incoming", data=form, headers=signed("/voice/incoming", form))
    assert response.status_code == 200
    assert messages_bn.GREETING in response.text


def test_signature_covers_the_query_string(make_client: MakeClient) -> None:
    client = make_client(validate_twilio_signature=True)
    form = {"CallSid": "CA1"}
    path = "/voice/result?job=missing"
    response = client.post(path, data=form, headers=signed(path, form))
    assert response.status_code == 200
    assert messages_bn.ERROR in response.text  # unknown job, but the signature was fine


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Twilio-Signature": "forged"}],
    ids=["missing", "forged"],
)
def test_unsigned_or_forged_webhook_gets_403(make_client: MakeClient, headers: dict[str, str]) -> None:
    client = make_client(validate_twilio_signature=True)
    response = client.post("/voice/incoming", data={"CallSid": "CA1", "From": PHONE}, headers=headers)
    assert response.status_code == 403


def test_changed_form_breaks_the_signature(make_client: MakeClient) -> None:
    client = make_client(validate_twilio_signature=True)
    headers = signed("/voice/incoming", {"CallSid": "CA1", "From": PHONE})
    changed = {"CallSid": "CA1", "From": "+8801899999999"}
    response = client.post("/voice/incoming", data=changed, headers=headers)
    assert response.status_code == 403


def test_signatures_off_by_default(make_client: MakeClient) -> None:
    response = make_client().post("/voice/incoming", data={"CallSid": "CA1", "From": PHONE})
    assert response.status_code == 200
