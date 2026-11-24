from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.application.ports.llm import LLM
from app.application.ports.repositories import (
    AnswerCache,
    CallRepo,
    ChecklistRepo,
    ClusterRepo,
    ConversationRepo,
    QuestionLogRepo,
)
from app.application.ports.retrieval import Embedder, Retriever
from app.config import Settings
from app.container import EMPTY, NOT_CONFIGURED, Container
from app.domain.value_objects import PhoneNumber
from app.infrastructure.llm.gemini_llm import GeminiLLM
from app.infrastructure.llm.ollama_llm import OllamaLLM
from app.infrastructure.llm.routed_llm import RoutedLLM
from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever
from app.infrastructure.retrieval.chunker import Chunk
from tests.fakes import FakeEmbedder

NO_CHROMA = Path(__file__).parent / "no_such_chroma_dir"
NO_ROUTER = Path(__file__).parent / "no_such_router.joblib"


def container_for(database_url: str = "sqlite://", chroma_dir: Path = NO_CHROMA) -> Container:
    return Container(
        Settings(_env_file=None, database_url=database_url, chroma_dir=chroma_dir, tfidf_model_path=NO_ROUTER)
    )


def test_creating_a_container_builds_nothing_yet() -> None:
    c = container_for("sqlite:///Z:/this/path/does/not/exist/db.sqlite")
    assert "engine" not in c.__dict__  # lazy: no connection until something needs it
    c.close()  # closing an unused container is fine


@pytest.mark.parametrize(
    ("attr", "port"),
    [
        ("conversations", ConversationRepo),
        ("checklists", ChecklistRepo),
        ("question_logs", QuestionLogRepo),
        ("calls", CallRepo),
        ("clusters", ClusterRepo),
        ("answer_cache", AnswerCache),
    ],
)
def test_each_repository_fits_its_port_and_is_built_once(attr: str, port: type) -> None:
    c = container_for()
    repo = getattr(c, attr)
    assert isinstance(repo, port)
    assert getattr(c, attr) is repo  # same object every time


def test_init_database_creates_the_tables_and_repos_work() -> None:
    c = container_for()
    c.init_database()
    assert "conversations" in inspect(c.engine).get_table_names()
    phone = PhoneNumber.parse("01712345678")
    assert c.conversations.get_or_create(phone) == c.conversations.get_or_create(phone)


def test_health_reports_ok_db_and_unbuilt_parts() -> None:
    health = container_for().health()
    assert health == {
        "status": "ok",
        "db": "ok",
        "llm": NOT_CONFIGURED,
        "vector_db": EMPTY,
        "router": NOT_CONFIGURED,
    }
    assert not NO_CHROMA.exists()  # asking about health must not create the store folder


def test_retriever_is_lazy_and_fits_its_port() -> None:
    c = container_for()
    assert isinstance(c.retriever, Retriever)
    assert isinstance(c.embedder, Embedder)
    assert c.embedder._model is None  # the 470 MB model is not loaded until a search needs it


@pytest.mark.parametrize(
    ("backend", "kind"), [("gemini", GeminiLLM), ("ollama", OllamaLLM), ("hybrid", RoutedLLM)]
)
def test_llm_is_chosen_from_llm_backend(backend: str, kind: type) -> None:
    c = Container(Settings(_env_file=None, llm_backend=backend))
    assert isinstance(c.llm, kind)
    assert isinstance(c.llm, LLM)
    assert c.llm is c.llm  # built once
    c.close()


def test_health_reports_ok_vector_db_after_ingest(tmp_path: Path) -> None:
    store = tmp_path / "chroma"
    chunk = Chunk("old_age_allowance-001", "old_age_allowance", "t", "https://x.gov.bd", "h", "বয়স ৬৫")
    ChromaRetriever(store, FakeEmbedder()).rebuild([chunk])
    assert container_for(chroma_dir=store).health()["vector_db"] == "ok"


def test_health_reports_a_broken_database_instead_of_crashing(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("x")  # a FILE where the database folder should be
    health = container_for(f"sqlite:///{(blocker / 'db.sqlite').as_posix()}").health()
    assert health["db"] == "error"
    assert health["status"] == "error"
