"""Admin login API and session tokens on every admin route (FR-ADM-05, hardened)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

NO_DIR = Path(__file__).parent / "no_such_dir"
PASSWORD = "s3cret-admin-password"
ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/stats"),
    ("GET", "/api/v1/admin/questions"),
    ("GET", "/api/v1/admin/clusters"),
]


def make_client(admin_token: str = PASSWORD, app_env: str = "dev") -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        chroma_dir=NO_DIR,
        admin_token=admin_token,  # type: ignore[arg-type]
        app_env=app_env,  # type: ignore[arg-type]
    )
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield from make_client()


def login(client: TestClient, password: str = PASSWORD):
    return client.post("/api/v1/admin/login", json={"password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_a_session_token_not_the_password(client: TestClient) -> None:
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"token", "expires_at"}
    assert PASSWORD not in r.text
    assert r.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_every_admin_route_needs_a_login(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, headers=bearer("123.forged")).status_code == 401
    token = login(client).json()["token"]
    ok = client.request(method, path, headers=bearer(token))
    assert ok.status_code == 200
    assert ok.headers["Cache-Control"] == "no-store"


def test_rebuild_clusters_also_needs_a_login(client: TestClient) -> None:
    assert client.post("/api/v1/admin/clusters/rebuild").status_code == 401


def test_the_password_header_still_works_for_swagger(client: TestClient) -> None:
    assert client.get("/api/v1/admin/stats", headers={"X-Admin-Token": PASSWORD}).status_code == 200
    assert client.get("/api/v1/admin/stats", headers={"X-Admin-Token": "wrong"}).status_code == 401


def test_wrong_password_then_too_many_tries(client: TestClient) -> None:
    for _ in range(5):
        r = login(client, "guess")
        assert r.status_code == 401 and r.json()["error"]["code"] == "HTTP_ERROR"
    blocked = login(client)  # the right password must wait too
    assert blocked.status_code == 429
    assert "Try again" in blocked.json()["error"]["message_en"]


def test_bad_login_body_is_a_bad_request(client: TestClient) -> None:
    assert client.post("/api/v1/admin/login", json={}).status_code == 422
    assert client.post("/api/v1/admin/login", json={"password": "x" * 501}).status_code == 422


@pytest.mark.parametrize("app_env", ["dev", "demo"])
def test_without_admin_token_nobody_gets_in(app_env: str) -> None:
    gen = make_client(admin_token="", app_env=app_env)
    client = next(gen)
    try:
        assert client.get("/api/v1/admin/stats").status_code == 503
        assert client.get("/api/v1/admin/clusters").status_code == 503
        assert client.get("/api/v1/admin/stats", headers={"X-Admin-Token": ""}).status_code == 503
        for password in ["", "anything"]:
            assert login(client, password).status_code == 503
    finally:
        gen.close()


def test_a_password_with_special_characters_works() -> None:
    special = "example-12345;pass'word"  # made-up test password with ; and ' inside
    gen = make_client(admin_token=special)
    client = next(gen)
    try:
        assert login(client, "example-12345").status_code == 401
        token = login(client, special).json()["token"]
        assert client.get("/api/v1/admin/stats", headers=bearer(token)).status_code == 200
    finally:
        gen.close()
