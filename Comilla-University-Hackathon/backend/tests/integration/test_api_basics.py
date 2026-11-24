"""The running API: /health, the error format, CORS (in-memory database, no network)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.domain import messages_bn
from app.domain.errors import InvalidPhone, LLMUnavailable, NotFound, RateLimited
from app.main import create_app


def build_app() -> FastAPI:
    no_store = Path(__file__).parent / "no_store"  # never created: vector_db reports "empty"
    # Gemini with no keys: llm reports "not_configured" without any network call.
    settings = Settings(
        _env_file=None, database_url="sqlite://", chroma_dir=no_store, tfidf_model_path=no_store / "r.joblib"
    )
    app = create_app(settings)

    # Test-only routes that fail on purpose, to check the error format.
    class Body(BaseModel):
        phone: str

    errors = {"phone": InvalidPhone, "missing": NotFound, "busy": RateLimited, "llm": LLMUnavailable}

    @app.get("/test/raise/{kind}")
    def raise_error(kind: str) -> None:
        if kind == "crash":
            raise RuntimeError("secret internal detail")
        raise errors[kind]("boom")

    @app.post("/test/body")
    def needs_body(body: Body) -> dict[str, str]:
        return {"phone": body.phone}

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(build_app(), raise_server_exceptions=False) as c:  # `with` runs startup/shutdown
        yield c


def test_health_is_ok_with_db_ready(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok", "db": "ok", "llm": "not_configured", "vector_db": "empty",
        "router": "not_configured",
    }  # fmt: skip


@pytest.mark.parametrize(
    ("kind", "status", "code", "message_bn"),
    [
        ("phone", 422, "INVALID_PHONE", messages_bn.INVALID_PHONE),
        ("missing", 404, "NOT_FOUND", messages_bn.NOT_FOUND),
        ("busy", 429, "RATE_LIMITED", messages_bn.RATE_LIMITED),
        ("llm", 503, "LLM_UNAVAILABLE", messages_bn.ERROR),
        ("crash", 500, "INTERNAL_ERROR", messages_bn.ERROR),
    ],
)
def test_errors_use_the_srs_format_in_bangla(
    client: TestClient, kind: str, status: int, code: str, message_bn: str
) -> None:
    r = client.get(f"/test/raise/{kind}")
    assert r.status_code == status
    error = r.json()["error"]
    assert error["code"] == code
    assert error["message_bn"] == message_bn
    assert error["message_en"]


def test_crash_details_are_never_shown_to_the_user(client: TestClient) -> None:
    assert "secret internal detail" not in client.get("/test/raise/crash").text


def test_missing_field_gives_bangla_bad_request(client: TestClient) -> None:
    r = client.post("/test/body", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BAD_REQUEST"
    assert r.json()["error"]["message_bn"] == messages_bn.BAD_REQUEST


def test_unknown_address_gives_bangla_not_found(client: TestClient) -> None:
    r = client.get("/no/such/page")
    assert r.status_code == 404
    assert r.json()["error"]["message_bn"] == messages_bn.NOT_FOUND


def test_bangla_is_returned_as_readable_utf8(client: TestClient) -> None:
    r = client.get("/test/raise/missing")
    assert "charset" not in r.headers["content-type"] or "utf-8" in r.headers["content-type"]
    assert messages_bn.NOT_FOUND in r.content.decode("utf-8")


def test_cors_allows_the_frontend_only(client: TestClient) -> None:
    def preflight(origin: str) -> str | None:
        r = client.options(
            "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        return r.headers.get("access-control-allow-origin")

    assert preflight("http://localhost:5173") == "http://localhost:5173"
    assert preflight("https://evil.example.com") is None


def test_swagger_docs_are_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]
