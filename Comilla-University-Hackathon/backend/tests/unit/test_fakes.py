import pytest

from app.application.ports.background import BackgroundRunner
from app.application.ports.classifier import ServiceClassifier
from app.application.ports.clustering import Clusterer
from app.application.ports.engine import AnswerEngine
from app.application.ports.llm import LLM
from app.application.ports.messaging import CallPlacer, SmsSender, TextToSpeech
from app.application.ports.repositories import (
    AnswerCache,
    CallRepo,
    ChecklistRepo,
    ClusterRepo,
    ConversationRepo,
    QuestionLogRepo,
)
from app.application.ports.retrieval import Embedder, Retriever
from app.domain.entities import Answer
from app.domain.errors import LLMUnavailable
from app.domain.value_objects import AnswerStatus, PhoneNumber
from tests import fakes

FALLBACK = Answer(status=AnswerStatus.FALLBACK, speech_text="x", display_text="x")

PAIRS = [
    (fakes.FakeLLM(), LLM),
    (fakes.FakeClassifier({"other": 1.0}), ServiceClassifier),
    (fakes.FakeEmbedder(), Embedder),
    (fakes.FakeRetriever(), Retriever),
    (fakes.FakeEngine(FALLBACK), AnswerEngine),
    (fakes.FakeClusterer(), Clusterer),
    (fakes.FakeSms(), SmsSender),
    (fakes.FakeCallPlacer(), CallPlacer),
    (fakes.FakeTts(), TextToSpeech),
    (fakes.FakeRunner(), BackgroundRunner),
    (fakes.InMemoryConversationRepo(), ConversationRepo),
    (fakes.InMemoryChecklistRepo(), ChecklistRepo),
    (fakes.InMemoryQuestionLogRepo(), QuestionLogRepo),
    (fakes.InMemoryCallRepo(), CallRepo),
    (fakes.InMemoryClusterRepo(), ClusterRepo),
    (fakes.InMemoryAnswerCache(), AnswerCache),
]


@pytest.mark.parametrize(("fake", "port"), PAIRS, ids=[port.__name__ for _, port in PAIRS])
def test_fake_fits_its_port(fake: object, port: type) -> None:
    assert isinstance(fake, port)


def test_fake_llm_returns_scripted_answers_in_order_and_counts_calls() -> None:
    llm = fakes.FakeLLM(responses=[{"a": 1}, {"b": 2}])
    assert llm.generate_json("p1", {}) == {"a": 1}
    assert llm.generate_json("p2", {}) == {"b": 2}
    assert llm.calls == 2 and llm.prompts == ["p1", "p2"]


def test_fake_llm_can_simulate_an_outage() -> None:
    with pytest.raises(LLMUnavailable):
        fakes.FakeLLM(fail=True).generate_json("p", {})


def test_fake_runner_runs_work_inline() -> None:
    sms, runner = fakes.FakeSms(), fakes.FakeRunner()
    phone = PhoneNumber.parse("01712345678")
    runner.submit(sms.send, phone, "হ্যালো", delay_s=3)
    assert sms.sent == [(phone, "হ্যালো")]
    assert runner.submitted == [("send", 3)]


def test_conversation_repo_keeps_history_per_phone() -> None:
    from app.domain.entities import Message
    from app.domain.value_objects import Channel, Role

    repo = fakes.InMemoryConversationRepo()
    a, b = PhoneNumber.parse("01712345678"), PhoneNumber.parse("01812345678")
    repo.add_message(repo.get_or_create(a), Message(Role.USER, Channel.APP, "প্রশ্ন ক"))
    repo.add_message(repo.get_or_create(b), Message(Role.USER, Channel.APP, "প্রশ্ন খ"))
    assert [m.text for m in repo.recent_messages(a, 6)] == ["প্রশ্ন ক"]
    assert repo.delete_for_phone(a) and repo.recent_messages(a, 6) == []
