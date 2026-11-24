"""LLM adapters without network: Gemini with a fake SDK client, Ollama with httpx.MockTransport."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors

from app.application.ports.llm import LLM, ModelRole
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.common import parse_json_object
from app.infrastructure.llm.gemini_llm import GeminiLLM
from app.infrastructure.llm.ollama_llm import OllamaLLM
from app.infrastructure.llm.routed_llm import RoutedLLM
from tests.fakes import FakeLLM

SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}


def client_error(code: int, message: str) -> genai_errors.ClientError:
    return genai_errors.ClientError(code, {"error": {"code": code, "message": message, "status": "X"}})


def server_error() -> genai_errors.ServerError:
    return genai_errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "X"}})


QUOTA = client_error(429, "Resource has been exhausted")
BAD_KEY = client_error(400, "API key not valid. Please pass a valid API key.")


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeModels:
    def __init__(self, key: str, script: dict[str, list[Any]], log: list[tuple[str, str, dict[str, Any]]]):
        self._key, self._script, self._log = key, script, log

    def generate_content(self, *, model: str, contents: str, config: dict[str, Any]) -> FakeResponse:
        self._log.append((self._key, model, config))
        outcome = self._script[self._key].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)

    def list(self, config: dict[str, Any]) -> list[str]:
        outcome = self._script.get(f"{self._key}:list", ["models/x"])
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def gemini(
    script: dict[str, list[Any]], keys: tuple[str, ...] = ("k1", "k2")
) -> tuple[GeminiLLM, list[tuple[str, str, dict[str, Any]]], list[float]]:
    calls: list[tuple[str, str, dict[str, Any]]] = []
    sleeps: list[float] = []

    class Client:
        def __init__(self, key: str) -> None:
            self.models = FakeModels(key, script, calls)

    llm = GeminiLLM(list(keys), "main-model", "fast-model", client_factory=Client, sleep=sleeps.append)
    return llm, calls, sleeps


# ---------------------------------------------------------------- Gemini


def test_gemini_fits_the_port_and_returns_parsed_json_from_the_right_model() -> None:
    llm, calls, _ = gemini({"k1": ['{"x": "হ্যাঁ"}', '{"x": "না"}']})
    assert isinstance(llm, LLM)
    assert llm.generate_json("প্রশ্ন", SCHEMA, ModelRole.MAIN, temperature=0.1) == {"x": "হ্যাঁ"}
    assert llm.generate_json("প্রশ্ন", SCHEMA, ModelRole.FAST) == {"x": "না"}
    assert [model for _, model, _ in calls] == ["main-model", "fast-model"]
    config = calls[0][2]
    assert config["response_json_schema"] == SCHEMA
    assert config["response_mime_type"] == "application/json"
    assert config["temperature"] == 0.1
    assert llm.stats.calls == 2 and llm.stats.failures == 0


def test_gemini_rate_limited_key_switches_to_the_next_key_and_stays_there() -> None:
    llm, calls, sleeps = gemini({"k1": [QUOTA], "k2": ['{"x": "1"}', '{"x": "2"}']})
    assert llm.generate_json("p", SCHEMA) == {"x": "1"}
    assert llm.generate_json("p", SCHEMA) == {"x": "2"}  # next question starts on the working key
    assert [key for key, _, _ in calls] == ["k1", "k2", "k2"]
    assert sleeps == []


def test_gemini_invalid_first_key_still_works_via_rotation() -> None:
    llm, calls, _ = gemini({"bad": [BAD_KEY], "k1": ['{"x": "ok"}']}, keys=("bad", "k1"))
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert [key for key, _, _ in calls] == ["bad", "k1"]


def test_gemini_all_keys_limited_waits_once_retries_once_then_gives_up() -> None:
    llm, calls, sleeps = gemini({"k1": [QUOTA, QUOTA], "k2": [QUOTA]})
    with pytest.raises(LLMUnavailable, match="rate-limited"):
        llm.generate_json("p", SCHEMA)
    assert sleeps == [1.0]
    assert len(calls) == 3  # k1, k2, then one retry


def test_gemini_server_error_is_retried_once_after_one_second() -> None:
    llm, calls, sleeps = gemini({"k1": [server_error(), '{"x": "ok"}']})
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert sleeps == [1.0]
    assert llm.stats.failures == 1


def test_gemini_two_server_errors_give_llm_unavailable() -> None:
    llm, _, _ = gemini({"k1": [server_error(), server_error()]})
    with pytest.raises(LLMUnavailable, match="not responding"):
        llm.generate_json("p", SCHEMA)


def test_gemini_bad_request_is_not_retried_with_other_keys() -> None:
    llm, calls, sleeps = gemini({"k1": [client_error(400, "Invalid JSON schema")]})
    with pytest.raises(LLMUnavailable, match="HTTP 400"):
        llm.generate_json("p", SCHEMA)
    assert len(calls) == 1 and sleeps == []


def test_gemini_reply_that_is_not_json_gives_llm_unavailable() -> None:
    llm, _, _ = gemini({"k1": ["দুঃখিত, আমি পারছি না"]})
    with pytest.raises(LLMUnavailable, match="valid JSON"):
        llm.generate_json("p", SCHEMA)


def test_gemini_errors_never_contain_a_key() -> None:
    secret = "AIzaSy-very-secret"
    llm, _, _ = gemini({secret: [QUOTA, QUOTA]}, keys=(secret,))
    with pytest.raises(LLMUnavailable) as info:
        llm.generate_json("p", SCHEMA)
    assert secret not in str(info.value)


def test_gemini_without_keys_or_models_is_not_configured() -> None:
    for llm in (GeminiLLM([], "m", "f"), GeminiLLM(["k"], "", "f")):
        assert not llm.configured
        assert llm.check() is False
        with pytest.raises(LLMUnavailable, match="not configured"):
            llm.generate_text("p")


def test_gemini_check_lists_models_and_caches_the_answer_for_60_seconds() -> None:
    now = [100.0]
    script: dict[str, list[Any]] = {"k1:list": ["models/x"]}

    class Client:
        def __init__(self, key: str) -> None:
            self.models = FakeModels(key, script, [])

    llm = GeminiLLM(["k1"], "m", "f", client_factory=Client, clock=lambda: now[0])
    assert llm.check() is True
    script["k1:list"] = RuntimeError("network down")  # type: ignore[assignment]
    now[0] += 30
    assert llm.check() is True  # cached
    now[0] += 31
    assert llm.check() is False  # asked again after 60 s


# ---------------------------------------------------------------- Ollama


def ollama(handler: Callable[[httpx.Request], httpx.Response], model: str = "qwen2.5:7b") -> OllamaLLM:
    client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    return OllamaLLM("http://ollama.test", model, client=client)


def chat_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def test_ollama_sends_the_schema_as_format_and_parses_the_reply() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        seen.append(json.loads(request.content))
        return chat_reply('{"x": "৬৫"}')

    llm = ollama(handler)
    assert isinstance(llm, LLM)
    assert llm.generate_json("প্রশ্ন", SCHEMA, temperature=0.1) == {"x": "৬৫"}
    body = seen[0]
    assert body["format"] == SCHEMA
    assert body["stream"] is False
    assert body["model"] == "qwen2.5:7b"
    assert body["keep_alive"]
    assert body["options"]["temperature"] == 0.1
    assert body["messages"] == [{"role": "user", "content": "প্রশ্ন"}]


def test_ollama_plain_text_has_no_format() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return chat_reply("  উত্তর  ")

    assert ollama(handler).generate_text("প্রশ্ন") == "উত্তর"
    assert "format" not in seen[0]


@pytest.mark.parametrize(
    ("handler", "match"),
    [
        (lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused", request=r)), "not reachable"),
        (lambda r: httpx.Response(404, json={"error": "model not found"}), "HTTP 404"),
        (lambda r: chat_reply("not json at all"), "valid JSON"),
        (lambda r: httpx.Response(200, json={"unexpected": True}), "replied badly"),
    ],
)
def test_ollama_failures_become_llm_unavailable(
    handler: Callable[[httpx.Request], httpx.Response], match: str
) -> None:
    with pytest.raises(LLMUnavailable, match=match):
        ollama(handler).generate_json("p", SCHEMA)


def test_ollama_check_needs_the_model_to_be_downloaded() -> None:
    def tags(names: list[str]) -> Callable[[httpx.Request], httpx.Response]:
        return lambda r: httpx.Response(200, json={"models": [{"name": n} for n in names]})

    assert ollama(tags(["qwen2.5:7b", "llama3:latest"])).check() is True
    assert ollama(tags(["llama3:latest"]), model="llama3").check() is True
    assert ollama(tags(["llama3:latest"])).check() is False

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert ollama(down).check() is False


# ---------------------------------------------------------------- hybrid


def test_hybrid_sends_fast_jobs_local_and_main_jobs_to_gemini() -> None:
    main, local = FakeLLM([{"who": "gemini"}]), FakeLLM([{"who": "local"}])
    llm = RoutedLLM(main=main, local=local)
    assert isinstance(llm, LLM)
    assert llm.generate_json("p", SCHEMA, ModelRole.FAST) == {"who": "local"}
    assert llm.generate_json("p", SCHEMA, ModelRole.MAIN) == {"who": "gemini"}


def test_hybrid_main_falls_back_to_local_when_gemini_is_unavailable() -> None:
    main, local = FakeLLM(fail=True), FakeLLM([{"who": "local"}])
    llm = RoutedLLM(main=main, local=local)
    assert llm.generate_json("p", SCHEMA, ModelRole.MAIN) == {"who": "local"}
    assert main.calls == 1 and local.calls == 1


def test_hybrid_check_is_ok_when_one_side_works() -> None:
    assert RoutedLLM(main=FakeLLM(healthy=False), local=FakeLLM(healthy=True)).check() is True
    assert RoutedLLM(main=FakeLLM(healthy=False), local=FakeLLM(healthy=False)).check() is False


# ---------------------------------------------------------------- JSON helper


def test_parse_json_object_accepts_code_fences_and_rejects_lists() -> None:
    assert parse_json_object('```json\n{"x": "১"}\n```') == {"x": "১"}
    with pytest.raises(LLMUnavailable):
        parse_json_object("[1, 2]")
