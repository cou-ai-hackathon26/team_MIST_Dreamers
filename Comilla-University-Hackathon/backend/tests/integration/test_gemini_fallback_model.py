"""GEMINI_MODEL_FALLBACK: when the model is overloaded (503) the same request goes once to another model."""

from typing import Any

import pytest

from app.application.ports.llm import ModelRole
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.gemini_llm import GeminiLLM
from tests.integration.test_llm_adapters import SCHEMA, FakeModels, client_error, server_error


def gemini(script: dict[str, list[Any]], fallback: str) -> tuple[GeminiLLM, list[tuple[str, str, Any]]]:
    calls: list[tuple[str, str, Any]] = []

    class Client:
        def __init__(self, key: str) -> None:
            self.models = FakeModels(key, script, calls)

    llm = GeminiLLM(
        ["k1"],
        "main-model",
        "fast-model",
        client_factory=Client,
        sleep=lambda _: None,
        fallback_model=fallback,
    )
    return llm, calls


def test_overloaded_model_falls_back_to_the_second_model() -> None:
    llm, calls = gemini({"k1": [server_error(), server_error(), '{"x": "ok"}']}, fallback="backup-model")
    assert llm.generate_json("p", SCHEMA, role=ModelRole.MAIN) == {"x": "ok"}
    assert [model for _, model, _ in calls] == ["main-model", "main-model", "backup-model"]


def test_without_a_fallback_model_the_error_reaches_the_caller() -> None:
    llm, calls = gemini({"k1": [server_error(), server_error()]}, fallback="")
    with pytest.raises(LLMUnavailable):
        llm.generate_json("p", SCHEMA)
    assert len(calls) == 2


def test_a_rejected_request_is_not_sent_to_the_fallback_model() -> None:
    llm, calls = gemini({"k1": [client_error(400, "Invalid JSON payload")]}, fallback="backup-model")
    with pytest.raises(LLMUnavailable):
        llm.generate_json("p", SCHEMA)
    assert [model for _, model, _ in calls] == ["main-model"]


def test_fallback_model_failing_too_gives_llm_unavailable() -> None:
    llm, calls = gemini({"k1": [server_error()] * 4}, fallback="backup-model")
    with pytest.raises(LLMUnavailable):
        llm.generate_json("p", SCHEMA, role=ModelRole.FAST)
    assert [model for _, model, _ in calls] == ["fast-model", "fast-model", "backup-model", "backup-model"]
