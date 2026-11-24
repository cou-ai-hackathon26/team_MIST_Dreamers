"""LLM adapter: Google Gemini through the google-genai SDK (FR-AGT-16, C-05).

- `role` picks the model: MAIN -> GEMINI_MODEL_MAIN, FAST -> GEMINI_MODEL_FAST.
- JSON answers use the SDK's JSON mode with our JSON schema (`response_json_schema`).
- Several free keys (GEMINI_API_KEYS=key1,key2): when a key is rate-limited (429) or invalid,
  the next key is used. Network or server errors get one retry after 1 second.
- GEMINI_MODEL_FALLBACK (optional): when the model still fails (for example 503 "high demand", which
  is per model), the same request is tried once more on this model. Then LLMUnavailable.
- check() lists models with the current key (no generation, no quota used); cached for 60 s.
Keys never appear in logs or error messages; keys are named by position (#1, #2, ...).
"""

import logging
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.application.ports.llm import ModelRole
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.common import LLMStats, parse_json_object

log = logging.getLogger(__name__)

ClientFactory = Callable[[str], Any]  # api key -> object with .models.generate_content / .models.list
BACKOFF_SECONDS = 1.0
CHECK_TTL_SECONDS = 60.0


def _default_client_factory(timeout_s: float) -> ClientFactory:
    def make(api_key: str) -> Any:
        from google import genai
        from google.genai import types

        options = types.HttpOptions(api_version="v1beta", timeout=int(timeout_s * 1000))
        return genai.Client(api_key=api_key, http_options=options)

    return make


class _Rejected(LLMUnavailable):
    """Gemini refused the request itself (HTTP 400): another model would refuse it too."""


def _is_key_problem(exc: Exception) -> bool:
    """Rate limit, quota or a bad key: another key may work."""
    code = getattr(exc, "code", None)
    message = str(getattr(exc, "message", "") or exc).lower()
    return code in (401, 403, 429) or (code == 400 and "api key" in message)


class GeminiLLM:
    def __init__(
        self,
        api_keys: Sequence[str],
        model_main: str,
        model_fast: str,
        timeout_s: float = 20.0,
        client_factory: ClientFactory | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        fallback_model: str = "",
    ) -> None:
        self._keys = [k for k in api_keys if k]
        self._models = {ModelRole.MAIN: model_main, ModelRole.FAST: model_fast}
        self._fallback_model = fallback_model.strip()
        self._factory = client_factory or _default_client_factory(timeout_s)
        self._clients: dict[int, Any] = {}
        self._key_index = 0
        self._lock = threading.Lock()
        self._sleep = sleep
        self._clock = clock
        self._checked: tuple[float, bool] | None = None
        self.stats = LLMStats()

    @property
    def configured(self) -> bool:
        return bool(self._keys) and all(self._models.values())

    def _client(self, index: int) -> Any:
        with self._lock:
            if index not in self._clients:
                self._clients[index] = self._factory(self._keys[index])
            return self._clients[index]

    # ---------------------------------------------------------------- LLM port

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_json_schema": dict(schema),
        }
        return parse_json_object(self._generate(prompt, role, config))

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        return self._generate(prompt, role, {"temperature": 0.2}).strip()

    def check(self) -> bool:
        now = self._clock()
        if self._checked is not None and now - self._checked[0] < CHECK_TTL_SECONDS:
            return self._checked[1]
        ok = False
        if self.configured:
            try:
                next(iter(self._client(self._key_index).models.list(config={"page_size": 1})), None)
                ok = True
            except Exception as exc:  # any failure means "not usable right now"
                log.warning("Gemini check failed with key #%d: %s", self._key_index + 1, type(exc).__name__)
        self._checked = (now, ok)
        return ok

    # ---------------------------------------------------------------- calling with key rotation

    def _generate(self, prompt: str, role: ModelRole, config: dict[str, Any]) -> str:
        if not self.configured:
            raise LLMUnavailable("Gemini is not configured (GEMINI_API_KEYS / GEMINI_MODEL_*)")
        primary = self._models[role]
        try:
            return self._generate_with(primary, prompt, role, config)
        except _Rejected:
            raise  # a bad request fails the same way on another model
        except LLMUnavailable:
            # "High demand" (503) and quotas are per model: a second model often still answers.
            if not self._fallback_model or self._fallback_model == primary:
                raise
            log.warning("Gemini %s unavailable; trying fallback model %s", primary, self._fallback_model)
            return self._generate_with(self._fallback_model, prompt, role, config)

    def _generate_with(self, model: str, prompt: str, role: ModelRole, config: dict[str, Any]) -> str:
        from google.genai import errors as genai_errors

        keys_left = len(self._keys)  # each key gets one chance per question
        retried = False
        while True:
            index = self._key_index
            started = time.perf_counter()
            try:
                response = self._client(index).models.generate_content(
                    model=model, contents=prompt, config=config
                )
                elapsed = time.perf_counter() - started
                self.stats.record(elapsed, ok=True)
                log.info("gemini %s call %.2fs (key #%d)", role.value, elapsed, index + 1)
                return response.text or ""
            except genai_errors.ClientError as exc:
                self.stats.record(time.perf_counter() - started, ok=False)
                if not _is_key_problem(exc):
                    raise _Rejected(f"Gemini rejected the request (HTTP {exc.code})") from exc
                log.warning("Gemini key #%d unusable (HTTP %s); trying the next key", index + 1, exc.code)
                keys_left -= 1
                with self._lock:
                    self._key_index = (index + 1) % len(self._keys)
                if keys_left > 0:
                    continue
                if retried:
                    raise LLMUnavailable("all Gemini keys are rate-limited or invalid") from exc
            except Exception as exc:  # server error, timeout, network: transient
                self.stats.record(time.perf_counter() - started, ok=False)
                log.warning("Gemini call failed (%s)", type(exc).__name__)
                if retried:
                    raise LLMUnavailable("Gemini is not responding") from exc
            retried = True  # one retry after a short wait
            keys_left = 1
            self._sleep(BACKOFF_SECONDS)
