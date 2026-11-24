"""D2-A3: a phone call with the real AskQuestion, SMS and logs; crash safety; CORS. No network.

The stub engine answers every question with the Old Age Allowance checklist, so the SMS rules
(FR-SMS-01, 02) can be checked through the voice webhooks: SMS line spoken once per service per
call, SMS sent to the citizen (also on our call-backs, where the citizen is "To").
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.domain import messages_bn
from app.main import create_app
from tests.fakes import FakeRunner, FakeSms

PHONE = "+8801712345678"
TWILIO = "+15005550006"
FRONTEND = "http://localhost:5173"

MakeClient = Callable[..., TestClient]


@pytest.fixture
def make_client() -> Iterator[MakeClient]:
    clients: list[TestClient] = []

    def make(**overrides: object) -> TestClient:
        no_store = Path(__file__).parent / "no_store"  # never created
        values: dict[str, object] = {
            "database_url": "sqlite://",
            "chroma_dir": no_store,
            "tfidf_model_path": no_store / "r.joblib",
            "agent_engine": "stub",
            "sms_backend": "console",
            "public_url": "https://example.ngrok-free.dev",
            "frontend_origins": FRONTEND,
            **overrides,
        }
        client = TestClient(create_app(Settings(_env_file=None, **values)))
        client.__enter__()
        container = client.app.state.container
        container.__dict__["sms"] = FakeSms()
        container.__dict__["runner"] = FakeRunner()  # SMS and voice turns run inline
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: MakeClient) -> TestClient:
    return make_client()


def turn(client: TestClient, speech: str, call_sid: str = "CA1", outbound: bool = False) -> str:
    form = {"CallSid": call_sid, "SpeechResult": speech}
    form |= {"From": TWILIO, "To": PHONE, "Direction": "outbound-api"} if outbound else {
        "From": PHONE, "To": TWILIO, "Direction": "inbound"}  # fmt: skip
    response = client.post("/voice/respond", data=form)
    assert response.status_code == 200
    return response.text


def sent(client: TestClient) -> list[str]:
    return [phone.e164 for phone, _ in client.app.state.container.sms.sent]


def logged_channels(client: TestClient) -> list[str]:
    with client.app.state.container.session_factory() as session:
        return list(session.execute(text("SELECT channel FROM question_logs")).scalars())


# ---------------------------------------------------------------- voice + SMS (FR-SMS-01, 02)


def test_checklist_answer_sends_the_sms_and_says_so(client: TestClient) -> None:
    xml = turn(client, "বয়স্ক ভাতা পেতে কী লাগে?")
    assert messages_bn.SMS_SENT in xml
    assert xml.count(messages_bn.SMS_SENT) == 1  # never twice in one answer
    assert sent(client) == [PHONE]


def test_same_service_again_in_the_call_sends_no_second_sms(client: TestClient) -> None:
    turn(client, "বয়স্ক ভাতা পেতে কী লাগে?")
    xml = turn(client, "আর কোথায় জমা দেবো?")
    assert messages_bn.SMS_SENT not in xml
    assert sent(client) == [PHONE]


def test_call_back_sends_the_sms_to_the_citizen_not_to_twilio(client: TestClient) -> None:
    turn(client, "বয়স্ক ভাতা পেতে কী লাগে?", call_sid="CA_out", outbound=True)
    assert sent(client) == [PHONE]


def test_failed_sms_does_not_break_the_call(client: TestClient) -> None:
    client.app.state.container.sms.succeed = False
    xml = turn(client, "বয়স্ক ভাতা পেতে কী লাগে?")
    assert "<Gather" in xml  # the call goes on


def test_voice_questions_are_logged_for_the_dashboard(client: TestClient) -> None:
    turn(client, "বয়স্ক ভাতা পেতে কী লাগে?")
    client.post("/api/v1/chat", json={"phone": PHONE, "message": "বিধবা ভাতা পেতে কী লাগে?"})
    assert sorted(logged_channels(client)) == ["app", "voice"]


# ---------------------------------------------------------------- crash safety (NFR-REL-01)


class Broken:
    def start(self, *args: object) -> object:
        raise RuntimeError("thread pool is gone")

    def result(self, job_id: str) -> object:
        raise RuntimeError("thread pool is gone")


@pytest.mark.parametrize(
    ("path", "form"),
    [
        ("/voice/respond", {"CallSid": "CA1", "SpeechResult": "বয়স্ক ভাতা", "From": PHONE}),
        ("/voice/result?job=abc", {"CallSid": "CA1"}),
    ],
    ids=["respond", "result"],
)
def test_unexpected_crash_speaks_error_and_keeps_the_call(
    client: TestClient, path: str, form: dict[str, str]
) -> None:
    client.app.state.container.__dict__["voice_answers"] = Broken()
    response = client.post(path, data=form)
    assert response.status_code == 200  # never a 500: Twilio would hang up
    assert messages_bn.ERROR in response.text
    assert "<Gather" in response.text


def test_webhook_with_almost_no_fields_still_gets_twiml(client: TestClient) -> None:
    for path in ("/voice/incoming", "/voice/start", "/voice/respond", "/voice/result"):
        response = client.post(path, data={})
        assert response.status_code == 200, path
        assert response.text.startswith("<?xml"), path


# ---------------------------------------------------------------- CORS (NFR-SEC-02)


def test_cors_allows_our_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/v1/tts",
        headers={"Origin": FRONTEND, "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "content-type"},
    )  # fmt: skip
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND


def test_cors_refuses_other_sites(client: TestClient) -> None:
    response = client.options(
        "/api/v1/callback",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_accepts_several_origins(make_client: MakeClient) -> None:
    deployed = "https://ekcall.vercel.app"
    client = make_client(frontend_origins=f"{FRONTEND}, {deployed}")
    response = client.get("/health", headers={"Origin": deployed})
    assert response.headers["access-control-allow-origin"] == deployed
