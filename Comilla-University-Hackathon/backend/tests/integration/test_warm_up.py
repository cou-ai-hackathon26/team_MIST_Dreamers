"""Model warm-up at startup (D2-T4): runs in the background and never breaks the app."""

from pathlib import Path

from app.config import Settings
from app.container import Container
from app.domain.errors import ClassifierUnavailable
from tests.fakes import FakeClassifier, FakeRetriever

NO_DIR = Path(__file__).parent / "no_such_dir"


def container_for(preload: bool) -> Container:
    return Container(
        Settings(_env_file=None, database_url="sqlite://", chroma_dir=NO_DIR, preload_models=preload)
    )


def test_warm_up_is_off_unless_preload_models_is_set() -> None:
    c = container_for(preload=False)
    assert c.warm_up() is None
    assert "classifier" not in c.__dict__ and "retriever" not in c.__dict__  # nothing was loaded


def test_warm_up_loads_router_search_and_agent_in_a_background_thread() -> None:
    c = container_for(preload=True)
    classifier, retriever = FakeClassifier({"old_age_allowance": 1.0}), FakeRetriever()
    c.__dict__.update(classifier=classifier, retriever=retriever)  # replace the cached adapters
    thread = c.warm_up()
    assert thread is not None and thread.daemon
    thread.join(timeout=30)
    assert classifier.texts == ["বয়স্ক ভাতা"]
    assert len(retriever.searches) == 1
    assert "answer_engine" in c.__dict__  # the agent graph is compiled


def test_a_missing_model_does_not_stop_the_rest_of_the_warm_up() -> None:
    class Missing(FakeClassifier):
        def classify(self, text: str) -> list[tuple[str, float]]:
            raise ClassifierUnavailable("no model file")

    c = container_for(preload=True)
    retriever = FakeRetriever()
    c.__dict__.update(classifier=Missing({}), retriever=retriever)
    c._preload()  # same work, run directly
    assert len(retriever.searches) == 1 and "answer_engine" in c.__dict__
