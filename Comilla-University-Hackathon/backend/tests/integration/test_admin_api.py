"""Admin API: /api/v1/admin/stats, /api/v1/admin/questions and the admin token (D2-R1: FR-ADM-01, 02, 05)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.entities import QuestionLog
from app.domain.value_objects import AnswerStatus, Channel
from app.main import create_app

NO_DIR = Path(__file__).parent / "no_such_dir"
TEST_ADMIN = "test-admin-password"


def app_client(admin_token: str = "") -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        chroma_dir=NO_DIR,
        admin_token=admin_token,  # type: ignore[arg-type]
    )
    with TestClient(create_app(settings)) as client:
        container = client.app.state.container  # type: ignore[attr-defined]
        now = datetime.now(UTC)
        rows = [
            ("বয়স্ক ভাতা পাবো?", AnswerStatus.ANSWERED, "old_age_allowance", Channel.VOICE, 3000),
            ("এনআইডি নামের বানান ভুল", AnswerStatus.ANSWERED, "nid_correction", Channel.APP, 5000),
            ("জমি নিয়ে প্রতিবেশীর সাথে ঝামেলা", AnswerStatus.FALLBACK, "other", Channel.VOICE, 1000),
        ]
        for i, (text, status, service, channel, latency) in enumerate(rows):
            container.question_logs.add(
                QuestionLog(
                    phone_hash="private-hash",
                    channel=channel,
                    text=text,
                    status=status,
                    service_id=service,
                    latency_ms=latency,
                    created_at=now - timedelta(minutes=10 - i),
                )  # fmt: skip
            )
        yield client


@pytest.fixture
def client() -> Iterator[TestClient]:
    for c in app_client(admin_token=TEST_ADMIN):
        c.headers["X-Admin-Token"] = TEST_ADMIN  # signed in for every request of these tests
        yield c


def test_stats(client: TestClient) -> None:
    r = client.get("/api/v1/admin/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_questions"] == 3
    assert (body["answered_pct"], body["fallback_pct"]) == (66.7, 33.3)
    assert body["avg_latency_ms"] == 3000
    assert body["calls_today"] == 0
    assert body["by_channel"] == {"voice": 2, "app": 1}
    assert body["by_status"] == {"answered": 2, "follow_up": 0, "fallback": 1, "error": 0}
    services = {s["id"]: s for s in body["by_service"]}
    assert len(services) == 9  # 8 services + other, zeros included
    assert services["nid_correction"] == {"id": "nid_correction", "name_bn": "এনআইডি সংশোধন", "count": 1}


def test_questions_newest_first_without_phone_data(client: TestClient) -> None:
    rows = client.get("/api/v1/admin/questions").json()["questions"]
    assert [q["text"] for q in rows][0] == "জমি নিয়ে প্রতিবেশীর সাথে ঝামেলা"
    assert set(rows[0]) == {
        "text", "status", "channel", "service_id", "service_name_bn",
        "router", "latency_ms", "is_demo", "created_at",
    }  # fmt: skip
    assert "private-hash" not in client.get("/api/v1/admin/questions").text


def test_unanswered_questions(client: TestClient) -> None:
    rows = client.get("/api/v1/admin/questions", params={"status": "fallback"}).json()["questions"]
    assert [(q["text"], q["channel"]) for q in rows] == [("জমি নিয়ে প্রতিবেশীর সাথে ঝামেলা", "voice")]


def test_limit_and_bad_input(client: TestClient) -> None:
    assert len(client.get("/api/v1/admin/questions", params={"limit": 2}).json()["questions"]) == 2
    bad_status = client.get("/api/v1/admin/questions", params={"status": "nope"})
    assert bad_status.status_code == 422 and bad_status.json()["error"]["code"] == "BAD_REQUEST"
    assert client.get("/api/v1/admin/questions", params={"limit": 0}).status_code == 422


def test_numbers_change_after_a_new_question(client: TestClient) -> None:
    before = client.get("/api/v1/admin/stats").json()["total_questions"]
    client.app.state.container.question_logs.add(  # type: ignore[attr-defined]
        QuestionLog(phone_hash="h", channel=Channel.APP, text="নতুন", status=AnswerStatus.ANSWERED)
    )
    assert client.get("/api/v1/admin/stats").json()["total_questions"] == before + 1


def test_admin_token_is_required_when_set() -> None:
    gen = app_client(admin_token="s3cret")
    client = next(gen)
    try:
        for path in ["/api/v1/admin/stats", "/api/v1/admin/questions"]:
            missing = client.get(path)
            assert missing.status_code == 401 and missing.json()["error"]["code"] == "HTTP_ERROR"
            assert client.get(path, headers={"X-Admin-Token": "wrong"}).status_code == 401
            assert client.get(path, headers={"X-Admin-Token": "s3cret"}).status_code == 200
    finally:
        gen.close()


def test_no_token_configured_means_closed() -> None:
    gen = app_client(admin_token="")
    client = next(gen)
    try:
        assert client.get("/api/v1/admin/stats").status_code == 503
        assert client.get("/api/v1/admin/questions").status_code == 503
    finally:
        gen.close()
