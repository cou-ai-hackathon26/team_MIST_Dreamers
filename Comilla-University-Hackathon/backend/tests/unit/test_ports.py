import dataclasses

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
from app.application.ports.retrieval import Embedder, Passage, Retriever
from app.domain.value_objects import PhoneNumber

ALL_PORTS = [
    ServiceClassifier, Embedder, Retriever, LLM, AnswerEngine, SmsSender, CallPlacer, TextToSpeech,
    ConversationRepo, ChecklistRepo, QuestionLogRepo, CallRepo, ClusterRepo, AnswerCache,
    Clusterer, BackgroundRunner,
]  # fmt: skip


@pytest.mark.parametrize("port", ALL_PORTS, ids=lambda p: p.__name__)
def test_every_port_is_a_runtime_checkable_protocol(port: type) -> None:
    assert getattr(port, "_is_protocol", False), f"{port.__name__} is not a Protocol"
    assert getattr(port, "_is_runtime_protocol", False), f"{port.__name__} is not @runtime_checkable"


class GoodSms:
    def send(self, phone: PhoneNumber, text: str) -> bool:
        return True


class WrongSms:
    def deliver(self, phone: PhoneNumber, text: str) -> bool:  # wrong method name
        return True


def test_a_class_with_the_right_methods_fits_the_port() -> None:
    assert isinstance(GoodSms(), SmsSender)


def test_a_class_with_the_wrong_methods_does_not_fit() -> None:
    assert not isinstance(WrongSms(), SmsSender)


def test_passage_is_frozen() -> None:
    p = Passage("old_age_allowance-001", "old_age_allowance", "শিরোনাম", "https://x", "লেখা", 0.9)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.score = 0.1  # type: ignore[misc]
