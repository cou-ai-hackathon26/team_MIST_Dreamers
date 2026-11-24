"""POST /api/v1/chat and the history endpoints, end to end with the stub engine (in-memory DB)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain import messages_bn
from app.main import create_app

PHONE = "01712345678"


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None, database_url="sqlite://", phone_hash_salt="test-salt", agent_engine="stub"
    )
    with TestClient(create_app(settings)) as c:
        yield c


def ask(client: TestClient, message: str = "বয়স্ক ভাতা", phone: str = PHONE):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/chat", json={"phone": phone, "message": message})


# ---------------------------------------------------------------- chat


def test_chat_returns_the_srs_response_shape(client: TestClient) -> None:
    r = ask(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "conversation_id", "status", "service", "confidence", "router", "speech_text", "display_text",
        "checklist", "citations", "follow_up_question", "latency_ms",
        "mode", "situation", "services", "checklists", "conflicts",  # sprint additions (additive)
    }  # fmt: skip
    assert body["mode"] == "single" and body["situation"] is None and body["conflicts"] == []
    assert body["status"] == "answered"
    assert body["service"]["id"] == "old_age_allowance"
    assert body["service"]["name_bn"] == "বয়স্ক ভাতা"
    assert body["checklist"]["fee"] == "বিনামূল্যে"
    assert len(body["citations"]) >= 1
    assert body["latency_ms"] >= 0


def test_same_phone_keeps_the_same_conversation(client: TestClient) -> None:
    first = ask(client).json()["conversation_id"]
    assert ask(client, phone="+8801712345678").json()["conversation_id"] == first  # other format, same person


@pytest.mark.parametrize("phone", ["12345", "01212345678", ""])
def test_invalid_phone_gives_bangla_error(client: TestClient, phone: str) -> None:
    r = ask(client, phone=phone)
    assert r.status_code == 422
    assert r.json()["error"]["message_bn"] == messages_bn.INVALID_PHONE


@pytest.mark.parametrize("message", ["", "    ", "ক" * 501])
def test_empty_or_too_long_message_is_a_bad_request(client: TestClient, message: str) -> None:
    r = ask(client, message=message)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BAD_REQUEST"


def test_voice_channel_is_not_accepted_on_the_app_endpoint(client: TestClient) -> None:
    r = client.post("/api/v1/chat", json={"phone": PHONE, "message": "ভাতা", "channel": "voice"})
    assert r.status_code == 422


# ---------------------------------------------------------------- history


def test_history_shows_messages_and_checklist(client: TestClient) -> None:
    ask(client, "বয়স্ক ভাতা কী?")
    r = client.get(f"/api/v1/conversations/{PHONE}")
    assert r.status_code == 200
    body = r.json()
    assert body["phone"] == "+8801712345678"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["text"] == "বয়স্ক ভাতা কী?"
    assert body["messages"][1]["status"] == "answered"
    assert len(body["checklists"]) == 1
    assert body["checklists"][0]["checklist"]["who"].startswith("পুরুষ ৬৫+")
    assert body["checklists"][0]["sms_sent"] is False


def test_history_works_with_any_phone_format(client: TestClient) -> None:
    ask(client)
    assert len(client.get("/api/v1/conversations/+8801712345678").json()["messages"]) == 2


def test_empty_history_for_a_new_number(client: TestClient) -> None:
    body = client.get("/api/v1/conversations/01999999999").json()
    assert body["messages"] == [] and body["checklists"] == []


def test_history_limit_is_validated(client: TestClient) -> None:
    assert client.get(f"/api/v1/conversations/{PHONE}?limit=0").status_code == 422
    assert client.get(f"/api/v1/conversations/{PHONE}?limit=500").status_code == 422


def test_invalid_phone_in_history_gives_bangla_error(client: TestClient) -> None:
    r = client.get("/api/v1/conversations/abc")
    assert r.status_code == 422
    assert r.json()["error"]["message_bn"] == messages_bn.INVALID_PHONE


def test_delete_removes_messages_and_checklists(client: TestClient) -> None:
    ask(client)
    assert client.delete(f"/api/v1/conversations/{PHONE}").json() == {"deleted": True}
    body = client.get(f"/api/v1/conversations/{PHONE}").json()
    assert body["messages"] == [] and body["checklists"] == []
    assert client.delete(f"/api/v1/conversations/{PHONE}").json() == {"deleted": False}


def test_delete_keeps_other_peoples_history(client: TestClient) -> None:
    ask(client, phone=PHONE)
    ask(client, phone="01812345678")
    client.delete(f"/api/v1/conversations/{PHONE}")
    assert len(client.get("/api/v1/conversations/01812345678").json()["messages"]) == 2
