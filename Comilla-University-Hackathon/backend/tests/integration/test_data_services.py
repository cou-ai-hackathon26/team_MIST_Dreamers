"""The data services from docker-compose.yml: Chroma server mode and Postgres.

The first tests need nothing running. The live ones run only when the services are up
(`docker compose up -d` in backend/) and skip otherwise, e.g. in CI:
- Chroma: the server on localhost:8001,
- Postgres: set EKCALL_TEST_DATABASE_URL to a database the test may fill, never the real one, e.g.
  postgresql+psycopg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:5432/ekcall_test
"""

import os
import socket
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.container import EMPTY, Container
from app.domain.value_objects import PhoneNumber
from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever
from tests.integration.test_chroma_retriever import CHUNKS, WordEmbedder

NO_DIR = Path(__file__).parent / "no_such_dir"
CHROMA_HOST, CHROMA_PORT = "localhost", 8001
TEST_DB = os.environ.get("EKCALL_TEST_DATABASE_URL", "")


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "_env_file": None,
        "database_url": "sqlite://",
        "chroma_dir": NO_DIR,
        "tfidf_model_path": NO_DIR / "r.joblib",
    }
    return Settings(**(base | overrides))


def chroma_is_up() -> bool:
    try:
        with socket.create_connection((CHROMA_HOST, CHROMA_PORT), timeout=0.5):
            return True
    except OSError:
        return False


class CountingStore:
    def __init__(self, n: int) -> None:
        self.n = n

    def count(self) -> int:
        return self.n


# ------------------------------------------------------------------ no services needed


def test_file_mode_is_still_the_default() -> None:
    assert Settings(_env_file=None).chroma_host == ""


def test_server_mode_uses_the_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import chromadb

    seen: dict[str, Any] = {}
    monkeypatch.setattr(chromadb, "HttpClient", lambda **kw: seen.update(kw) or "http-client")
    r = ChromaRetriever(NO_DIR, WordEmbedder(), host="chroma.local", port=1234)
    assert r.client == "http-client"
    assert (seen["host"], seen["port"]) == ("chroma.local", 1234)
    assert not NO_DIR.exists()  # no local folder is created in server mode


def test_container_passes_the_chroma_server_settings() -> None:
    r = Container(settings(chroma_host="chroma.local", chroma_port=1234)).retriever
    assert (r._host, r._port) == ("chroma.local", 1234)


def test_health_in_server_mode_does_not_need_the_local_folder() -> None:
    c = Container(settings(chroma_host="chroma.local"))
    c.__dict__["retriever"] = CountingStore(5)  # stands in for the server
    assert c.check_vector_db() == "ok"
    c.__dict__["retriever"] = CountingStore(0)
    assert c.check_vector_db() == EMPTY


# ------------------------------------------------------------------ live services


@pytest.mark.skipif(not chroma_is_up(), reason="Chroma server not running (docker compose up -d)")
def test_chroma_server_stores_and_searches() -> None:
    collection = f"pytest_{uuid.uuid4().hex[:8]}"  # never the real ek_call_docs collection
    r = ChromaRetriever(
        NO_DIR, WordEmbedder(), min_score=0.5, collection=collection, host=CHROMA_HOST, port=CHROMA_PORT
    )
    try:
        assert r.rebuild(CHUNKS) == len(CHUNKS)
        assert r.count() == len(CHUNKS)
        hits = r.search("পাসপোর্ট ফি ৪০২৫ টাকা", "e_passport", k=1)
        assert hits[0].chunk_id == "e_passport-001"
    finally:
        r.client.delete_collection(collection)


@pytest.mark.skipif(not TEST_DB, reason="set EKCALL_TEST_DATABASE_URL to test Postgres")
def test_postgres_tables_and_a_conversation_round_trip() -> None:
    from app.infrastructure.db.models import Base

    c = Container(settings(database_url=TEST_DB))
    try:
        Base.metadata.drop_all(c.engine)  # a clean test database each run
        c.init_database()
        assert c.check_db() == "ok"
        phone = PhoneNumber.parse("01712345678")
        conversation_id = c.conversations.get_or_create(phone)
        assert c.conversations.get_or_create(phone) == conversation_id
    finally:
        c.close()
