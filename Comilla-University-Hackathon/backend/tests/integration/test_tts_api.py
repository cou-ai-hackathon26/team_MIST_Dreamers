"""POST /api/v1/tts end to end with a fake speech service (FR-APP-04, SRS 8). No network."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain import messages_bn
from app.infrastructure.tts.gtts_tts import TtsFailed
from app.main import create_app
from tests.fakes import FakeTts


@pytest.fixture
def client() -> Iterator[TestClient]:
    no_store = Path(__file__).parent / "no_store"  # never created
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        chroma_dir=no_store,
        tfidf_model_path=no_store / "r.joblib",
        agent_engine="stub",
        sms_backend="console",
    )
    with TestClient(create_app(settings)) as test_client:
        test_client.app.state.container.__dict__["tts"] = FakeTts()
        yield test_client


def test_returns_mp3(client: TestClient) -> None:
    response = client.post("/api/v1/tts", json={"text": "বয়স্ক ভাতা"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"ID3fake-mp3:" + "বয়স্ক ভাতা".encode()


@pytest.mark.parametrize("text", ["", "   ", "ক" * 2001], ids=["empty", "blank", "too-long"])
def test_bad_text_gets_422(client: TestClient, text: str) -> None:
    response = client.post("/api/v1/tts", json={"text": text})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_speech_service_down_gives_the_bangla_error(client: TestClient) -> None:
    class DownTts:
        def synthesize(self, text: str) -> bytes:
            raise TtsFailed("speech service failed")

    client.app.state.container.__dict__["tts"] = DownTts()
    client.app.state.container.__dict__.pop("synthesize_speech", None)
    response = client.post("/api/v1/tts", json={"text": "হ্যালো"})
    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "TTS_FAILED",
        "message_bn": messages_bn.ERROR,
        "message_en": "speech service failed",
    }
